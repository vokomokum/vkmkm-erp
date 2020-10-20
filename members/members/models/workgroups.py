import re

from sqlalchemy import Table, Column, Integer, Unicode, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from pyramid.security import Allow, DENY_ALL

from members.models.base import Base, VokoValidationError
from members.models.member import Member


membership = Table(
    'wg_membership', Base.metadata,
    Column('wg_id', Integer, ForeignKey('workgroups.id')),
    Column('mem_id', Integer, ForeignKey('members.mem_id'))
    )

leadership = Table(
    'wg_leadership', Base.metadata,
    Column('wg_id', Integer, ForeignKey('workgroups.id')),
    Column('mem_id', Integer, ForeignKey('members.mem_id'))
    )


class Workgroup(Base):
    __tablename__ = 'workgroups'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode(255), unique=True)
    desc = Column(Unicode(255))
    required_members = Column(Integer, default=1)
    active = Column(Boolean(), default=True)

    __acl__ = [(Allow, 'group:admins', ('view', 'edit')),
               (Allow, 'group:wg-leaders', ('view', 'edit')),
               (Allow, 'group:wg-members', 'view'),
               (Allow, 'group:members', 'view'),
               DENY_ALL]

    def __init__(self, request=None, name='', desc='', required_members=1):
        ''' receiving request makes this class a factory for views '''
        self.exists = False
        self.name = name
        self.desc = desc
        self.active = True
        self.required_members = int(required_members)

    def __repr__(self):
        return self.name

    @property
    def main_mailing_list_address(self):
        ''' return the email address that reaches coordinators '''
        return "{}@vokomokum.nl".format(self._mkaddress())
     
    @property
    def all_mailing_list_address(self):
        ''' return the email address that reaches all members of this group '''
        return "{}-all@vokomokum.nl".format(self._mkaddress())

    def _mkaddress(self):
        name = self.name.strip()
        name = re.sub(r'\s+', '-', name)
        name = re.sub(r'[\'"@,:;]', "", name)
        return name.lower()


    def validate(self):
        ''' validate if this object is valid, raise exception otherwise '''
        if self.name == '':
            raise VokoValidationError('A workgroup needs a name.')
        if self.desc == '':
            raise VokoValidationError('A workgroup needs a description.')
        if len(self.leaders) == 0:
            raise VokoValidationError('A workgroup needs at least '\
                                      'one coordinator.')
        if int(self.required_members) < 1:
            raise VokoValidationError('A workgroup needs at least one member.')

    @property
    def headcount(self):
        return len(self.active_members)

    @property
    def active_members(self):
        return [m for m in self.members if m.mem_active]

    @property
    def active_leaders(self):
        return [m for m in self.leaders if m.mem_active]


Workgroup.members = relationship('Member', secondary=membership)
Member.workgroups = relationship('Workgroup', secondary=membership)
Workgroup.leaders = relationship('Member', secondary=leadership)
Member.led_workgroups = relationship('Workgroup', secondary=leadership)


def get_wg(session, request):
    ''' make a Workgroup object, use ID from request if possible '''
    wg = Workgroup('', '')
    if 'wg_id' in request.matchdict:
        wg_id = request.matchdict['wg_id']
        if wg_id == 'new':
            return wg
        try:
            wg_id = int(wg_id)
        except ValueError:
            raise Exception("No workgroup with ID %s" % wg_id)
        wg = session.query(Workgroup).get(wg_id)
        if wg:
            wg.exists = True
        else:
            raise Exception("No workgroup with ID %s" % wg_id)
    return wg
