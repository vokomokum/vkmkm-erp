from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Unicode
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, backref

from datetime import datetime

from base import Base
from base import DBSession
from base import VokoValidationError
from member import Member
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
    wg_id = Column(Integer, ForeignKey('workgroups.id'), nullable=False)
    mem_id = Column(Integer, ForeignKey('members.mem_id'), nullable=True)
    state = Column(Unicode(255), default=u'open')
    task = Column(Unicode(255), default=u'')
    day = Column(Unicode(255), nullable=True)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)

    workgroup = relationship(Workgroup,
                  backref=backref('shifts', cascade='all,delete,delete-orphan',
                                           order_by='Shift.id'))
    member = relationship(Member, backref='scheduled_shifts')

    def __init__(self, wg_id, task, year, month, day=None, mem_id=None):
        self.mem_id = mem_id
        self.wg_id = wg_id
        self.task = task
        if mem_id:
            self.state = 'assigned'
        else:
            self.state = 'open'
        self.day = day
        self.month = month
        self.year = year

    def __repr__(self):
        return "Shift - workgroup '%s' on '%s-%d-%d', by member %s"\
               " in the '%s'-group [state is %s]" %\
                (str(self.workgroup), str(self.day), self.month, self.year, self.member.fullname,
                 self.workgroup, self.state)

    def clone(self):
        return Shift(self.wg_id, self.task, self.year, self.month,
                  self.day, self.mem_id)

    @property
    def is_locked(self):
        '''
        Only the wg leader can sign off a member from a locked shift
        TODO: now all shifts w/o a (numeric) day are locked 1 week before the
              month starts, probably we want to change that, but need to discuss
        '''
        day = self.day
        if not self.day or not str(self.day).isdigit():
            day = 1
        now = datetime.now()
        sdate = datetime(self.year, self.month, int(day))
        return self.day and (sdate - now).days < 7

    def validate(self):
        '''
        validate if this object is valid, raise VokoValidationError otherwise
        '''
        tmp_day = self.day
        if not self.day or not str(self.day).isdigit():
            tmp_day = 1
        try:
            datetime(self.year, self.month, int(tmp_day))
        except ValueError, e:
            raise VokoValidationError('The date of this shift is not correct: %s.' % e)
        if self.task == "":
            raise VokoValidationError('The task should not be empty.')
        if self.state in ['assigned', 'worked', 'no-show']:
            if not self.mem_id or self.mem_id == '--':
                raise VokoValidationError('Please select a member. We need to know a member for state "{}".'.format(self.state))
            m = DBSession.query(Member).get(self.mem_id)
            if not m:
                raise VokoValidationError('No member could be found for this ID.')
            if not m in self.workgroup.members:
                raise VokoValidationError('The member of this shift (%s) is not '\
                        'a member in the workgroup %s.' % (m, self.workgroup))
        if not self.state in shift_states:
            raise VokoValidationError('The state must be either "open", "assigned", '\
                        '"worked" or "no-show". Cannot set it to %s' % (self.state))


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
