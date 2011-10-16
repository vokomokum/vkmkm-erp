from sqlalchemy import Column, Integer, Unicode, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from setup import Base
from member import Member
from workgroups import Workgroup


class Task(Base):
    '''
    A task is a label for some job.
    Each group can identify some labels they want to use.
    '''
    __tablename__ = 'wg_tasks'

    id = Column(Integer, primary_key=True)
    label = Column(Unicode(255))
    wg_id = Column(Integer, ForeignKey('workgroups.id'), nullable=False)
    active = Column(Boolean(), default=True)

    workgroup = relationship(Workgroup, backref='tasks')


    def __init__(self, label, wg_id):
        self.label = label
        self.wg_id = wg_id

    def __repr__(self):
        return self.label


