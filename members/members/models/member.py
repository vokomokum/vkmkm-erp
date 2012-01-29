'''
member
=========

The member class.
Describes all attributes of the database we need here.
'''

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Unicode
from sqlalchemy import Boolean
from sqlalchemy import DateTime

from pyramid.security import Allow, DENY_ALL

from setup import Base, VokoValidationError


class Member(Base):
    '''
    Data model
    '''
    __tablename__ = 'members'

    mem_id = Column(Integer, primary_key=True)
    mem_fname = Column(Unicode(255), default=u'')
    mem_prefix = Column(Unicode(255), default=u'')
    mem_lname = Column(Unicode(255), default=u'')
    mem_email = Column(Unicode(255), default=u'')
    mem_street =  Column(Unicode(255), default=u'')
    mem_house = Column(Unicode(255), default=u'')
    mem_flatno = Column(Unicode(255), default=u'')
    mem_city = Column(Unicode(255), default=u'')
    mem_postcode = Column(Unicode(6), default=u'')
    mem_home_tel = Column(Unicode(25), default=u'')
    mem_work_tel = Column(Unicode(255), default=u'')
    mem_mobile = Column(Unicode(25), default=u'')
    mem_bank_no = Column(Unicode(255), default=u'')
    mem_enc_pwd = Column(Unicode(255), default=u'')
    mem_pwd_url = Column(Unicode(255), default=u'')
    mem_cookie = Column(Unicode(255), default=u'')
    mem_ip = Column(Unicode(255), default=u'')
    mem_active = Column(Boolean(), default=False)
    mem_membership_paid = Column(Boolean(), default=False)
    mem_admin = Column(Boolean(), default=False)
    mem_adm_adj = Column(Boolean(), default=False)
    # unused fields - TODO: do we need them?
    #mem_adm_comment = Column(Unicode(255), default=u'')
    #mem_message = Column(Unicode(255), default=u'')
    #mem_news = Column(Unicode(255), default=u'')
    #mem_message_auth = Column(Integer())
    #mem_message_date = Column(DateTime()) #timestamp

    __acl__ = [ (Allow, 'group:admins', ('view', 'edit')),
                (Allow, 'group:this-member', ('view', 'edit')),
                (Allow, 'group:members', ('view')),
                DENY_ALL]

    def __init__(self, request=None, fname='', prefix='', lname=''):
        ''' receiving request makes this class a factory for views '''
        self.mem_active = True
        self.exists = False
        self.mem_fname = fname
        self.mem_prefix = prefix
        self.mem_lname = lname

    def __repr__(self):
        return self.fullname()

    def fullname(self):
        return "%s %s %s" %\
            (self.mem_fname or '', self.mem_prefix or '', self.mem_lname or '')

    def addr_street(self):
        return "%s %s%s" % (self.mem_street, self.mem_house, self.mem_flatno)

    def addr_city(self):
        return "%s %s" % (self.mem_postcode, self.mem_city)

    def validate(self):
        ''' checks on address, bank account, passwords, ...
        '''
        # check missing fields
        missing = []
        for f in ('mem_fname', 'mem_lname', 'mem_email',
                  'mem_street', 'mem_house', 'mem_postcode', 'mem_city',
                  'mem_bank_no'):
            if not self.__dict__.has_key(f) or self.__dict__[f] == '':
                missing.append(f)
        if len(missing) > 0:
            raise VokoValidationError('We still require you to fill in: %s'\
                                    % ', '.join([m[4:] for m in missing]))
        # TODO check email
        if not '@' in self.mem_email:
            raise VokoValidationError('The email address does not seem to be valid.')
        # check postcode
        if not (self.mem_postcode[:4].isdigit() and self.mem_postcode[-2:].isalpha()):
            raise VokoValidationError('The email postcode does not seem to be valid (should be NNNNLL, where N=number and L=letter).')
        # check house no
        if not self.mem_house.isdigit():
            raise VokoValidationError('House number should just be a number.')
        # check bank no
        bank_no_clean = self.mem_bank_no.replace(' ', '').replace('-', '')
        if len(bank_no_clean) < 7 or len(bank_no_clean) > 9:
            raise VokoValidationError('Bank number needs to consist of 7 (postbank) or 9 numbers.')
        if not bank_no_clean.isdigit():
            raise VokoValidationError('Bank number needs to consist of only numbers.')
        # at least one telephone number
        ks = self.__dict__.keys()
        if (not 'mem_home_tel' in ks and not 'mem_work_tel' in ks and not 'mem_mobile' in ks) or\
           (self.mem_home_tel == "" and self.mem_work_tel == "" and self.mem_mobile == ""):
            raise VokoValidationError('Please specify at least one telephone number.')

    def validate_pwd(self, req):
        '''
        Check request on password(s), and also check if it is long enough
        '''
        if not req.params.has_key('pwd1'):
            raise VokoValidationError('Please specify a password.')
        if not req.params.has_key('pwd2'):
            raise VokoValidationError('Please confirm password.')
        if not req.params['pwd2'] == req.params['pwd1']:
            raise VokoValidationError('Passwords do not match.')
        if not 6 <= len(req.params['pwd1']) <= 30:
            raise VokoValidationError('The password should be between 6 and 30 characters long.')


