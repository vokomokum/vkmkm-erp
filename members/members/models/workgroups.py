from sqlalchemy import Table, Column, Integer, Unicode, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey

from pyramid.security import Allow, DENY_ALL

from setup import Base
from member import Member


membership = Table(
    'wg_membership', Base.metadata,
    Column('wg_id', Integer, ForeignKey('workgroups.id')),
    Column('mem_id', Integer, ForeignKey('members.id'))
    )


class Workgroup(Base):
    __tablename__ = 'workgroups'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode(255))
    desc = Column(Unicode(255))
    leader_id = Column('leader_id', Integer, ForeignKey('members.id'))

    leader = relationship(Member, backref='led_wgs')

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

Workgroup.members = relationship('Member', secondary=membership)
Member.workgroups = relationship('Workgroup', secondary=membership)
