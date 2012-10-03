from pyramid.config import Configurator
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from sqlalchemy import engine_from_config
from pyramid.exceptions import NotFound

from members.models.base import configure_session
from members.utils.security import groupfinder
from members.views.base import NotFoundView
from members.views.base import ErrorView
# import all our types here once, important
from members.models.member import Member
from members.models.workgroups import Workgroup
from members.models.shift import Shift
from members.models.others import Order
from members.models.applicant import Applicant


def main(global_config, **settings):
    """
    This function returns a Pyramid WSGI application.
    """
    engine = engine_from_config(settings, 'sqlalchemy.')
    configure_session(engine)

    # authentication setup TODO: use order app cookies
    #f = open('auth.key', 'r')
    #authkey = f.readline()
    authkey = 'pretty_secret'
    authn_policy = AuthTktAuthenticationPolicy(
            authkey,
            callback=groupfinder,
            cookie_name='Mem',
            include_ip=True)
    authz_policy = ACLAuthorizationPolicy()
    config = Configurator(settings=settings,
        #root_factory = 'members.models.auth.RootFactory',
        authentication_policy = authn_policy,
        authorization_policy = authz_policy)

    # routes to our views
    # (each view indicates a route pattern it applies to) 
    config.add_static_view('static', 'members:static')
    config.add_route('home', '/')
    config.add_route('login', '/login')
    config.add_route('logout', '/logout')
    config.add_route('member', '/member/{mem_id}', factory=Member)
    config.add_route('member-list', '/members', factory=Member)
    config.add_route('member-new', '/members/new', factory=Member)
    config.add_route('member-edit', '/member/{mem_id}/edit', factory=Member)
    config.add_route('reset-pwd-request', '/reset-pwd')
    config.add_route('reset-pwd', '/member/{mem_id}/reset-pwd/{key}', factory=Member)
    config.add_route('workgroup', '/workgroup/{wg_id}', factory=Workgroup)
    config.add_route('workgroup-list', '/workgroups', factory=Workgroup)
    config.add_route('workgroup-new', '/workgroups/new', factory=Workgroup)
    config.add_route('workgroup-edit', '/workgroup/{wg_id}/edit', factory=Workgroup)
    config.add_route('shift-list', '/workgroup/{wg_id}/shifts/{year}/{month}', factory=Workgroup)
    config.add_route('shift-new', '/workgroup/{wg_id}/new-shift', factory=Workgroup)
    config.add_route('shift-edit', '/workgroup/{wg_id}/edit-shift/{s_id}/{action}', factory=Workgroup)
    config.add_route('applicant-list', '/applicants', factory=Applicant)
    config.add_route('applicant-new', '/applicants/new', factory=Applicant)
    config.add_route('applicant-delete', '/applicant/{a_id}/delete', factory=Applicant)
    config.add_route('applicant-mkmember', '/applicant/{a_id}/mkmember', factory=Applicant)

    # custom error views, catching NotFound and all Exceptions
    config.add_view(NotFoundView, context=NotFound, renderer='templates/base.pt')
    config.add_view(ErrorView, context=Exception, renderer='templates/base.pt')

    config.scan()

    return config.make_wsgi_app()


