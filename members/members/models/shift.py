from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Unicode
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from datetime import datetime

from base import Base
from base import DBSession
from base import VokoValidationError
from member import Member
from task import Task
from workgroups import Workgroup


shift_states = ['open', 'assigned', 'worked' ,'no-show']

class Shift(Base):
    '''
    A shift is not identifiable by any number of its attributes, as
    anyone can do more than one shift in the same workgroup in the
    order period. This is why they have their own id.
    '''
    __tablename__ = 'wg_shifts'

    id = Column(Integer, primary_key=True)
    mem_id = Column(Integer, ForeignKey('members.mem_id'), nullable=True)
    task_id = Column(Integer, ForeignKey('wg_tasks.id'), nullable=True)
    state = Column(Unicode(255), default=u'open')
    day = Column(Integer, nullable=True)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)

    member = relationship(Member, backref='scheduled_shifts')
    task = relationship(Task)

    def __init__(self, t_id, year, month, day=None, mem_id=None):
        self.mem_id = mem_id
        self.task_id = t_id
        if mem_id:
            self.state = 'assigned'
        else:
            self.state = 'open'
        self.day = day
        self.month = month
        self.year = year

    def __repr__(self):
        return "Shift - task '%s' on '%d-%d-%d', by member %s"\
               " in the '%s'-group [state is %s]" %\
                (str(self.task), str(self.day), self.month, self.year, self.member.fullname,
                 self.workgroup, self.state)

    def validate(self):
        '''
        validate if this object is valid, raise VokoValidationError otherwise
        '''
        tmp_day = self.day or 1
        try:
            datetime(self.year, self.month, tmp_day)
        except ValueError, e:
            raise VokoValidationError('The date of this shift is not correct: %s.' % e)
        if self.state in ['assigned', 'worked', 'no-show']:
            if self.mem_id == '--':
                raise VokoValidationError('Please select a member.')
            m = DBSession.query(Member).get(self.mem_id)
            if not m:
                raise VokoValidationError('No member specified.')
            task = DBSession.query(Task).get(self.task_id)
            if not m in task.workgroup.members:
                raise VokoValidationError('The member of this shift (%s) is not '\
                        'a member in the workgroup %s.' % (m, task.workgroup))
        if not self.state in shift_states:
            raise VokoValidationError('The state must be either "open", "assigned", '\
                        '"worked" or "no-show". Cannot set it to %s' % (self.state))

    @property
    def workgroup(self):
        return self.task.workgroup


def get_shift(session, request):
    ''' get shift object from id '''
    if (request and 's_id' in request.matchdict
         and int(request.matchdict['s_id']) >= 0):
            shift = session.query(Shift).get(request.matchdict['s_id'])
            if shift:
                shift.exists = True
    else:
        shift = None
    return shift
