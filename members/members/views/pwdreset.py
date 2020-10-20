import os
import base64

from pyramid.view import view_config
from passlib.hash import md5_crypt

from members.views.base import BaseView
from members.models.member import Member, get_member
from members.models.base import DBSession
from members.utils.mail import sendmail


def send_pwdreset_request(member, app_url, first=False):
    '''
    Make a key that enables resetting the password. Store it in the member
    table and then send it per email to the member, in a nice rest URL.
    
    :param Member member: member whose password is to be reset
    :param string app_url: URL of this application
    :param bool first: True if this email is the first this user gets (on
                        account creation)
    '''
    code = str(base64.urlsafe_b64encode(os.urandom(16)), "utf-8")
    member.mem_pwd_url = code
    subject = 'Set a new password for your Vokomokum account.'
    if first:
        subject = 'Welcome to Vokomokum. Please set a password.'
    mail_templ = open('members/templates/pwdreset_txt.eml', 'r')
    mail = mail_templ.read()
    body = mail.format(portal_url=app_url, mem_id=member.mem_id, key=code)
    return sendmail(member.mem_email, subject, body, folder='passwords')


@view_config(renderer='../templates/pwdreset.pt', route_name='reset-pwd-request')
class ResetPasswordRequestView(BaseView):
    
    tab = 'members'

    def __call__(self):
        '''
        Default: Show form to identify member
        If data entered and member identified, send reset request email 
        '''
        self.login_necessary = False
        session = DBSession()
        p = self.request.params
        member = None
        if 'email' in p and p['email'] != "":
            member = session.query(Member)\
                            .filter(Member.mem_email == p['email']).first()
        if 'mem_id' in p and p['mem_id'] != "":
            try:
                member = get_member(session, self.request)
            except Exception:
                member = None
        if member:
            send_pwdreset_request(member, self.request.application_url)
            return dict(msg=u'A reset link has been sent to the email'\
                             ' address {!s}.'.format(member.mem_email),
                        m=member, form=None, key=None)
        if (('email' in p and p['email'] != "") or
            ('mem_id' in p and p['mem_id'] != "")):
            return dict(msg=u'Cannot find any member with this information.',
                        m=member, form='request', key=None)
        return dict(msg=u'', m=member, form='request', key=None)


@view_config(renderer='../templates/pwdreset.pt', route_name='reset-pwd')
class ResetPasswordView(BaseView):
    
    tab = 'members'

    def __call__(self):
        '''
        Actually reset the password, if correct key (from sent link) 
        is used to come here and member is identifiable from request.
        '''
        self.login_necessary = False
        session = DBSession()
        md = self.request.matchdict
        def info(msg):
            return dict(form="", m=None, key=None, msg=msg)

        if not 'key' in md or md['key'] == "":
            return info(u'Sorry, no key given to grant reset request.')
        member = get_member(session, self.request)
        if not member:
            return info(u'Sorry, cannot identify member.')
        if member.mem_pwd_url != md['key']:
            return info(u'Sorry, the reset request cannot be authorised.')
        if 'pwd1' not in self.request.params:
            # show password reset form 
            return dict(m=member, form='reset', key=md['key'])
        # set new password
        member.validate_pwd(self.request)
        pwd = str(self.request.params['pwd1'])
        member.mem_enc_pwd = md5_crypt.hash(pwd)
        member.mem_pwd_url = ''
        return info(u'Password has been set.'\
               ' Please use the new password the next time you log in.')
