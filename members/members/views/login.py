from pyramid.httpexceptions import HTTPFound
from pyramid.security import remember
from pyramid.security import forget
from pyramid.url import route_url
from pyramid.view import view_config

from members.security import get_member
from members.views.base import BaseView


@view_config(renderer='../templates/base.pt', route_name='login')
class Login(BaseView):

    def __call__(self):
        print "LOGIN"
        login_url = route_url('login', self.request)
        referrer = self.request.url
        if referrer == login_url:
            referrer = '/' # never use the login form itself as came_from
        came_from = self.request.params.get('came_from', referrer)
        message = ''
        if 'form.submitted' in self.request.params:
            login = self.request.params['login']
            passwd = self.request.params['passwd']
            member = get_member(login)
            if member:
                #import md5
                #if member.mem_enc_pwd == md5.new(passwd).digest():
                print member.mem_enc_pwd, passwd
                if member.mem_enc_pwd == passwd:
                    self.logged_in = True
                    headers = remember(self.request, login)
                    return HTTPFound(location = came_from,
                        headers = headers)
            else:
                message = 'Member not found. '
            message += 'The Login failed.'

        return dict(msg = message,
                    url = self.request.application_url + '/login',
                    came_from = came_from,
                   )


@view_config(renderer='../templates/base.pt', route_name='logout')
class Logout(BaseView):

    def __call__(self):
        headers = forget(self.request)
        #return HTTPFound(location = route_url('home', self.request),
        #                 headers = headers)
        self.logged_in = False

        return dict(logged_in = False,
                    msg = 'You have been logged out')
