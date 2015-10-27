from pyramid.view import view_config
import datetime
import json

from members.views.base import BaseView
from members.models.member import Member
from members.models.transactions import Transaction
from members.models.transactions import TransactionType
from members.models.transactions import get_ttypeid_by_name
from members.models.base import DBSession
from members.utils.mail import sendmail
from members.utils.misc import membership_fee, ascii_save
from members.utils.security import authenticated_user
#from members.utils.graphs import orders_money_and_people

@view_config(renderer='json', route_name='charge-members')
class ChargeMembers(BaseView):
    
    def __call__(self):
        '''
        Create transactions which charge members.

        Expects a list of dicts where each has these fields:
        * user_id
        * order_id
        * amount > 0
        * note (optional)

        Returns JSON dict with status (ok|error) and a msg.
        msg describes number of created, updated transactions and how
        many membership fees were charged for first-time orderers.
        '''
        try:
            session = DBSession()
            charge_ttype_id = get_ttypeid_by_name('Order Charge')
            # this endpoint is available from remote apps
            user = authenticated_user(self.request, bypass_ip=True)
            if not user or\
            (not 'Finance' in [wg.name for wg in user.workgroups]\
                and not user.mem_admin):
                return dict(status='error', 
                            msg='Only Finance people can do this.')
            
            # get data from request body
            try:
                parsed_body = json.loads(self.request.body)
            except Exception, e:
                return dict(status='error',
                            msg='Body could not be parsed: {}.'.format(e))
            if not 'charges' in parsed_body:
                return dict(status='error', msg='No "charges" list found in request body.')
            charges = parsed_body['charges']
            if not isinstance(charges, list):
                return dict(status='error', msg='Charges are not given as list.')

            # rule out non-positive amounts
            charges = [c for c in charges if c['amount'] > 0]
            
            # now we make charges and also membership fees
            created = 0
            updated = 0
            first_orderers = []
            for c in charges:
                member = session.query(Member).get(c['user_id'])
                if not member:
                    return dict(status='error',
                                msg='No member with id {} could be found.'\
                                    .format(c['user_id']))
                existing_order_charges = [t for t in member.transactions\
                                          if t.ttype_id == charge_ttype_id\
                                          and t.ord_no == c['order_id']]
                comment = c.get('note')
                if not comment:
                    comment = 'Automatically charged for order {}.'\
                              .format(c['order_id']) 
                amount = float(c['amount'])
                if not existing_order_charges:
                    t = Transaction(amount=-1 * amount, comment=comment)
                    ttype = session.query(TransactionType)\
                                         .get(charge_ttype_id)
                    t.ttype = ttype
                    t.member = member
                    t.ord_no = c['order_id']
                    created += 1
                else:
                    if len(existing_order_charges) > 1:
                        return dict(status='error',
                                    msg='Member {} was charged twice for order {}.'\
                                        ' This should be fixed first!'\
                                        .format(c['user_id'], c['order_id']))
                    t = existing_order_charges[0]
                    t.amount = -1 * amount
                    t.comment = comment
                    updated += 1
                t.validate()
                session.add(t)
                # first order charge of this member? Charge Membership fee
                existing_charge = [t for t in member.transactions\
                                   if t.ttype_id == charge_ttype_id]
                if not existing_charge:
                    first_orderers.append(member)
                    mf = Transaction(\
                            amount = membership_fee(member) * -1,
                            comment = 'Automatically charged (for {}'\
                            ' people in the household) on first-time'\
                            ' order ({})'\
                            .format(member.mem_household_size,
                                    c['order_id'])
                    )
                    ttype = session.query(TransactionType)\
                                .get(get_ttypeid_by_name('Membership Fee'))
                    mf.ttype = ttype
                    mf.member = member
                    mf.validate()
                    session.add(mf)
            # updating graph data doesn't work anymore because we don't have orders in-house
            # orders_money_and_people()
            # inform membership about people who ordered for first time
            subject = 'First-time orderers'
            body = 'FYI: Below is a list of people who ordered for the'\
                    ' first time today. This mail was auto-generated.\n\n'
            body += '\n'.join(['{} [ID:{}]'.format(ascii_save(m.fullname), m.mem_id)\
                                for m in first_orderers])
            sendmail('membership@vokomokum.nl', subject, body,
                    folder='order-charge-notifications',
                    sender='finance@vokomokum.nl')

            return dict(status='ok', msg='Created {} & updated {} transactions.'
                                        'Charged {} times membership fee.'\
                                        .format(created, updated,
                                                len(first_orderers)))
        except Exception, e:
            return dict(status='error', msg="{}: {}".format(str(type(e)), str(e)))


@view_config(renderer='json', route_name='mail-payment-reminders')
class MailPaymentReminders(BaseView):

    def __call__(self):
        '''
        Send members an email about their negative balance.
        We keep copies of the mails in folders, by date.
        '''
        sent = 0
        try:
            # this endpoint is available from remote apps
            user = authenticated_user(self.request, bypass_ip=True)
            if not user or\
                (not 'Finance' in [wg.name for wg in user.workgroups]\
                 and not user.mem_admin):
                return dict(status='error', 
                            msg='Only Finance people can do this.')
 
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
                        folder='payment-reminders/{}-{}-{}'\
                               .format(deadline.year, deadline.month, deadline.day),
                        filename='MemberNo{}'.format(m.mem_id))
                sent += 1
        except Exception, e:
            return dict(status='error', msg="{}: {}".format(str(type(e)), str(e)))
        return dict(status='ok', msg=u'{} emails with payment reminders have been'\
                                      ' sent to members.'.format(sent))

