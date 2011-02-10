from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Unicode

from setup import Base


class Shift(Base):
    __tablename__ = 'wg_shifts'
    
    id = Column(Integer, primary_key=True)
    year = Column(Integer)
    month = Column(Integer)
    day = Column(Integer)
    wg_id = Column(Integer)
    mem_id = Column(Integer)
    state = Column(Unicode(255), default='assigned')

    def __init__(self, wg_id, mem_id, year, month):
        self.year = year
        self.month = month
        self.wg_id = wg_id
        self.mem_id = mem_id

    def __repr__(self):
        return "%d/%d/%d member: %d, group: %d, state: %s" %\
                (self.year, self.month, self.day, self.mem_id, self.wg_id, self.state)

    def set_day(self, day):
        self.day = day

    def set_state(self, state):
        assert(state in ['assigned', 'worked'])
        self.state = state

