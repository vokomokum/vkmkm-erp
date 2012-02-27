from pyramid import testing

from sqlalchemy.exc import InvalidRequestError

from members.tests.base import VokoTestCase
from members.views.workgroup import WorkgroupView, WorkgrouplistView, WorkgroupEditView
from members.models.workgroups import Workgroup
from members.models.member import Member


class TestWorkgroups(VokoTestCase):

    def test_getquery(self):
        wgs = self.DBSession.query(Workgroup).order_by(Workgroup.name).all()
        self.assertEqual(len(wgs), 2)
        self.assertEqual(wgs[0].name, 'Besteling')
        self.assertEqual(wgs[1].name, 'Systems')

    def test_membership(self):
        s = self.DBSession
        peter = s.query(Member).filter(Member.mem_fname==u'Peter').first()
        hans = s.query(Member).filter(Member.mem_fname==u'Hans').first()
        wg_systems = s.query(Workgroup).filter(Workgroup.name==u'Systems').first()
        wg_bestel = s.query(Workgroup).filter(Workgroup.name==u'Besteling').first()
        self.failUnless(peter.mem_id in [m.mem_id for m in wg_systems.members])
        self.failUnless(peter in wg_bestel.members)
        self.failUnless(hans in wg_bestel.members)

    def test_view(self):
        request = testing.DummyRequest()
        request.matchdict = {'wg_id': 2}
        view_info = WorkgroupView(None, request)()
        self.assertEqual(view_info['wg'].id, 2)

    def test_view_noexist(self):
        request = testing.DummyRequest()
        request.matchdict = {'wg_id': 3}
        self.assertRaises(Exception, WorkgroupView(None, request))

    def test_list(self):
        ''' simple test of list view '''
        request = testing.DummyRequest()
        view_info = WorkgrouplistView(None, request)()
        self.assertEqual([wg.id for wg in view_info['workgroups']], [1,2])
        self.assertEqual(view_info['order_name_choice'], 'desc')
        # change ordering
        request.params['order_dir'] = 'desc'
        view_info = WorkgrouplistView(None, request)()
        self.assertEqual([wg.id for wg in view_info['workgroups']], [2,1])
        self.assertEqual(view_info['order_name_choice'], 'asc')

    def test_edit(self):
        ''' edit the name '''
        request = testing.DummyRequest()
        request.matchdict = {'wg_id': 2}
        request.params['name'] = 'Wholesale Besteling'
        request.params['action'] = 'save'
        view_info = WorkgroupEditView(None, request)()
        wg_bestel = self.DBSession.query(Workgroup).get(2)
        self.assertEqual(wg_bestel.name, 'Wholesale Besteling')

    def test_invalid(self):
        ''' giving no name: invalid'''
        request = testing.DummyRequest()
        request.matchdict = {'wg_id': 2}
        request.params['name'] = ''
        request.params['action'] = 'save'
        self.assertRaises(Exception, WorkgroupEditView(None, request))

    def test_invalid_edit_noleader(self):
        request = testing.DummyRequest()
        request.matchdict = {'wg_id': 2}
        request.params['wg_leaders'] = []
        request.params['action'] = 'save'
        self.assertRaises(Exception, WorkgroupEditView(None, request))

    def test_delete(self):
        request = testing.DummyRequest()
        def get_sys_wg():
            return self.DBSession.query(Workgroup).filter(Workgroup.name==u'Systems').first()
        wg_system = get_sys_wg()
        request.matchdict = {'wg_id': wg_system.id}
        request.params['action'] = 'delete'
        view = WorkgroupEditView(None, request)
        view()
        self.assertTrue(view.confirm_deletion)
        request.params['action'] = 'delete-confirmed'
        # an invalid request error is thrown when attempting to delete
        # (object can't be deleted, this test has no persistent state), 
        # thus deletion was attempted. Fine.
        #self.assertRaises(InvalidRequestError, view)
        view()
        self.assertIsNone(get_sys_wg())

    def test_delete_withshift(self):
        ''' no delete possible when shift exists '''
        request = testing.DummyRequest()
        wg_bestel = self.DBSession.query(Workgroup).filter(Workgroup.name==u'Besteling').first()
        request.matchdict = {'wg_id': wg_bestel.id}
        request.params['action'] = 'delete'
        view = WorkgroupEditView(None, request)
        view()
        self.assertTrue(view.confirm_deletion)
        request.params['action'] = 'delete-confirmed'
        ex = None
        try:
            view()
        except Exception, e:
            ex = e
        self.assertIn('there are shifts', str(ex))

