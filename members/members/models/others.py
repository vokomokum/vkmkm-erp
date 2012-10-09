'''
Models of second order in this app
'''

from sqlalchemy import Column, Integer, Unicode, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from base import Base, DBSession


class NotAllowedActionException(Exception):
    pass


class Order(Base):
    '''
    Helper class to work with orders. This table has no direct PK,
    but we use two fields as combined identification.
    Instead of simply querying all orders (to all suppliers) you can do this:
    session.query(distinct(Order.id, Order.label))
    Not in use right now, but might be useful some day ...
    '''
    __tablename__ = 'wh_order'

    id = Column('ord_no', Integer, primary_key=True)
    label = Column('ord_label', Unicode(255), primary_key=True)
    completed = Column('who_order_completed', DateTime)
    
    def __init__(self):
        raise NotAllowedActionException('Creation of an order not '\
                                        'allowed in this application.')


def get_order_label(order_id):
    dbsession = DBSession()
    query = """SELECT DISTINCT ord_label FROM wh_order WHERE ord_no = %d;"""\
                                                         % order_id
    return list(dbsession.execute(query))[0][0]
