from sqlalchemy import Table, Column
from sqlalchemy import Integer, Unicode, Boolean, Numeric, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey

from pyramid.security import Allow, DENY_ALL

from datetime import datetime

from base import Base, VokoValidationError
from member import Member
from others import Order


class TransactionType(Base):
    __tablename__ = 'transaction_types'

    id = Column(Integer, primary_key=True)
    # TODO: comment?
    name = Column(Unicode(100), unique=True)

    __acl__ = [(Allow, 'group:admins', ('view', 'edit')),
               (Allow, 'group:finance', ('view', 'edit')),
               (Allow, 'group:wg-members', 'view'),
               DENY_ALL]

    def __init__(self, request=None, name=''):
        ''' receiving request makes this class a factory for views '''
        self.name = name

    def __repr__(self):
        return self.name

    def validate(self):
        ''' validate if this object is valid, raise exception otherwise '''
        if self.name == '':
            raise VokoValidationError('A transaction type needs a name.')

    def locked(self):
        ''' Transaction type can't be removed if transactions use it ''' 
        return len(self.transactions) > 0


class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    ttype_id = Column(Integer, ForeignKey('transaction_types.id'), nullable=False)
    ttype = relationship(TransactionType, backref='transactions')
    amount = Column(Numeric)
    mem_id = Column(Integer, ForeignKey('members.mem_id'), nullable=False)
    member = relationship(Member, backref='transactions')
    comment = Column(Unicode(500))
    ord_no = Column(Integer, ForeignKey('wh_order.ord_no'), nullable=True)
    order = relationship(Order, backref='transactions')
    date = Column(DateTime)
    late = Column(Boolean, default=False)

    __acl__ = [(Allow, 'group:admins', ('view', 'edit')),
               (Allow, 'group:finance', ('view', 'edit')),
               (Allow, 'group:wg-members', 'view'),
               DENY_ALL]

    def __init__(self, request=None, ttype_id=None, amount=0, mem_id=None,
                 comment='', ord_no=None, date=datetime.now(), late=False):
        self.ttype_id = ttype_id
        self.amount = amount
        self.mem_id = mem_id
        self.comment = comment
        self.ord_no = ord_no
        self.date = date
        self.late = late

    def __repr__(self):
        return "{}; [{}]: EUR {}".format(self.member, self.ttype, self.amount)

    def locked(self):
        ''' Transactions can't be removed if they're from last cal. month ''' 
        begin_of_this_month = datetime.now()
        begin_of_this_month.day = 1
        begin_of_this_month.hour = 0
        begin_of_this_month.minute = 0
        return self.date < begin_of_this_month

    def validate(self):
        ''' validate if this object is valid, raise exception otherwise '''
        if not self.ttype:
            raise VokoValidationError('A transaction needs a type.')
        if not self.member:
            raise VokoValidationError('A transaction needs a member.')
        if self.amount <= 0:
            raise VokoValidationError('A transaction should have a positive'\
                                      ' amount.')

"""
def get_transaction(session, request):
    ''' get transaction object from id '''
    if (request and 't_id' in request.matchdict
         and int(request.matchdict['t_id']) >= 0):
            transaction = session.query(Transaction).get(request.matchdict['t_id'])
    else:
        transaction = None
    return transaction
"""
