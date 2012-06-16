from sqlalchemy import Column, Integer, Unicode, Boolean, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.schema import UniqueConstraint

from base import Base, VokoValidationError
from member import Member
from workgroups import Workgroup


reoccuring_modes = ['once', 'weekly', 'bi-monthly', 'monthly']

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
    num_people = Column(Integer, default=1)

    workgroup = relationship(Workgroup,
                  backref=backref('tasks', cascade='all,delete,delete-orphan',
                                           order_by='Task.id'))

    # no task can exist twice within one group
    __table_args__ = (UniqueConstraint('label', 'wg_id'), {})

    def __init__(self, label, wg_id, num_people=1):
        self.label = label
        self.wg_id = wg_id
        self.active = True
        self.num_people = num_people

    def __repr__(self):
        return self.label

    def validate(self, tasks):
        '''
        validate if this object is valid, raise VokoValidationError otherwise
        '''
        if self.label == '':
            raise VokoValidationError('A task needs a label.')
        if self.num_people < 1:
            raise VokoValidationError('A task needs at least one person.')
        for task in [t for t in tasks if not t.id == self.id]:
            if task.label == self.label:
                raise VokoValidationError('This workgroup already has a task '\
                                    'with the label "{}".'.format(self.label))
