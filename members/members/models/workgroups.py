from sqlalchemy import Table, Column, Integer, Unicode, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey

from pyramid.security import Allow, DENY_ALL

from setup import Base, VokoValidationError
from member import Member


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

    __acl__ = [ (Allow, 'group:admins', ('view', 'edit')),
                (Allow, 'group:wg-leaders', ('view', 'edit')),
                (Allow, 'group:wg-members', 'view'), DENY_ALL ]

    def __init__(self, request=None, name='', desc=''):
        ''' receiving request makes this class a factory for views '''
        self.exists = False
        self.name = name
        self.desc = desc

    def __repr__(self):
        return self.name

    def set_leader(self, leader_id):
        self.leader_id = leader_id

    def validate(self):
        ''' validate if this object is valid, raise exception otherwise '''
        if self.name == '':
            raise VokoValidationError('A workgroup needs a name.')
        if self.desc == '':
            raise VokoValidationError('A workgroup needs a description.')
        if len(self.leaders) == 0:
            raise VokoValidationError('A workgroup needs at least one coordinator.')


Workgroup.members = relationship('Member', secondary=membership)
Member.workgroups = relationship('Workgroup', secondary=membership)
Workgroup.leaders = relationship('Member', secondary=leadership)
Member.led_workgroups = relationship('Workgroup', secondary=leadership)
