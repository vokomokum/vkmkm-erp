from sqlalchemy import Column, Integer, Unicode, ForeignKey
from sqlalchemy.orm import relationship

from setup import Base
from member import Member
from task import Task
from workgroups import Workgroup
from others import get_order_label


class Shift(Base):
    '''
    A shift is not identifiable by any number of its attributes, as
    anyone can do more than one shift in the same workgroup in the
    order period. This is why they have their own id.
    '''
    __tablename__ = 'wg_shifts'

    id = Column(Integer, primary_key=True)
    wg_id = Column(Integer, ForeignKey('workgroups.id'), nullable=False)
    mem_id = Column(Integer, ForeignKey('members.mem_id'), nullable=False)
    order_id = Column(Integer, nullable=False)
    task_id = Column(Integer, ForeignKey('wg_tasks.id'), nullable=False)
    state = Column(Unicode(255), default=u'assigned')

    member = relationship(Member, backref='scheduled_shifts')
    workgroup = relationship(Workgroup)
    task = relationship(Task)

    def __init__(self, wg_id, mem_id, o_id, t_id):
        self.wg_id = wg_id
        self.mem_id = mem_id
        self.order_id = o_id
        self.task_id = t_id

    def __repr__(self):
        return "Shift - task '%s' in order '%d' by member %s in the '%s'-group [state is %s]" %\
                (str(self.task), self.order_id, self.member.fullname(), self.workgroup, self.state)

    def set_state(self, state):
        assert(state in ['assigned', 'worked'])
        self.state = state

    @property
    def order(self):
        return get_order_label(self.order_id)

