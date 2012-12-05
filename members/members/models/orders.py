'''
Models of second order in this app
'''

from sqlalchemy import Column, Integer, Unicode, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from datetime import datetime

from base import Base, DBSession, CreationForbiddenException
from members.models.member import Member
from members.utils.misc import running_sqlite


class Order(Base):
    '''
    Helper class to work with orders. This table has no direct PK,
    but we use two fields as combined identification.
    Instead of simply querying all orders (to all suppliers) you can do this:
    session.query(distinct(Order.id, Order.label))
    '''
    __tablename__ = 'wh_order'

    id = Column('ord_no', Integer, primary_key=True)
    label = Column('ord_label', Unicode(255), primary_key=True)
    completed = Column('who_order_completed', DateTime)
    
    def __init__(self):
        raise CreationForbiddenException('Creation of an order not '\
                                        'allowed in this application.')

    def __repr__(self):
        return self.label


def get_order_amount(ord_no, mem_id):
    ''' let DB compute amount for this member on this order in EUR  '''
    query = """SELECT * FROM order_totals({}, {});""".format(ord_no, mem_id)
    if running_sqlite():
        return -1
    return list(DBSession().connection().engine.execute(query))[0][11] / 100.


class MemberOrder(object):
    '''
    Helper class to model member orders (Note: not a DB model class)
    '''

    def __init__(self, member, order):
        self.member = member
        self.order = order
        self._mnt = -1

    @property
    def amount(self):
        ''' lazily use get_order_amount to compute this once when needed '''
        if self._mnt == -1:
            self._mnt = get_order_amount(self.member.mem_id, self.order.id)
        return self._mnt

    def is_first_order(self):
        '''
        True if this member is ordering for the first time.
        The modern way would be to check for an Order Charge transaction,
        however we have to check legacy data from before Nov 2012, as well.
        '''
        now = datetime.now()
        query = "SELECT count(*) FROM mem_order WHERE mem_id = {} AND memo_amt > 0"\
                " AND memo_completed < '{}';".format(self.member.mem_id, str(now))
        if running_sqlite():
            return False
        return int(list(DBSession().connection().engine.execute(query))[0][0]) == 0


"""
doesn't work yet (see model/workgroups.py how to do it right, i.e. how to 
connect ord_no and mem_id, since this basically represents an m:n table - 
but is also not needed right now, anyway)
class MemberOrder(Base):
    '''
    Helper class to work with orders by members. This table has no direct PK,
    but uses two fields as combined identification: ord_no and mem_id
    '''
    __tablename__ = 'mem_order'

    ord_no = Column(Integer, ForeignKey('members.mem_id'), nullable=False, primary_key=True)
    mem_id = Column(Integer, ForeignKey('members.mem_id'), nullable=False, primary_key=True)
    completed = Column('memo_completed', DateTime)
    amount = Column('memo_amt', Integer)
    order = relationship(Order, backref='member_orders')
    member = relationship(Member, backref='orders')
    
    def __init__(self):
        raise CreationForbiddenException('Creation of an order not '\
                                        'allowed in this application.')

    def __repr__(self):
        return "Order of {}".format(self.member)
"""
