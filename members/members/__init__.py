from pyramid.config import Configurator
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from sqlalchemy import engine_from_config

from members.models.setup import initialize_sql
from members.security import groupfinder


def main(global_config, **settings):
    """
    This function returns a Pyramid WSGI application.
    """
    print "WAAAH"
    engine = engine_from_config(settings, 'sqlalchemy.')
    initialize_sql(engine)
    f = open('auth.key', 'r')
    authkey = f.readline()
    authn_policy = AuthTktAuthenticationPolicy(
            authkey, callback=groupfinder)
    authz_policy = ACLAuthorizationPolicy()
    config = Configurator(settings=settings,
        root_factory = 'members.models.auth.RootFactory',
        authentication_policy = authn_policy,
        authorization_policy = authz_policy)

    config.add_view(context='pyramid.exceptions.NotFound',
                    view='pyramid.view.append_slash_notfound_view')

    #config.add_renderer('.pt', 'pyramid.chameleon_zpt.renderer_factory')
    config.add_static_view('static', 'members:static')
    config.add_route('home', '/')
    config.add_route('login', '/login')
    config.add_route('logout', '/logout')
    config.add_route('memberlist', '/members')
    config.add_route('new_member', '/members/new')
    config.add_route('member', '/member/{id}')
    config.add_route('workgrouplist', '/workgroups')
    config.add_route('new_workgroup', '/workgroups/new')
    config.add_route('workgroup', '/workgroup/{id}')
    config.scan()
    #config.add_route('home', '/', view='members.views.views.TestView',
    #                 view_renderer='templates/mytemplate.pt')


    return config.make_wsgi_app()


