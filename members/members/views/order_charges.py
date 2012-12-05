import os
import base64

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


def get_charges(order, session):
    ''' get all (positive) order charges for this order '''
    charges = [MemberOrder(m, order) for m in\
                session.query(Member).all()]
    return [c for c in charges if c.amount > 0]


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
        charge_ttype_id = get_ttypeid_by_name('Order Charge')

        if not 'Finance' in [wg.name for wg in self.user.workgroups]\
            and not self.user.mem_admin:
            return dict(order=order, action=None, 
                        msg='Only Finance people can do this.')
        # all charges for members who have not been charged for 
        # this order yet
        charges = [c for c in get_charges(order, session) if not o_id in\
                    [t.order.id for t in c.member.transactions\
                                if t.ttype_id == charge_ttype_id]]

        if not 'action' in self.request.params:
            # show charges that would be made
            return dict(order=order, action='show', charges=charges)
        else:
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
                        # charge membership fee
                        mf = Transaction(\
                                amount = c.member.mem_household_size * 10 * -1,
                                comment = 'automatically charged (for {}'\
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
                return dict(order=order, action='done')
        return dict(order=order, action='')


@view_config(renderer='../templates/base.pt', route_name='mail-order-charges')
class MailOrderCharges(BaseView):

    tab = 'finance'

    def __call__(self):
        '''
        Send members an email about their order charge
        '''
        o_id = self.request.matchdict['o_id']
        session = DBSession()
        order = session.query(Order).\
                    filter(Order.id == o_id).first()
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
        for c in get_charges(order, session):
            subject = 'Please pay for order of {}'.format(order.label)
            mail_templ = open('members/templates/order_charge_txt.eml', 'r')
            mail = mail_templ.read()
            body = mail.format(label=order.label, amount=c.amount,
                       deadline_nl=deadline_nl, deadline_en=deadline_en)
            sendmail(c.member.mem_email, subject, body,
                        folder='order-charges/{}'.format(order.id),
                        sender='finance@vokomokum.nl')
        return dict(msg=u'Emails with order charges have been sent out '\
                        'for order {}'.format(order.label))

