from pyramid import testing
from sqlalchemy.exc import IntegrityError

import os

import base
from members.models.member import Member
from members.models.base import VokoValidationError
from members.views.login import Login
from members.views.member import MemberView
from members.views.member import NewMemberView
from members.views.member import ListMemberView
from members.views.member import EditMemberView
from members.views.pwdreset import ResetPasswordView
from members.views.pwdreset import ResetPasswordRequestView
from members.utils import mail
from members.utils.misc import get_settings
from members.utils.md5crypt import md5crypt

from members.tests.base import VokoTestCase


class TestMembers(VokoTestCase):

    def test_getquery(self):
        self.assertEqual(self.get_peter().mem_lname, 'Pan')

    def test_view(self):
        request = testing.DummyRequest()
        request.matchdict = {'mem_id': 1}
        view_info = MemberView(None, request)()
        self.assertEqual(view_info['m'].mem_id, 1)
        self.assertEqual(view_info['assigned_shifts'][0].task, 'do stuff')
        self.assertEqual(len(view_info['worked_shifts']), 0)

    def test_new_view_empty(self):
        request = testing.DummyRequest()
        view = NewMemberView(None, request)
        view.user = self.get_peter()
        self.assertEquals(view()['m'].mem_fname, '')

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

    def test_list_inactive(self):
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

    def test_login(self):
        ''' test if basic login works '''
        request = testing.DummyRequest()
        request.params['form.submitted'] = True
        request.params['login'] = '1'
        request.params['passwd'] = 'notsecret'
        peter = self.get_peter()
        view = Login(None, request)
        view.user = peter
        view()
        self.assertTrue(view.logged_in)

    def test_no_login_for_inactive(self):
        ''' inactive members are not allowed to logon anymore'''
        request = testing.DummyRequest()
        request.params['form.submitted'] = True
        request.params['login'] = '1'
        request.params['passwd'] = ''
        peter = self.get_peter()
        peter.mem_active = False
        view = Login(None, request)
        view()
        self.assertFalse(view.logged_in)

    def fillin_dummy_data(self, request):
        request.params['mem_email'] = 'peter@peter.de'
        request.params['mem_fname'] = 'Peter'
        request.params['mem_street'] = 'Blastreet'
        request.params['mem_house'] = '38'
        request.params['mem_mobile'] = '06 12345678'
        request.params['mem_postcode'] = '1017EA'
        request.params['mem_city'] = 'Amsterdam'
        request.params['mem_bank_no'] = '123456789'
        return request

    def test_edit(self):
        ''' edit the name '''
        request = testing.DummyRequest()
        request.matchdict = {'mem_id': 1} # peter
        request.params['action'] = 'save'
        # Make hans an admin, and let him be the user executing the view
        hans = self.get_hans()
        hans.mem_admin = True
        view = EditMemberView(None, request)
        view.user = hans
        # not enough info yet
        self.assertRaises(VokoValidationError, view)
        request = self.fillin_dummy_data(request)
        # and some explicit editing
        request.params['mem_lname'] = 'Petersnewlname'
        view_info = view()
        self.assertEqual(self.get_peter().mem_lname, 'Petersnewlname')

    def test_invalid_email_edit(self):
        request = testing.DummyRequest()
        request.matchdict = {'mem_id': 2} # hans
        hans = self.get_hans()
        view = EditMemberView(None, request)
        view.user = hans
        request = self.fillin_dummy_data(request)
        request.params['mem_email'] = 'peterATsomewhere'
        request.params['action'] = 'save'
        self.assertRaises(VokoValidationError, view)

    def test_invalid_attribute_edit(self):
        ''' this test runs as non-admin user '''
        peter = self.get_peter()
        self.assertTrue(peter.mem_active)
        request = testing.DummyRequest()
        request.matchdict = {'mem_id': peter.mem_id}
        request = self.fillin_dummy_data(request)
        request.params['mem_active'] = '0'
        request.params['action'] = 'save'
        self.assertTrue(peter.mem_active)

    def test_create(self):
        '''
        The NewMemberView only shows an empty form.
        Creation is done in EditMemberView
        '''
        request = testing.DummyRequest()
        request = self.fillin_dummy_data(request)
        request.params['action'] = 'save'
        view = EditMemberView(None, request)
        request.params['mem_lname'] = 'NewLastname'
        # Make peter an admin, and let him be the user executing the view
        peter = self.get_peter()
        peter.mem_admin = True
        view.user = peter
        view()
        # check if member exists
        mem = self.DBSession.query(Member)\
                            .filter(Member.mem_lname==u'NewLastname').first()
        self.assertIsNotNone(mem)

        # check if password reset email was sent with expected key
        mem_id,key = self.get_reset_info_from_mails()
        self.assertEquals(mem_id, mem.mem_id)
        self.assertEquals(key, mem.mem_pwd_url)

        # visit password reset view with key from sent link
        request = testing.DummyRequest()
        password = 'notsecret'
        request.params['pwd1'] = password
        request.params['pwd2'] = password
        request.matchdict['mem_id'] = mem_id
        request.matchdict['key'] = key
        view = ResetPasswordView(None, request)
        response = view()
        self.assertTrue('Password has been set' in response['msg'])
        # check if password was saved and encrypted correctly
        mem = self.DBSession.query(Member).filter(Member.mem_id==mem_id).first()
        enc_pwd = md5crypt(str(password), str(mem.mem_enc_pwd))
        self.assertEquals(enc_pwd, mem.mem_enc_pwd)

    def test_toggle_active(self):
        request = testing.DummyRequest()
        peter = self.get_peter()
        self.assertTrue(peter.mem_active)
        request.matchdict = {'mem_id': peter.mem_id}
        request.params['action'] = 'toggle-active'
        view = EditMemberView(None, request)
        view.user = peter
        view()
        self.assertTrue(peter.mem_active)
        self.assertTrue(view.confirm_toggle_active)
        request.params['action'] = 'toggle-active-confirmed'
        view()
        self.assertFalse(peter.mem_active)
        # and back again ...
        request.params['action'] = 'toggle-active'
        view()
        request.params['action'] = 'toggle-active-confirmed'
        view()
        self.assertTrue(peter.mem_active)

    def test_reset_password(self):
        # request a password reset, unsuccessfully
        request = testing.DummyRequest()
        request.params['mem_id'] = '999999999999'
        response = ResetPasswordRequestView(None, request)()
        self.assertTrue('Cannot find any member' in response['msg'])
        request = testing.DummyRequest()
        request.params['email'] = 'does@not.exist.com'
        response = ResetPasswordRequestView(None, request)()
        self.assertTrue('Cannot find any member' in response['msg'])
        # now successfully
        mem = self.DBSession.query(Member)\
                            .filter(Member.mem_fname=='Peter').first()
        request = testing.DummyRequest()
        request.params['mem_id'] = mem.mem_id
        response = ResetPasswordRequestView(None, request)()
        self.assertTrue('A reset link has been sent' in response['msg'])

        # visit password reset view with key from sent link, set new password
        mem_id,key = self.get_reset_info_from_mails() 
        self.assertEquals(key, mem.mem_pwd_url)
        request = testing.DummyRequest()
        password = 'notsecret'
        request.params['pwd1'] = password
        request.params['pwd2'] = password
        request.matchdict['mem_id'] = mem_id
        request.matchdict['key'] = key
        view = ResetPasswordView(None, request)
        response = view()
        self.assertTrue('Password has been set' in response['msg'])
        # check if password was saved and encrypted correctly
        mem = self.DBSession.query(Member).filter(Member.mem_id==mem_id).first()
        enc_pwd = md5crypt(str(password), str(mem.mem_enc_pwd))
        self.assertEquals(enc_pwd, mem.mem_enc_pwd)

        # the key is now not longer valid
        self.assertNotEqual(key, mem.mem_pwd_url)
        

    def get_reset_info_from_mails(self):
        mail_folder = get_settings()['vokomokum.mail_folder']
        mails = [m for m in os.listdir(mail_folder) if m.endswith('.eml')]
        f = open('%s/%s' % (mail_folder, mails[0]), 'r')
        line = ""
        for l in f:
            if l.startswith('<URL'):
                line = l
        mem_id = int(line.split('member/')[1].split('/reset-pwd')[0].strip())
        key = line.split('reset-pwd/')[1].strip()[:-1]
        return mem_id, key
