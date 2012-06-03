from __future__ import unicode_literals

from pyramid.httpexceptions import HTTPFound
from pyramid.security import remember, forget
from pyramid.url import route_url
from pyramid.view import view_config

from members.utils.security import get_member
from members.utils.md5crypt import md5crypt
from members.views.base import BaseView


@view_config(renderer='../templates/base.pt', route_name='login')
@view_config(renderer='../templates/base.pt',
             context='pyramid.exceptions.Forbidden')
class Login(BaseView):

    def __call__(self):
        login_url = route_url('login', self.request)
        referrer = self.request.url
        if referrer == login_url:
            referrer = '/' # never use the login form itself as came_from
        came_from = self.request.params.get('came_from', referrer)
        message = ''
        if came_from != '/':
            message = 'You are not allowed to access this resource.'\
                      ' You may want to login as a member with the'\
                      ' sufficient access rights.'
        if 'form.submitted' in self.request.params:
            login = self.request.params['login']
            passwd = self.request.params['passwd']
            member = get_member(login)
            if member:
                # jim uses encrypted pwd as salt
                enc_pwd = md5crypt(str(passwd), str(member.mem_enc_pwd))
                if (member.mem_enc_pwd and str(member.mem_enc_pwd) == enc_pwd):
                    if member.mem_active:
                        self.logged_in = True
                        headers = remember(self.request, member.mem_id)
                        return HTTPFound(location = came_from, headers = headers)
                    else:
                        message += 'Note that the account of {} has been '\
                                   ' set to inactive. Please contact '\
                                   ' members@vokomokum.nl.'.format(member)
                else:
                    message += ' The password is not correct.'
            else:
                message += ' Member not found. '
            message += ' The Login failed.'

        return dict(msg = message,
                    url = self.request.application_url + '/login',
                    came_from = came_from,
                   )


@view_config(renderer='../templates/base.pt', route_name='logout')
class Logout(BaseView):

    def __call__(self):
        headers = forget(self.request)
        return HTTPFound(location = route_url('home', self.request),
                         headers = headers)
