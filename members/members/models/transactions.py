from sqlalchemy import Table, Column
from sqlalchemy import Integer, Unicode, Boolean, Numeric, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey

from pyramid.security import Allow, DENY_ALL

from base import Base, VokoValidationError
from member import Member


class TransactionType(Base):
    __tablename__ = 'transaction_types'

    id = Column(Integer, primary_key=True)
    # TODO: comment?
    name = Column(Unicode(100), unique=True)

    __acl__ = [(Allow, 'group:finance', ('view', 'edit')),
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


class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    ttype_id = Column(Integer, ForeignKey('transaction_types.id'), nullable=False)
    ttype = relationship(TransactionType, backref='transactions')
    amount = Column(Numeric)
    mem_id = Column(Integer, ForeignKey('members.mem_id'), nullable=False)
    member = relationship(Member, backref='transactions')
    #comment = Column(Unicode(100))
    ord_no = Column(Integer)
    date = Column(DateTime)
    late = Column(Boolean, default=False)

    __acl__ = [(Allow, 'group:finance', ('view', 'edit')),
               (Allow, 'group:wg-members', 'view'),
               DENY_ALL]

    def __init__(self, request=None, name=''):
        self.name = name

    def __repr__(self):
        return "{}; {}: {} EUR".format(self.member, self.ttype, self.amount)


