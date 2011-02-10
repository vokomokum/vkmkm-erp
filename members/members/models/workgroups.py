from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Unicode
from sqlalchemy import Boolean

from setup import Base


class Workgroup(Base):
    __tablename__ = 'workgroups'
    
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(255))
    desc = Column(Unicode(255))
    leader_id = Column(Integer)
    active = Column(Boolean, default=False)

    def __init__(self, name, desc):
        self.name = name
        self.desc = desc

    def __repr__(self):
        return self.name

    def set_leader(self, leader_id):
        self.leader_id = leader_id


class Membership(Base):
    __tablename__ = 'wg_membership'
    
    id = Column(Integer, primary_key=True)
    wg_id = Column(Integer)
    mem_id = Column(Integer)
    #active = Column(Boolean)

    def __init__(self, wg_id, mem_id):
        self.wg_id = wg_id
        self.mem_id = mem_id


