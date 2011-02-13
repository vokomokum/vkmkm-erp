from sqlalchemy import Column, Integer, Unicode, ForeignKey 

from setup import Base


class Shift(Base):
    __tablename__ = 'wg_shifts'
    
    id = Column(Integer, primary_key=True)
    year = Column(Integer)
    month = Column(Integer)
    day = Column(Integer)
    wg_id = Column(Integer, ForeignKey('workgroups.id'))
    mem_id = Column(Integer, ForeignKey('members.id'))
    state = Column(Unicode(255), default='assigned')

    def __init__(self, wg_id, mem_id, year, month):
        self.year = year
        self.month = month
        self.wg_id = wg_id
        self.mem_id = mem_id

    def __repr__(self):
        return "%d/%d/%s member: %d, group: %d, state: %s" %\
                (self.year, self.month, str(self.day), self.mem_id, self.wg_id, self.state)

    def set_day(self, day):
        assert(day in xrange(1, 25, 1))
        self.day = day

    def set_state(self, state):
        assert(state in ['assigned', 'worked'])
        self.state = state

