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

from setup import Base


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
