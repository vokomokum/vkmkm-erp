from pyramid.authentication import AuthTktCookieHelper
from pyramid.security import Everyone, Authenticated

import pkg_resources

from members.models.base import DBSession
from members.models.member import Member
from members.utils.security import groupfinder, authenticated_userid


class VokoAuthenticationPolicy(object):
    '''
    Policy that mimics what the wholesale order app does: two cookies,
    one for mem_id and one for a key in the DB.
    We want to store this on the parent domain, which is easy if pyramid version
    >= 1.5, otherwise a little custom str-replace is needed.

    TODO: the test app should still use specific domains, bcs they work on outdated data!
    '''

    def __init__(self, settings):
        secret = ''
        ti = ''
        rt = ''
        self.pyramid_lt_15 =\
                pkg_resources.get_distribution("pyramid").version < "1.5"
        self.max_age = 9999999999
        self.cookieMem = AuthTktCookieHelper(secret, cookie_name='Mem',
            timeout=ti, reissue_time=rt, max_age=self.max_age)
        self.cookieKey = AuthTktCookieHelper(secret, cookie_name='Key',
            timeout=ti, reissue_time=rt, max_age=self.max_age)
        if not self.pyramid_lt_15:
            self.cookieMem.parent_domain = True
            self.cookieKey.parent_domain = True

    def remember(self, request, principal, **kw):
        m = DBSession().query(Member).filter(Member.mem_id == principal).first()
        headers = self.cookieMem._get_cookies(request, str(m.mem_id), max_age=self.max_age) + \
                  self.cookieKey._get_cookies(request, str(m.mem_cookie), max_age=self.max_age)
        if self.pyramid_lt_15: 
            new_headers = []
            for h in headers:
                new_headers.append((h[0], h[1].replace('members.vokomokum.nl', 'vokomokum.nl')))
            headers = new_headers
        return headers

    def forget(self, request):
        headers = self.cookieMem.forget(request) +\
                  self.cookieKey.forget(request)
        return headers

    def unauthenticated_userid(self, request):
        result = self.cookieMem.identify(request)
        if result:
            return result['userid']  # TODO: does this work?

    def authenticated_userid(self, request):
        return authenticated_userid(request)

    def effective_principals(self, request):
        return groupfinder(self.authenticated_userid(request), request)


