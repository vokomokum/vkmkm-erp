from sqlalchemy import Table, Column, Integer, Unicode

from pyramid.security import Allow, DENY_ALL

from base import Base, VokoValidationError


class Applicant(Base):
    __tablename__ = 'applicants'

    id = Column(Integer, primary_key=True)
    fname = Column(Unicode(50))
    lname = Column(Unicode(50))
    month = Column(Unicode(5))
    comment = Column(Unicode(500))
    email = Column(Unicode(50), unique=True)
    telnr = Column(Unicode(20))

    __acl__ = [(Allow, 'group:membership', ('view', 'edit')),
               (Allow, 'group:wg-members', 'view'),
               DENY_ALL]

    def __init__(self, request=None, fname='', lname='', month='', comment='',
                 email='', telnr=''):
        ''' receiving request makes this class a factory for views '''
        self.fname = fname
        self.lname = lname
        self.month = month
        self.comment = comment
        self.email = email
        self.telnr = telnr

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


