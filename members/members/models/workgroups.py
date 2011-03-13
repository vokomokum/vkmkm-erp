from sqlalchemy import Table, Column, Integer, Unicode, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey

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
    leader_id = Column(Integer)

    def __init__(self, name, desc):
        self.name = name
        self.desc = desc
        self.exists = False

    def __repr__(self):
        return str(self.id)

    def set_leader(self, leader_id):
        self.leader_id = leader_id

Workgroup.members = relationship('Member', secondary=membership)
Member.workgroups = relationship('Workgroup', secondary=membership)
