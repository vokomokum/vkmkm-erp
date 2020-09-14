'''
member
=========

The member class.
Describes all attributes of the database we need here.
'''
from __future__ import unicode_literals
import re
import dns.resolver

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Unicode
from sqlalchemy import Boolean

from pyramid.security import Allow, DENY_ALL

from members.models.base import Base, VokoValidationError
from members.models.base import DBSession


class Member(Base):
    '''
    Data model
    '''
    __tablename__ = 'members'

    mem_id = Column(Integer, primary_key=True)
    mem_fname = Column(Unicode(255), default='')
    mem_prefix = Column(Unicode(255), default='')
    mem_lname = Column(Unicode(255), default='')
    mem_email = Column(Unicode(255), default='')
    mem_street = Column(Unicode(255), default='')
    mem_house = Column(Integer, default=0)
    mem_flatno = Column(Unicode(255), default='')
    mem_city = Column(Unicode(255), default='')
    mem_postcode = Column(Unicode(6), default='')
    mem_home_tel = Column(Unicode(25), default='')
    mem_work_tel = Column(Unicode(255), default='')
    mem_mobile = Column(Unicode(25), default='')
    mem_enc_pwd = Column(Unicode(255), default='')
    mem_pwd_url = Column(Unicode(255), default='')
    # tracking
    mem_cookie = Column(Unicode(255), default='')
    mem_ip = Column(Unicode(255), default='')
    # admin-editable
    mem_active = Column(Boolean(), default=True)
    mem_membership_paid = Column(Boolean(), default=False)
    mem_admin = Column(Boolean(), default=False)
    mem_adm_adj = Column(Boolean(), default=False)
    mem_adm_comment = Column(Unicode(255), default='')
    # unused fields - TODO: do we need them?
    mem_bank_no = Column(Unicode(255), default='')
    mem_household_size = Column(Integer, default=0)

    __acl__ = [(Allow, 'group:admins', ('view', 'edit')),
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
        return self.fullname

    @property
    def fullname(self):
        return "{} {} {}".format(self.mem_fname or '',
                                 self.mem_prefix or '',
                                 self.mem_lname or '')

    def addr_street(self):
        return "{} {}{}".format(self.mem_street, self.mem_house,
                                self.mem_flatno)

    def addr_city(self):
        return "{} {}".format(self.mem_postcode, self.mem_city)

    def validate(self):
        ''' checks on address, bank account, ...
        '''
        # check missing fields
        missing = []
        for f in ('mem_fname', 'mem_lname', 'mem_email'):
            if not f in self.__dict__ or self.__dict__[f] == '':
                missing.append(f)
        if len(missing) > 0:
            raise VokoValidationError('We still require you to fill in: %s'\
                                    % ', '.join([m[4:] for m in missing]))
        self.validate_email()
        # also check unique constraint on email address here for nicer error msg
        session = DBSession()
        members = session.query(Member)\
                         .filter(Member.mem_email == self.mem_email).all()
        if len(members) > 0:
            if not (len(members) == 1 and members[0].mem_id == self.mem_id):
                raise VokoValidationError('The email address already exists '\
                                          'for a member in the database.')

        # we want one telephone number, as well
        sd = self.__dict__
        if ((not 'mem_home_tel' in sd and not 'mem_work_tel' in sd
             and not 'mem_mobile' in sd)
           or (self.mem_home_tel == "" and self.mem_work_tel == ""
               and self.mem_mobile == "")):
            raise VokoValidationError('Please specify at least one telephone '\
                                      'number.')

        # check postcode
        if self.mem_postcode and len(self.mem_postcode) > 0\
                and not (self.mem_postcode[:4].isdigit()\
                and self.mem_postcode[-2:].isalpha()):
            raise VokoValidationError('The postcode does not seem to be'\
                    ' valid (should be NNNNLL, where N=number and L=letter).')
        # check bank no
        if self.mem_bank_no:
            bank_no_clean = self.mem_bank_no.replace(' ', '').replace('-', '')
            if not len(bank_no_clean) in [0, 7, 8, 9]:
                # length of 8 is legacy data
                raise VokoValidationError('Bank number needs to consist of 7 '\
                                          '(postbank) or 9 numbers.')
            if len(bank_no_clean) > 0 and not bank_no_clean.isdigit():
                raise VokoValidationError('Bank number needs to consist of '\
                                          'only numbers.')
        # household size
        if self.mem_household_size is None or self.mem_household_size < 1:
            raise VokoValidationError('Please specify how many people live '\
                                      'in the household.')

    def validate_email(self):
        ''' check email '''
        # check general form: a valid local name + @ + some host
        # (for local name, see http://en.wikipedia.org/wiki/Email_address#Local_part)
        if not re.match('[A-Za-z0-9\-\_\.\+\$\%\#\&\*\/\=\?\{\}\|\~]+@[^@]+',
                        self.mem_email): 
            raise VokoValidationError('The email address does not '\
                                      'seem to be valid.')
        # check host
        host = re.findall('[^@]+', self.mem_email)[1]
        try:
            # dns.resolver throws an exception when it can't find a mail (MX)
            # host. The point at the end makes it not try to append domains
            _ = dns.resolver.query('{}.'.format(host), 'MX')
        except:
            raise VokoValidationError('The host {} is not known in the DNS'\
                                      ' system as a mail server.'\
                                      ' Is it spelled correctly?'.format(host))


    def validate_pwd(self, req):
        '''
        Check request on password(s), and also check if it is long enough
        '''
        if not 'pwd1' in req.params:
            raise VokoValidationError('Please specify a password.')
        if not 'pwd2' in req.params:
            raise VokoValidationError('Please confirm password.')
        if not req.params['pwd2'] == req.params['pwd1']:
            raise VokoValidationError('Passwords do not match.')
        if not 6 <= len(req.params['pwd1']) <= 30:
            raise VokoValidationError('The password should be between '\
                                 '6 and 30 characters long.')

    @property
    def balance(self):
        ''' returns the account balance'''
        balance = 0
        for t in self.transactions:
            balance += t.amount
        return balance


def get_member(session, request):
    '''
    Make a Member object, use member ID from request if possible.
    Will return an empty object when no information is in the request.
    '''
    member = Member(fname=u'', prefix=u'', lname=u'')
    m_id = None
    if 'mem_id' in request.matchdict:
        m_id = request.matchdict['mem_id']
    if 'mem_id' in request.params:
        m_id = request.params['mem_id']
    if m_id:
        if m_id == 'new':
            return member
        try:
            m_id = int(m_id)
        except ValueError:
            raise Exception("No member with ID {0}".format(m_id))
        member = session.query(Member).get(m_id)
        if member:
            member.exists = True
        else:
            raise Exception("No member with ID {0}".format(m_id))
    return member
