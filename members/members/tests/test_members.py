from pyramid import testing
from sqlalchemy.exc import IntegrityError

import base
from members.models.member import Member
from members.models.base import VokoValidationError
from members.views.member import MemberView, NewMemberView, ListMemberView, EditMemberView

from members.tests.base import VokoTestCase


class TestMembers(VokoTestCase):

    def get_peter(self):
        return self.DBSession.query(Member).get(1)

    def test_getquery(self):
        self.assertEqual(self.get_peter().mem_lname, 'Pan')

    def test_view(self):
        request = testing.DummyRequest()
        request.matchdict = {'mem_id': 1}
        view_info = MemberView(None, request)()
        self.assertEqual(view_info['m'].mem_id, 1)
        self.assertEqual(view_info['assigned_shifts'][0].task.label, 'do stuff')
        self.assertEqual(len(view_info['worked_shifts']), 0)

    def test_new_view(self):
        request = testing.DummyRequest()
        view_info = NewMemberView(None, request)()
        self.assertEquals(view_info['m'].mem_fname, '')

    def test_view_noexist(self):
        request = testing.DummyRequest()
        request.matchdict = {'mem_id': 3}
        self.assertRaises(Exception, MemberView(None, request))

    def test_list(self):
        ''' simple test of list view '''
        request = testing.DummyRequest()
        view_info = ListMemberView(None, request)()
        self.assertEqual([m.mem_id for m in view_info['members']], [1,2])
        self.assertEqual(view_info['order_id_choice'], 'desc')
        self.assertEqual(view_info['order_name_choice'], 'asc')
        # change ordering
        request.params['order_by'] = 'id'
        request.params['order_dir'] = 'desc'
        view_info = ListMemberView(None, request)()
        self.assertEqual([m.mem_id for m in view_info['members']], [2,1])
        self.assertEqual(view_info['order_name_choice'], 'asc')

    def test_inactive(self):
        ''' show only active by default '''
        request = testing.DummyRequest()
        view_info = ListMemberView(None, request)()
        self.assertEqual([m.mem_id for m in view_info['members']], [1,2])
        peter = self.get_peter()
        peter.mem_active = False
        view_info = ListMemberView(None, request)()
        self.assertEqual([m.mem_id for m in view_info['members']], [2])
        request.params['include_inactive'] = True
        view_info = ListMemberView(None, request)()
        self.assertEqual([m.mem_id for m in view_info['members']], [1,2])

    def fillin_dummy_data(self, request):
        request.params['mem_email'] = 'peter@peter.de'
        request.params['mem_fname'] = 'Peter'
        request.params['mem_street'] = 'Blastreet'
        request.params['mem_house'] = '38'
        request.params['mem_mobile'] = '06 12345678'
        request.params['mem_postcode'] = '1017EA'
        request.params['mem_city'] = 'Amsterdam'
        request.params['mem_bank_no'] = '123456789'
        request.params['mem_enc_pwd'] = 'notsecret'
        return request

    def test_edit(self):
        ''' edit the name '''
        request = testing.DummyRequest()
        request.matchdict = {'mem_id': 1}
        request.params['action'] = 'save'
        # not enough info yet
        self.assertRaises(VokoValidationError, EditMemberView(None, request))
        request = self.fillin_dummy_data(request)
        # and some explicit editing
        request.params['mem_lname'] = 'Petersnewlname'
        view_info = EditMemberView(None, request)()
        self.assertEqual(self.get_peter().mem_lname, 'Petersnewlname')

    def test_invalid_edit(self):
        ''' giving no name: invalid'''
        request = testing.DummyRequest()
        request.matchdict = {'mem_id': 2}
        request = self.fillin_dummy_data(request)
        request.params['mem_email'] = 'peterATsomewhere'
        request.params['action'] = 'save'
        self.assertRaises(VokoValidationError, EditMemberView(None, request))

    def test_create(self):
        '''The NewMemberView only shows an empty form. Creation is done in EditMemberView'''
        request = testing.DummyRequest()
        request = self.fillin_dummy_data(request)
        request.params['action'] = 'save'
        view = EditMemberView(None, request)
        request.params['mem_lname'] = 'NewLastname'
        request.params['pwd1'] = 'notsecret'
        request.params['pwd2'] = 'notsecret'
        # raises an AttributeError when redirecting after successful
        # save, bcs we haven't set view.user
        self.assertRaises(AttributeError, view)
        mem = self.DBSession.query(Member).filter(Member.mem_lname==u'NewLastname').first()
        self.assertIsNotNone(mem)

    def test_delete(self):
        request = testing.DummyRequest()
        peter = self.get_peter()
        request.matchdict = {'mem_id': peter.mem_id}
        request.params['action'] = 'delete'
        view = EditMemberView(None, request)
        view()
        self.assertTrue(view.confirm_deletion)
        request.params['action'] = 'delete-confirmed'
        # no idea why I have to do that, I suspect it has to do with
        # using sqlite
        if base.db_type == 'sqlite':
            view()
            self.assertRaises(IntegrityError,
                    self.DBSession.query(Member).filter(Member.mem_fname==u'Peter').first)
        else:
            self.assertRaises(IntegrityError, view)
            self.assertIsNone(self.get_peter())

