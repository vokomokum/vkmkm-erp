from pyramid.view import view_config
import datetime

from members.views.base import BaseView
from members.models.member import Member
from members.models.orders import Order, MemberOrder
from members.models.transactions import Transaction
from members.models.transactions import TransactionType
from members.models.transactions import get_ttypeid_by_name
from members.models.base import DBSession
from members.utils.mail import sendmail
from members.utils.misc import membership_fee, ascii_save
from members.utils.graphs import orders_money_and_people


@view_config(renderer='../templates/order-charges.pt', route_name='charge-order')
class ChargeOrder(BaseView):
    
    tab = 'finance'

    def __call__(self):
        '''
        Create order charges for a given order in the system
        '''
        o_id = int(self.request.matchdict['o_id'])
        session = DBSession()
        order = session.query(Order).\
                filter(Order.id == o_id).first()
        if not order:
            return dict(msg='An order with ID {} does not exist.'.format(o_id),
                        order=None, action=None)
        charge_ttype_id = get_ttypeid_by_name('Order Charge')

        if not 'Finance' in [wg.name for wg in self.user.workgroups]\
            and not self.user.mem_admin:
            return dict(order=order, action=None, 
                        msg='Only Finance people can do this.')
        # all (positive) charges for members who have not been charged for 
        # this order yet
        charges = [MemberOrder(m, order) for m in session.query(Member).all()]
        charges = [c for c in charges if c.amount > 0 and not o_id in\
                                [t.order.id for t in c.member.transactions\
                                            if t.ttype_id == charge_ttype_id]]
        first_orderers = []

        if not 'action' in self.request.params:
            # show charges that would be made
            return dict(order=order, action='show', charges=charges)
        else:
            # temporary backdoor to test this
            if self.request.params['action'] == 'gggraph':
                orders_money_and_people()
            if self.request.params['action'] == 'charge':
                # confirmation: make charges
                for c in charges:
                    t = Transaction(amount = -1 * c.amount,
                        comment = 'Automatically charged.' 
                    )
                    ttype = session.query(TransactionType)\
                                   .get(charge_ttype_id)
                    t.ttype = ttype
                    t.member = c.member
                    t.order = c.order
                    t.validate()
                    session.add(t)
                    # first order of this member? Charge Membership fee
                    if c.is_first_order():
                        first_orderers.append(c.member)
                        mf = Transaction(\
                                amount = membership_fee(c.member) * -1,
                                comment = 'Automatically charged (for {}'\
                                ' people in the household) on first-time'\
                                ' order ({})'\
                                .format(c.member.mem_household_size,
                                        c.order.label)
                        )
                        ttype = session.query(TransactionType)\
                                    .get(get_ttypeid_by_name('Membership Fee'))
                        mf.ttype = ttype
                        mf.member = c.member
                        mf.validate()
                        session.add(mf)
                # use this opportunity to update graph data
                orders_money_and_people()
                # inform membership about people who ordered for first time
                subject = 'First-time orderers'
                body = 'FYI: Below is a list of people who ordered for the'\
                       ' first time today. This mail was auto-generated.\n\n'
                body += '\n'.join(['{} [ID:{}]'.format(ascii_save(m.fullname), m.mem_id)\
                                  for m in first_orderers])
                sendmail('membership@vokomokum.nl', subject, body,
                        folder='order-charges/{}'.format(o_id),
                        sender='finance@vokomokum.nl')

                return dict(order=order, action='done')
        return dict(order=order, action='')


@view_config(renderer='json', route_name='mail-payment-reminders')
class MailPaymentReminders(BaseView):

    def __call__(self):
        '''
        Send members an email about their negative balance.
        We keep copies of the mails in folders, by date.
        '''
        try:
            session = DBSession()
            members = [m for m in session.query(Member).all() if m.balance < 0]
            now = datetime.datetime.now()
            deadline = now + datetime.timedelta(days = 3)
            weekdays_en= ['monday', 'tuesday', 'wednesday', 'thursday',
                        'friday', 'saturday', 'sunday']
            weekdays_nl = ['maandag', 'dinsdag', 'woensdag', 'donderdag',
                        'vrijdag', 'zaterdag', 'zondag']
            deadline_en = '{} {}.{}.{}'.format(weekdays_en[deadline.weekday()],
                            deadline.day, deadline.month, deadline.year)
            deadline_nl = '{} {}.{}.{}'.format(weekdays_nl[deadline.weekday()],
                            deadline.day, deadline.month, deadline.year)
            for m in members:
                subject = 'Payment request / Verzoek tot betaling'
                mail_templ = open('members/templates/payment_reminders.eml', 'r')
                mail = mail_templ.read()
                body = mail.format(mem_id=m.mem_id, amount=m.balance,
                        deadline_nl=deadline_nl, deadline_en=deadline_en)
                sendmail(m.mem_email, subject, body,
                        sender='finance@vokomokum.nl',
                        folder='payment-reminders/{}'.format(),
                        filename='MemberNo{}'.format(m.mem_id))
        except Exception, e:
            return dict(status='error', msg=str(e))
        return dict(status='ok', msg=u'Emails with payment reminders have been'\
                                      ' to members.')

