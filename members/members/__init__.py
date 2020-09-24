from pyramid.config import Configurator
from pyramid.authorization import ACLAuthorizationPolicy
from sqlalchemy import engine_from_config
from pyramid.exceptions import NotFound

from members.models.base import configure_session
from members.utils.auth import VokoAuthenticationPolicy
from members.views.base import NotFoundView
from members.views.base import ErrorView
# import all our types here once, important
from members.models.member import Member
from members.models.workgroups import Workgroup
from members.models.applicant import Applicant
from members.models.transactions import Transaction, TransactionType


def main(global_config, **settings):
    """
    This function returns a Pyramid WSGI application.
    """
    engine = engine_from_config(settings, 'sqlalchemy.')
    configure_session(engine)

    # authentication setup
    authn_policy = VokoAuthenticationPolicy(settings)
    authz_policy = ACLAuthorizationPolicy()
    config = Configurator(settings=settings,
        authentication_policy = authn_policy,
        authorization_policy = authz_policy)
    config.include('pyramid_chameleon') # needed for pyramid >= 1.5

    # routes to our views
    # (each view indicates a route pattern it applies to) 
    config.add_static_view('static', 'members:static')
    config.add_route('home', '/')
    config.add_route('login', '/login')
    config.add_route('logout', '/logout')
    config.add_route('userinfo', '/userinfo')
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
    config.add_route('shift-year-overview', '/workgroup/{wg_id}/shifts/{year}', factory=Workgroup)
    config.add_route('applicant-list', '/applicants', factory=Applicant)
    config.add_route('applicant-new', '/applicants/new', factory=Applicant)
    config.add_route('applicant-delete', '/applicant/{a_id}/delete', factory=Applicant)
    config.add_route('applicant-mkmember', '/applicant/{a_id}/mkmember', factory=Applicant)
    config.add_route('transaction-type-list', '/transaction-types', factory=TransactionType)
    config.add_route('transaction-type-new', '/transaction-types/new', factory=TransactionType)
    config.add_route('transaction-type-save', '/transaction-type/{tt_id}/save', factory=TransactionType)
    config.add_route('transaction-type-delete', '/transaction-type/{tt_id}/delete', factory=TransactionType)
    config.add_route('transactions', '/transactions', factory=Transaction)
    config.add_route('transaction-list', '/transactions/{year}/{month}', factory=Transaction)
    config.add_route('transaction-new', '/transactions/new', factory=Transaction)
    config.add_route('transaction-edit', '/transaction/{t_id}/edit/{action}', factory=Transaction)
    config.add_route('transaction-delete', '/transaction/{t_id}/delete', factory=Transaction)
    config.add_route('transactions-year-overview', '/transactions/{year}', factory=Transaction)
    config.add_route('charge-order', '/charge-order/{o_id}')
    config.add_route('mail-order-charges', '/mail-order-charges/{o_id}')
    config.add_route('docs', '/docs*folder')
    config.add_route('doc-view', '/doc*doc_path')
    config.add_route('doc-upload-form', '/file-upload-form')

    # custom error views, catching NotFound and all Exceptions
    config.add_view(NotFoundView, context=NotFound, renderer='templates/base.pt')
    config.add_view(ErrorView, context=Exception, renderer='templates/base.pt')

    config.scan(ignore="members.tests")

    return config.make_wsgi_app()


