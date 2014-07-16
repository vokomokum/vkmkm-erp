from pyramid.authentication import AuthTktCookieHelper

from members.models.base import DBSession
from members.models.member import Member
from members.utils.security import groupfinder, authenticated_userid


class VokoAuthenticationPolicy(object):
    '''
    Policy that mimics what the wholesale order app does: two cookies,
    one for mem_id and one for a key in the DB.
    We want to store this on the parent domain, so several app on subdomains
    can make use of these cookies.
    (requires Pyramid >= 1.5)

    TODO: the test app should still use specific domains, bcs they work on outdated data!
    '''

    def __init__(self, settings):
        secret = ''
        self.cookieMem = AuthTktCookieHelper(secret, cookie_name='Mem')
        self.cookieKey = AuthTktCookieHelper(secret, cookie_name='Key')
        self.cookieMem.parent_domain = True
        self.cookieKey.parent_domain = True

    def remember(self, request, principal, **kw):
        m = DBSession().query(Member).filter(Member.mem_id == principal).first()
        headers = self.cookieMem._get_cookies(request, str(m.mem_id)) + \
                  self.cookieKey._get_cookies(request, str(m.mem_cookie))
        return headers

    def forget(self, request):
        headers = self.cookieMem.forget(request) +\
                  self.cookieKey.forget(request)
        return headers

    def unauthenticated_userid(self, request):
        result = self.cookieMem.identify(request)
        if result:
            return result['userid']

    def authenticated_userid(self, request):
        return authenticated_userid(request)

    def effective_principals(self, request):
        return groupfinder(self.authenticated_userid(request), request)


