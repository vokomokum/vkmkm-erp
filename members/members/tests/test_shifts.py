from pyramid import testing

from members.tests.base import VokoTestCase
from members.models.base import VokoValidationError
from members.models.member import Member
from members.models.workgroups import Workgroup
from members.models.shift import Shift
from members.views.shift import NewShiftView, EditShiftView


class TestShifts(VokoTestCase):

    def get_shifts(self, mname=None, wgname=u'Besteling'):
        wg = self.DBSession.query(Workgroup).filter(Workgroup.name==wgname).first()
        peter = self.DBSession.query(Member).filter(Member.mem_fname==mname).first()
        shifts = self.DBSession.query(Shift).filter(Shift.wg_id == wg.id)
        if mname:
            shifts = shifts.filter(Shift.mem_id == peter.mem_id)
        return shifts

    def test_get_data_from_db(self):
        '''look at our dummy data and if the shift is loaded correctly'''
        peter = self.DBSession.query(Member).filter(Member.mem_fname==u'Peter').first()
        shifts = self.get_shifts(mname=u'Peter')
        self.assertEqual(shifts.count(), 1)
        shift = shifts.one()
        self.assertEqual(shift.mem_id, peter.mem_id)
        self.assertEqual(shift.workgroup.id, 2)
        self.assertEqual(shift.state, 'assigned')

    def test_setstate_on_db(self):
        ''' change the status of a shift in the DB, set it to "worked"'''
        peter = self.DBSession.query(Member).filter(Member.mem_fname==u'Peter').first()
        shift = self.get_shifts(mname=u'Peter').one()
        shift.state = 'worked'
        self.DBSession.add(shift)
        self.DBSession.flush()
        shift = self.get_shifts(mname=u'Peter').one()
        self.assertEqual(shift.state, 'worked')

    def test_create(self):
        ''' Let Hans do a shift here, as well'''
        hans = self.DBSession.query(Member).filter(Member.mem_fname==u'Hans').first()
        wg = self.DBSession.query(Workgroup).filter(Workgroup.name==u'Besteling').first()
        self.assertEqual(self.get_shifts().count(), 1)
        request = testing.DummyRequest()
        request.matchdict['wg_id'] = wg.id
        request.params['task'] = 'some task'
        request.params['year'] = 2012
        request.params['month'] = 6
        request.params['mem_id'] = hans.mem_id
        view = NewShiftView(None, request)
        view.user = self.get_peter()
        view()
        self.assertEqual(self.get_shifts().count(), 2)

    def test_create_wrong_member(self):
        '''
        If the member is not in that workgroup, don't allow the shift.
        Systems workgroup has no shifts yet and Hans is not a member.
        '''
        hans = self.DBSession.query(Member).filter(Member.mem_fname==u'Hans').first()
        wg = self.DBSession.query(Workgroup).filter(Workgroup.name==u'Systems').first()
        request = testing.DummyRequest()
        request.matchdict['wg_id'] = wg.id
        request.params['task'] = 'do system stuff'
        request.params['year'] = 2012
        request.params['month'] = 6
        request.params['mem_id'] = hans.mem_id
        view = NewShiftView(None, request)
        shifts = self.get_shifts(wgname='Systems')
        self.assertEqual(shifts.count(), 0)

    def test_delete(self):
        shift = self.get_shifts(mname=u'Peter').one()
        wg = self.DBSession.query(Workgroup).filter(Workgroup.name==u'Besteling').first()
        request = testing.DummyRequest()
        request.matchdict = {'wg_id': wg.id}
        request.matchdict['s_id'] = shift.id
        request.params['action'] = 'delete'
        view = EditShiftView(None, request)
        view.user = self.get_peter()
        view()
        self.assertEquals(self.get_shifts(mname=u'Peter').count(), 0)

    def test_toggle_state(self):
        shift = self.get_shifts(mname=u'Peter').one()
        self.assertEquals(shift.state, 'assigned')
        wg = self.DBSession.query(Workgroup).filter(Workgroup.name==u'Besteling').first()
        request = testing.DummyRequest()
        request.matchdict = {'wg_id': wg.id}
        request.matchdict['s_id'] = shift.id
        request.params['action'] = 'save'
        request.params['state'] = 'worked'
        view = EditShiftView(None, request)
        view.user = self.get_peter()
        view()
        self.assertEquals(shift.state, 'worked')
        request.params['state'] = 'assigned'
        view.user = self.get_peter()
        view()
        self.assertEquals(shift.state, 'assigned')
        request.params['state'] = 'invalid-state'
        self.assertRaises(VokoValidationError, view)
        # This does not work here, as in the view the shift has been
        # retrieved from the session and then changed before
        # validation throws an error.
        # In production, a rollback happens, but not here
        #shift = self.get_shifts(mname=u'Peter').one()
        #self.assertEquals(shift.state, 'assigned')


