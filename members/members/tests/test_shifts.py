from members.tests.base import VokoTestCase
from members.models.member import Member
from members.models.shift import Shift


class TestShifts(VokoTestCase):

    def get_shifts_by_member(self, m):
        return self.DBSession.query(Shift)\
                      .filter(Shift.mem_id == m.mem_id)

    def test_getdata(self):
        '''look at our dummy data and if the shift is loaded correctly'''
        peter = self.DBSession.query(Member).filter(Member.mem_fname==u'Peter').first()
        shifts = self.get_shifts_by_member(peter)
        self.assertEqual(shifts.count(), 1)
        shift = shifts.one()
        self.assertEqual(shift.mem_id, peter.mem_id)
        self.assertEqual(shift.wg_id, 2)
        self.assertEqual(shift.state, 'assigned')

    def test_setstatus(self):
        ''' change the status of a shift in the DB, set it to "worked"'''
        peter = self.DBSession.query(Member).filter(Member.mem_fname==u'Peter').first()
        shifts = self.get_shifts_by_member(peter)
        shift = shifts.one()
        shift.set_state('worked')
        self.DBSession.add(shift)
        self.DBSession.flush()
        shifts = self.get_shifts_by_member(peter)
        shift = shifts.one()
        self.assertEqual(shift.state, 'worked')


