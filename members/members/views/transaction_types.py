from pyramid.view import view_config
#from sqlalchemy import asc, desc

from datetime import datetime

from members.models.base import DBSession
from members.views.base import BaseView
from members.models.member import Member


def get_transaction_types(session):
    return session.query(TransactionTypes)\
            .order_by(TransactionTypes.id)\
            .all()

 
def get_transaction_type(session, tt_id):
    return session.query(TransactionType).get(tt_id)


def tt_deletable(session, tt_id):
    transactions = session.query(Transaction)\
                          .filter(Transaction.ttype == tt_id).all() 
    if len(transactions) > 0:
        return False
    else:
        return True


@view_config(renderer='../templates/transaction_types.pt',
             route_name='transaction-types-list',
             permission='view')
class ListTransactionTypes(BaseView):

    tab = 'finance'

    def __call__(self):
        return dict(transaction_types=get_transaction_types(session))

    def deletable(self, tt_id):
        session = DBSession()
        return tt_deletable(session, tt_id)


@view_config(renderer='../templates/transaction_types.pt',
             route_name='transaction-types-new',
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
        return dict(transaction_types=get_transaction_types(session),
                    msg="Transaction type has been added to the list.")


@view_config(renderer='../templates/transaction_types.pt',
             route_name='transaction-types-save',
             permission='edit')
class SaveTransactionType(BaseView):

    tab = 'applicants'

    def __call__(self):
        session = DBSession()
        tt_id = self.request.matchdict['tt_id']
        name = self.request.matchdict['name']
        tt = get_transaction_type(session, tt_id)
        tt.name = name
        tt.validate()
        return dict(transaction_types=get_transaction_types(session),
                    msg="Transaction Type has been saved.")


@view_config(renderer='../templates/transaction_types.pt',
             route_name='transaction-types-delete',
             permission='edit')
class DeleteTransactionType(BaseView):

    tab = 'applicants'

    def __call__(self):
        session = DBSession()
        tt_id = self.request.matchdict['tt_id']
        tt = get_transaction_type(session, tt_id)
        if tt_deletable(session, tt_id):
            session.delete(tt)
            session.flush()
            return dict(transaction_types=get_transaction_types(session),
                        msg="Transaction type has been removed from list.")
        else:
            return dict(transaction_types=get_transaction_types(session),
                        msg="Can't remove transaction type: transactions"\
                            " refer to it.")

