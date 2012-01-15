from sqlalchemy import Column, Integer, Unicode, Boolean, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.schema import UniqueConstraint

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
    label = Column(Unicode(255), unique=True)
    wg_id = Column(Integer, ForeignKey('workgroups.id'), nullable=False)
    active = Column(Boolean(), default=True)

    workgroup = relationship(Workgroup, backref=backref('tasks', cascade='all,delete,delete-orphan'))

    # no task can exist twice within one group
    __table_args__ = (UniqueConstraint('label', 'wg_id'), {})

    def __init__(self, label, wg_id):
        self.label = label
        self.wg_id = wg_id

    def __repr__(self):
        return self.label

    def validate(self):
        ''' validate if this object is valid, raise exception otherwise '''
        if self.label == '':
            raise Exception('A task needs a label.')


