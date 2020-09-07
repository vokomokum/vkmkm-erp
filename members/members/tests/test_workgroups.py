from pyramid import testing
from multidict import MultiDict

from members.tests.base import VokoTestCase
from members.views.workgroup import WorkgroupView, NewWorkgroupView, ListWorkgroupView, EditWorkgroupView
from members.models.workgroups import Workgroup
from members.models.member import Member
from members.models.base import VokoValidationError


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

    def test_new_view(self):
        request = testing.DummyRequest()
        view_info = NewWorkgroupView(None, request)()
        self.assertEquals(view_info['wg'].name, '')

    def test_view_noexist(self):
        request = testing.DummyRequest()
        request.matchdict = {'wg_id': 3}
        self.assertRaises(Exception, WorkgroupView(None, request))

    def test_list(self):
        ''' simple test of list view '''
        request = testing.DummyRequest()
        view_info = ListWorkgroupView(None, request)()
        self.assertEqual([wg.id for wg in view_info['workgroups']], [1,2])
        self.assertEqual(view_info['order_name_choice'], 'desc')
        # change ordering
        request.params['order_dir'] = 'desc'
        view_info = ListWorkgroupView(None, request)()
        self.assertEqual([wg.id for wg in view_info['workgroups']], [2,1])
        self.assertEqual(view_info['order_name_choice'], 'asc')

    def test_edit(self):
        ''' edit the name '''
        request = testing.DummyRequest()
        request.matchdict = {'wg_id': 2}
        request.params['name'] = 'Wholesale Besteling'
        request.params['action'] = 'save'
        view = EditWorkgroupView(None, request)
        view.user = self.get_peter()
        _ = view()
        wg_bestel = self.DBSession.query(Workgroup).get(2)
        self.assertEqual(wg_bestel.name, 'Wholesale Besteling')

    def test_invalid_edit(self):
        ''' giving no name: invalid'''
        request = testing.DummyRequest()
        request.matchdict = {'wg_id': 2}
        request.params['name'] = ''
        request.params['action'] = 'save'
        self.assertRaises(Exception, EditWorkgroupView(None, request))

    def test_invalid_edit_noleader(self):
        request = testing.DummyRequest()
        request.matchdict = {'wg_id': 2}
        request.POST = MultiDict()
        request.POST['wg_leaders'] = ''
        request.params['action'] = 'save'
        view = EditWorkgroupView(None, request)
        view.user = self.get_peter()
        self.assertRaises(VokoValidationError, view)

    def test_create(self):
        '''The NewWorkgroupView only shows an empty form. Creation is done in EditWorkgroupView'''
        request = testing.DummyRequest()
        request.params['name'] = 'Cafe'
        request.params['desc'] = 'Shake and Bake'
        request.POST = MultiDict()
        request.POST['wg_leaders'] = '1'
        request.params['action'] = 'save'
        view = EditWorkgroupView(None, request)
        view.user = self.get_peter()
        view()
        wg = self.DBSession.query(Workgroup).filter(Workgroup.name==u'Cafe').first()
        self.assertEquals(wg.desc, 'Shake and Bake')

    def test_deactivate(self):
        request = testing.DummyRequest()
        def get_sys_wg():
            return self.DBSession.query(Workgroup).filter(Workgroup.name==u'Systems').first()
        wg_system = get_sys_wg()
        request.matchdict = {'wg_id': wg_system.id}
        request.params['action'] = 'toggle-active'
        view = EditWorkgroupView(None, request)
        view()
        self.assertTrue(view.confirm_toggle_active)
        request.params['action'] = 'toggle-active-confirmed'
        view()
        self.assertFalse(get_sys_wg().active)

