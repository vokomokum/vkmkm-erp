from pyramid.config import Configurator
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from sqlalchemy import engine_from_config

from members.models.setup import initialize_sql
from members.security import groupfinder
from members.models.member import Member
from members.models.workgroups import Workgroup
from members.models.shift import Shift


def main(global_config, **settings):
    """
    This function returns a Pyramid WSGI application.
    """
    engine = engine_from_config(settings, 'sqlalchemy.')
    initialize_sql(engine)

    # authentication setup TODO: use order app cookies
    f = open('auth.key', 'r')
    authkey = f.readline()
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

    # TODO: custom not found view
    config.add_view(context='pyramid.exceptions.NotFound',
                    view='pyramid.view.append_slash_notfound_view')
    #config.add_renderer('.pt', 'pyramid.chameleon_zpt.renderer_factory')

    # routes to be used by views
    config.add_static_view('static', 'members:static')
    config.add_route('home', '/')
    config.add_route('login', '/login')
    config.add_route('logout', '/logout')
    config.add_route('memberlist', '/members', factory=Member)
    config.add_route('new_member', '/members/new', factory=Member)
    config.add_route('member', '/member/{mem_id}', factory=Member)
    config.add_route('member-edit', '/member/{mem_id}/edit', factory=Member)
    config.add_route('workgrouplist', '/workgroups', factory=Workgroup)
    config.add_route('new_workgroup', '/workgroups/new', factory=Workgroup)
    config.add_route('workgroup', '/workgroup/{wg_id}', factory=Workgroup)
    config.add_route('workgroup-edit', '/workgroup/{wg_id}/edit', factory=Workgroup)
    config.add_route('new_shift', '/workgroup/{wg_id}/new-shift/in/{month}/{year}', factory=Workgroup)
    config.add_route('edit_shift', '/workgroup/{wg_id}/edit-shift/{s_id}', factory=Workgroup)

    config.scan()

    return config.make_wsgi_app()


