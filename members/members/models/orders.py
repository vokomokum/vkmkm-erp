'''
Models of second order in this app
'''

from sqlalchemy import Column, Integer, Unicode, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from base import Base, DBSession, CreationForbiddenException
from members.models.member import Member


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


def get_order_label(ord_no):
    dbsession = DBSession()
    query = """SELECT DISTINCT ord_label FROM wh_order WHERE ord_no = {};"""\
                                                .format(ord_no)
    return list(dbsession.execute(query))[0][0]

def get_order_amount(ord_no, mem_id):
    '''TODO: look at Jims email to get this right, do sthg else if sqlite'''
    dbsession = DBSession()
    query = """SELECT amount FROM order... WHERE ord_no = {} and mem_id = {};"""\
                                                .format(ord_no, mem_id)
    return list(dbsession.execute(query))[0][0]


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
