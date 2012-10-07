from pyramid.view import view_config
#from sqlalchemy import asc, desc

from datetime import datetime

from members.models.base import DBSession
from members.views.base import BaseView
from members.models.member import Member
from members.models.transactions import TransactionType, Transaction


def get_transaction_types(session):
    return session.query(TransactionType)\
            .order_by(TransactionType.id)\
            .all()

 
def get_transaction_type(session, tt_id):
    return session.query(TransactionType).get(tt_id)


def tt_deletable(session, tt):
    if len(tt.transactions) > 0:
        return False
    else:
        return True


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
        return dict(msg=msg,
                    transaction_types=get_transaction_types(DBSession()))

    def deletable(self, tt):
        return tt_deletable(DBSession(), tt)


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
        session.add(tt)
        session.flush()
        return self.redirect('/transaction-types?msg=Transaction type "{}"'\
                             ' has been added to the list.'.format(tt.name))


@view_config(renderer='../templates/transaction_types.pt',
             route_name='transaction-type-save',
             permission='edit')
class SaveTransactionType(BaseView):

    tab = 'applicants'

    def __call__(self):
        session = DBSession()
        tt_id = self.request.matchdict['tt_id']
        name = self.request.params['name']
        tt = get_transaction_type(session, tt_id)
        tt.name = name
        tt.validate()
        return self.redirect('/transaction-types?msg=Transaction type "{}" '\
                             'has been saved.'.format(tt.name))


@view_config(renderer='../templates/transaction_types.pt',
             route_name='transaction-type-delete',
             permission='edit')
class DeleteTransactionType(BaseView):

    tab = 'applicants'

    def __call__(self):
        session = DBSession()
        tt_id = self.request.matchdict['tt_id']
        tt = get_transaction_type(session, tt_id)
        if tt_deletable(session, tt):
            session.delete(tt)
            session.flush()
            return self.redirect('/transaction-types?msg='\
                                 'Transaction type "{}" has been deleted.'\
                                  .format(tt.name))
        else:
            return self.redirect('/transaction-types?msg=Cannot remove'\
                                 ' transaction type "{}": transactions'\
                                 ' refer to it.'.format(tt.name))

