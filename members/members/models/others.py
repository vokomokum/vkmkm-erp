'''
Models of second order in this app
'''

from sqlalchemy import Column, Integer, Unicode, ForeignKey
from sqlalchemy.orm import relationship

from setup import Base


class SecondOrderModelException(Exception):
    pass


class Order(Base):

    __tablename__ = 'wh_order'

    id = Column('ord_no', Integer, primary_key=True)
    label = Column('ord_label', Unicode(255))

    def __init__(self):
        raise SecondOrderModelException('Creation of an order not allowed in this application.')

    def __repr__(self):
        return self.label

