'''
Models of second order in this app
'''

from sqlalchemy import Column, Integer, Unicode, ForeignKey
from sqlalchemy.orm import relationship

from setup import Base


class SecondOrderModelException(Exception):
    pass


class Order(Base):
    '''
    Helper class to work with orders. This table has no direct PK,
    but we use two fields as combined identification.
    Instead of simply querying all orders you can do this:
    session.query(distinct(Order.id, Order.label))
    Example-use in views/workgroup
    '''
    __tablename__ = 'wh_order'

    id = Column('ord_no', Integer, primary_key=True)
    label = Column('ord_label', Unicode(255), primary_key=True)

    def __init__(self):
        raise SecondOrderModelException('Creation of an order not allowed in this application.')

    def __repr__(self):
        return self.label

