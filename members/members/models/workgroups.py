from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Unicode
from sqlalchemy import Boolean

from setup import Base


class Workgroup(Base):
    __tablename__ = 'workgroups'
    wg_id = Column(Integer, primary_key=True)
    wg_name = Column(Unicode(255))
    wg_desc = Column(Unicode(255))
    leader_id = Column(Integer)
    active = Column(Boolean)

    def __init__(self, gname, leader_id, desc):
        self.wg_name = gname
        self.wg_desc = desc
        self.leader_id = leader_id


class Membership(Base):
    __tablename__ = 'wg_membership'
    wg_id = Column(Integer, primary_key=True)
    mem_id = Column(Integer)
    #active = Column(Boolean)

    def __init__(self, wg_id. mem_id):
        self.wg_id = wg_id
        self.mem_id = mem_id


