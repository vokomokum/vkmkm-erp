from sqlalchemy import Table, Column, Integer, Unicode

from pyramid.security import Allow, DENY_ALL

from members.models.base import Base, VokoValidationError


class Applicant(Base):
    __tablename__ = 'applicants'

    id = Column(Integer, primary_key=True)
    fname = Column(Unicode(50))
    lname = Column(Unicode(50))
    month = Column(Unicode(5))
    comment = Column(Unicode(500))
    email = Column(Unicode(50), unique=True)
    telnr = Column(Unicode(20))
    household_size = Column(Integer, default=0)

    __acl__ = [(Allow, 'group:membership', ('view', 'edit')),
               (Allow, 'group:admins', ('view', 'edit')),
               (Allow, 'group:members', 'view'),
               DENY_ALL]

    def __init__(self, request=None, fname='', lname='', month='', comment='',
                 email='', telnr='', household_size=0):
        ''' receiving request makes this class a factory for views '''
        self.fname = fname
        self.lname = lname
        self.month = month
        self.comment = comment
        self.email = email
        self.telnr = telnr
        self.household_size = int(household_size)

    def __repr__(self):
        return '{} {}'.format(self.fname, self.lname)

    def validate(self):
        ''' validate if this object is valid, raise exception otherwise '''
        if self.fname == '' or self.lname == '':
            raise VokoValidationError('An applicant needs first- and lastname.')
        if self.email == '':
            raise VokoValidationError('An applicant needs an email.')
        if self.telnr == '':
            raise VokoValidationError('An applicant needs a telephone number.')
        if self.household_size < 1:
            raise VokoValidationError('Please specify how many people live '\
                                      'the household.')

