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

from setup import Base


class Member(Base):
    '''
    Data model
    '''
    __tablename__ = 'members'

    id = Column(Integer, primary_key=True)
    mem_fname = Column(Unicode(255))
    mem_prefix = Column(Unicode(255))
    mem_lname = Column(Unicode(255))
    mem_email = Column(Unicode(255))
    mem_street =  Column(Unicode(255))
    mem_house = Column(Unicode(255))
    mem_flatno = Column(Unicode(255))
    mem_city = Column(Unicode(255))
    mem_postcode = Column(Unicode(6))
    mem_home_tel = Column(Unicode(25))
    mem_work_tel = Column(Unicode(255))
    mem_mobile = Column(Unicode(25))
    mem_bank_no = Column(Unicode(255))
    mem_enc_pwd = Column(Unicode(255))
    mem_pwd_url = Column(Unicode(255))
    mem_cookie = Column(Unicode(255))
    mem_ip = Column(Unicode(255))
    mem_active = Column(Boolean())
    mem_membership_paid = Column(Boolean())
    mem_admin = Column(Boolean())
    mem_adm_adj = Column(Boolean())
    #mem_adm_comment = Column(Unicode(255))
    #mem_message = Column(Unicode(255))
    #mem_news = Column(Unicode(255))
    #mem_message_auth = Column(Integer())
    #mem_message_date = Column(DateTime()) #timestamp


    def __init__(self, fname, prefix, lname):
        self.mem_fname = fname
        self.mem_prefix = prefix
        self.mem_lname = lname
        self.mem_active = True
        self.exists = False

    def __repr__(self):
        return self.fullname()

    def fullname(self):
        return "%s %s %s" % (self.mem_fname, self.mem_prefix, self.mem_lname)

    def addr_street(self):
        return "%s %s%s" % (self.mem_street, self.mem_house, self.mem_flatno)

    def addr_city(self):
        return "%s %s" % (self.mem_postcode, self.mem_city)
