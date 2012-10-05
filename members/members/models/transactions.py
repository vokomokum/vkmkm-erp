from sqlalchemy import Table, Column, Integer, Unicode, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey

from pyramid.security import Allow, DENY_ALL

from base import Base, VokoValidationError
from member import Member


class TransactionType(Base):
    __tablename__ = 'transaction_types'

    id = Column(Integer, primary_key=True)
    fname = Column(Unicode(50), unique=True)

    __acl__ = [(Allow, 'group:finance', ('view', 'edit')),
               (Allow, 'group:wg-members', 'view'),
               DENY_ALL]

    def __init__(self, request=None, name=''):
        ''' receiving request makes this class a factory for views '''
        self.name = fname

    def __repr__(self):
        return self.name

    def validate(self):
        ''' validate if this object is valid, raise exception otherwise '''
        if self.name == '':
            raise VokoValidationError('A transaction type needs a name.')

