from sqlalchemy import Table, Column
from sqlalchemy import Integer, Unicode, Boolean, Numeric, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey

from pyramid.security import Allow, DENY_ALL

import datetime

from base import Base, VokoValidationError, DBSession
from member import Member
from orders import Order
from members.utils.misc import ascii_save


# These types have special meaning and a re therefore protected
reserved_ttype_names = ['Membership Fee', 'Order Charge']


class TransactionType(Base):
    __tablename__ = 'transaction_types'

    id = Column(Integer, primary_key=True)
    # TODO: comment?
    name = Column(Unicode(100), unique=True)

    __acl__ = [(Allow, 'group:admins', ('view', 'edit')),
               (Allow, 'group:finance', ('view', 'edit')),
               (Allow, 'group:members', 'view'),
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

    @property
    def locked(self):
        ''' Transaction type can't be removed if transactions use it ''' 
        return len(self.transactions) > 0

    @property
    def reserved(self):
        '''
        Returns True if the name of this transaction type cannot be changed
        '''
        return self.name in reserved_ttype_names


def get_ttypeid_by_name(name):
    session = DBSession()
    tt = session.query(TransactionType)\
                .filter(TransactionType.name == name).first()
    return tt.id 


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
               DENY_ALL]

    def __init__(self, request=None, ttype_id=None, amount=0, mem_id=None,
                 comment='', ord_no=None, date=datetime.datetime.now(), late=False):
        self.ttype_id = ttype_id
        self.amount = amount
        self.mem_id = mem_id
        self.comment = comment
        self.ord_no = ord_no
        self.date = date
        self.late = late

    def __repr__(self):
        return "EUR {} from {} [{}]".format(round(self.amount, 2), 
                                            ascii_save(self.member.fullname),
                                            self.ttype)

    def locked(self):
        '''
        Transactions can't be removed by the app if they were created
        by the system based on existing data (for now: Order Charge) ''' 
        if self.ttype.name == 'Order Charge':
            return True
        return False

    def validate(self):
        ''' validate if this object is valid, raise exception otherwise '''
        try:
            _ = float(self.amount)
        except Exception, e:
            raise VokoValidationError('The amount is not numeric - maybe it '\
                                      'contains illegal characters (please '\
                                      'write numbers with a dot, e.g. "3.89").')
        if not self.ttype:
            raise VokoValidationError('A transaction needs a type.')
        if not self.member:
            raise VokoValidationError('A transaction needs a member.')
        if self.ttype.name in ['Order Charge', 'Membership Fee']\
            and self.amount > 0:
            raise VokoValidationError('A transaction of this type is charged '\
                                      'from members and should be negative.')

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
