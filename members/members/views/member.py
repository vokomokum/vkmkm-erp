from pyramid.view import view_config

from sqlalchemy import asc, desc

import os
from datetime import datetime
import random
import string
import base64

from members.models.member import Member
from members.models.base import DBSession, VokoValidationError
from members.views.base import BaseView
from members.utils.md5crypt import md5crypt
from members.utils.mail import sendmail


def get_member(session, request):
    ''' make a Member object, use ID from request if possible '''
    member = Member(fname=u'', prefix=u'', lname=u'')
    if request.matchdict.has_key('mem_id'):
        m_id = request.matchdict['mem_id']
        if m_id == 'new':
            return member
        try:
            mid = int(m_id)
        except ValueError:
            raise Exception("No member with ID %s" % m_id)
        member = session.query(Member).get(m_id)
        if member:
            member.exists = True
        else:
            raise Exception("No member with ID %s" % m_id)
    return member


def fill_member_from_request(member, request):
    '''overwrite member properties from request'''
    if request and member:
        # overwrite member properties from request, pwds are excluded
        for attr in [a for a in Member.__dict__.keys()\
                     if a.startswith('mem_') and not a in ['mem_id']]:
            type = str(member.__mapper__.columns._data[attr].type)
            if request.params.has_key(attr):
                v = request.params[attr]
                if type == 'BOOLEAN':
                    v = {'on':True, '':False}[v]
                member.__setattr__(attr, v)
            else:
                if type == 'BOOLEAN' and member.__dict__.has_key(attr)\
                   and member.__dict__[attr] is True\
                   and request.params.has_key('action')\
                   and request.params['action'] == 'save':
                    member.__setattr__(attr, False)
    return member


@view_config(renderer='../templates/edit-member.pt',
             route_name='member-new',
             permission='edit')
class NewMemberView(BaseView):

    tab = 'members'

    def __call__(self):
        return dict(m = Member('', '', ''), msg='')


@view_config(renderer='../templates/member.pt',
             route_name='member',
             permission='view')
class MemberView(BaseView):

    tab = 'members'

    def user_can_edit(self):
        if user:
            return self.user.mem_id == m.mem_id or self.user.mem_admin
        else:
            return False

    def __call__(self):
        m = get_member(DBSession(), self.request)
        # assigned and worked shifts
        assigned = [s for s in m.scheduled_shifts if s.state == 'assigned']
        worked = [s for s in m.scheduled_shifts if s.state == 'worked']
        return dict(m=m, msg='', assigned_shifts=assigned, worked_shifts=worked)


@view_config(renderer='../templates/edit-member.pt',
             route_name='member-edit',
             permission='edit')
class EditMemberView(BaseView):

    tab = 'members'

    def __call__(self):
        session = DBSession()
        member = get_member(session, self.request)
        if self.request.params.has_key('action'):
            action = self.request.params['action']
            if action == "save":
                member = fill_member_from_request(member, self.request)
                member.validate()
                if not member.exists:
                    #member.validate_pwd(self.request)
                    #salt = ''.join(random.choice(string.letters) for i in xrange(8))
                    #member.mem_enc_pwd = md5crypt(str(self.request.params['pwd1']), salt)
                    session.add(member)
                    session.flush() # flushing manually so the member gets an ID
                    pwd_reset_request(member)
                    return self.redirect('/member/%d?msg=Member was created'\
                                         ' and was sent a mail to set up a'\
                                         ' password.' % member.mem_id)
                if not member.mem_enc_pwd or member.mem_enc_pwd == '':
                    raise VokoValidationError('Member has no password.')
                return dict(m = member, msg='Member has been saved.')
            elif action == 'delete':
                member = get_member(session, self.request)
                self.confirm_deletion = True
                return dict(m=member)
            elif action == 'delete-confirmed':
                session.delete(member)
                return dict(m=None, msg='Member %s has been deleted.' % member)
        return dict(m = member, msg='')


def pwd_reset_request(member, first=False):
    '''
    sent member a mail with a temporary URL to update their password.
    we set an initial random code in mem_pwd_url and send an email
    with the reset link
    
    :param Member member: member whose password is to be reset
    :param bool first: True if this email is the first this user gets (on
                        account creation)
    '''
    code = base64.urlsafe_b64encode(os.urandom(16))
    member.mem_pwd_url = code
    subject = 'Set a new pasword for your Vokomokum account.'
    if first:
        subject = 'Welcome to Vokomokum. Please set a password.'
    mail_templ = open('members/templates/pwdreset_txt.eml', 'r')
    body = mail_templ.read()
    return sendmail(member.mem_email, subject, body.format(key=code))


#class ResetPasswordView(BaseView):
# TODO:
# - make this into a full-class view:
#   make template and routing
# - 1. default: show a form to request a password reset (enter emial or member number)
# - 2. if it member is identifiable, send them an email with a link
# - 3. if correct code (from sent link) is used to come here, then we reset
#
#    def __call__(self):
#       has_code = False
#       code_ok = False
#       msg = ''
#       if params has code:
#           has_code = True
#           member = find member by code
#           if member:
#               code_ok = True
#               if params has no pwd:
#                   msg = u'Please enter a new password below.'
#                   # show form
#               else:
#                   # set new password
#                   member.validate_pwd(self.request)
#                   salt = ''.join(random.choice(string.letters) for i in xrange(8))
#                   member.mem_enc_pwd = md5crypt(str(self.request.params['pwd1']), salt)
#                   member.mem_pwd_url = ''
#                   msg = u'Password has been set. Please use new password to log in.'
#                   TODO: log out (forget headers), redirect to login view
#           else:
#               msg = u'code invalid'
#       else:
#           if params has email address or member number:
#               if it is known:
#                   pwd_reset_request(member)
#                   msg = u'A reset link has been sent to your email
#                   address (%s).' % email
#               else:
#                   msg = u'Cannot find any member with this
#                   information: %s.' % bla
#           else:
#
#       return dict(msg=msg, code=code, has_code=has_code, code_ok=code_ok)


@view_config(renderer='../templates/list-members.pt', route_name='member-list')
class ListMemberView(BaseView):

    tab = 'members'

    def __call__(self):
        dbsession = DBSession()
        m_query = dbsession.query(Member)

        # show msg
        if self.request.params.has_key('msg'):
            msg = self.request.params['msg']
        else:
            msg = ''

        # -- inactive members? --
        show_inactive = True
        if not self.request.params.has_key('include_inactive')\
           or not self.request.params['include_inactive']:
            show_inactive = False
            m_query = m_query.filter(Member.mem_active==True)

        # -- ordering --
        # direction
        odir = asc
        if self.request.params.has_key('order_dir')\
           and self.request.params['order_dir'] == 'desc':
            odir = desc
        # order by
        # key is what the outside world sees, value is what SQLAlchemy uses
        order_idxs = {'id': Member.mem_id, 'name': Member.mem_lname}
        order_by = 'id'
        if self.request.params.has_key('order_by')\
          and order_idxs.has_key(self.request.params['order_by']):
            order_by = self.request.params['order_by']
        # ordering choices
        order_id_choice = 'asc'
        if order_by == 'id' and odir == asc:
            order_id_choice = 'desc'
        order_name_choice = 'asc'
        if order_by == 'name' and odir == asc:
            order_name_choice = 'desc'

        m_query = m_query.order_by(odir(order_idxs[order_by]))
        members = m_query.all()
        self.mem_count = len(members)
        return dict(members = members, msg=msg, order_by=order_by,
                    order_id_choice=order_id_choice, order_name_choice=order_name_choice,
                    show_inactive=show_inactive, came_from='/members')

