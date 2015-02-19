from __future__ import unicode_literals

from pyramid.view import view_config

from suppliers.views.base import BaseView
from suppliers.models.supplier import Supplier, get_supplier



def fill_supplier_from_request(supplier, request, user_may_edit_admin_settings):
    pass


@view_config(renderer='../templates/edit-supplier.pt',
             route_name='supplier-new',
             permission='edit')
class NewSupplierView(BaseView):

    tab = 'suppliers'

    def __call__(self):
        self.user_may_edit_admin_settings = self.user.mem_admin
        return dict(m=Supplier('', '', ''), msg='')


@view_config(renderer='../templates/supplier.pt',
             route_name='supplier',
             permission='view')
class SupplierView(BaseView):

    tab = 'suppliers'


@view_config(renderer='../templates/edit-supplier.pt',
             route_name='supplier-edit',
             permission='edit')
class EditSupplierView(BaseView):

    tab = 'suppliers'

    def __call__(self):
        session = DBSession()
        supplier = get_supplier(session, self.request)


@view_config(renderer='../templates/list-suppliers.pt', route_name='supplier-list')
class ListSupplierView(BaseView):

    tab = 'suppliers'

    def __call__(self):
        dbsession = DBSession()
        m_query = dbsession.query(Supplier)


