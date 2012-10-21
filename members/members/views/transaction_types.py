from __future__ import unicode_literals

from pyramid.view import view_config

from members.models.base import DBSession
from members.views.base import BaseView
from members.models.transactions import TransactionType, Transaction
from members.models.transactions import reserved_ttype_names


def get_transaction_types(session):
    return session.query(TransactionType)\
            .order_by(TransactionType.id)\
            .all()

 
def get_transaction_type(session, tt_id):
    return session.query(TransactionType).get(tt_id)


@view_config(renderer='../templates/transaction_types.pt',
             route_name='transaction-type-list',
             permission='view')
class ListTransactionTypes(BaseView):

    tab = 'finance'

    def __call__(self):
        if 'msg' in self.request.params:
            msg = self.request.params['msg']
        else:
            msg = ''
        self.user_can_edit = self.user.mem_admin\
                             or 'Finance' in self.user.workgroups
        return dict(msg=msg,
                    reserved_names = reserved_ttype_names,
                    transaction_types=get_transaction_types(DBSession()))


@view_config(renderer='../templates/transaction_types.pt',
             route_name='transaction-type-new',
             permission='edit')
class NewTransactionType(BaseView):

    tab = 'finance'

    def __call__(self):
        name = self.request.params['name']
        tt = TransactionType(None, name)
        tt.validate()
        session = DBSession()
        existing = session.query(TransactionType)\
                          .filter(TransactionType.name == tt.name).all()
        if len(existing) > 0: 
            return self.redirect('/transaction-types?msg=Transaction type '\
                                 ' with name "{}" already exists'\
                                 .format(tt.name))
        session.add(tt)
        session.flush()
        return self.redirect('/transaction-types?msg=Transaction type "{}"'\
                             ' has been added to the list.'.format(tt.name))


@view_config(renderer='../templates/transaction_types.pt',
             route_name='transaction-type-save',
             permission='edit')
class SaveTransactionType(BaseView):

    tab = 'finance'

    def __call__(self):
        session = DBSession()
        tt_id = self.request.matchdict['tt_id']
        name = self.request.params['name']
        tt = get_transaction_type(session, tt_id)
        if tt.name in reserved_ttype_names:
            return self.redirect('/transaction-types?msg=The name {} is '\
                                 'reserved and cannot be changed'\
                                 .format(tt.name))
        tt.name = name
        tt.validate()
        return self.redirect('/transaction-types?msg=Transaction type "{}" '\
                             'has been saved.'.format(tt.name))


@view_config(renderer='../templates/transaction_types.pt',
             route_name='transaction-type-delete',
             permission='edit')
class DeleteTransactionType(BaseView):

    tab = 'finance'

    def __call__(self):
        session = DBSession()
        tt_id = self.request.matchdict['tt_id']
        tt = get_transaction_type(session, tt_id)
        if not tt.locked:
            session.delete(tt)
            session.flush()
            return self.redirect('/transaction-types?msg='\
                                 'Transaction type "{}" has been deleted.'\
                                  .format(tt.name))
        else:
            return self.redirect('/transaction-types?msg=Cannot remove'\
                                 ' transaction type "{}": transactions'\
                                 ' refer to it.'.format(tt.name))

