from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Unicode

from setup import Base


class Shift(Base):
    __tablename__ = 'wg_shifts'
    year = Column(Integer)
    month = Column(Integer)
    day = Column(Integer)
    wg_id = Column(Integer)
    mem_id = Column(Integer)
    state = Column(Unicode(255))

    def __init__(self, year, month, day, wg_id, mem_id):
        self.year = year
        self.month = month
        self.day = day
        self.wg_id = wg_id
        self.mem_id = mem_id

    def set_state(self, state):
        assert(state in ['assigned', 'worked'])
        self.state = state

