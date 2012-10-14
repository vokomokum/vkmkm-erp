from pyramid.view import view_config
from sqlalchemy import distinct, desc

import datetime

from members.models.base import DBSession
from members.views.base import BaseView
from members.models.member import Member, get_member
from members.models.transactions import Transaction, TransactionType
from members.models.others import Order
from members.utils.misc import month_info


def get_transactions(session):
    return session.query(Transaction)\
            .order_by(Transaction.id)\
            .all()

 
def get_transaction(session, t_id):
    return session.query(Transaction).get(t_id)


class BaseTransactionView(BaseView):

    @property
    def members(self):
        session = DBSession()
        return session.query(Member).all()

    @property
    def transaction_types(self):
        session = DBSession()
        return session.query(TransactionType).all()

    @property
    def orders(self):
        ''' return a dict, with order IDs as keys and labels as values'''
        session = DBSession()
        #return session.query(distinct((Order.id, Order.label)))\
        return session.query(Order)\
                    .order_by(desc(Order.completed)).all()

    def redir_to_list(self, year, month, msg=''):
        ''' redirect to list view '''
        if msg != '':
            msg = '?msg={}'.format(msg)
        return self.redirect('/transactions/{}/{}{}'.format(year, month, msg))

            
@view_config(renderer='../templates/transactions.pt',
             route_name='transactions',
             permission='view')
class EntryListTransactions(BaseTransactionView):

    def __call__(self):
        now = datetime.datetime.now()
        return self.redir_to_list(now.year, now.month) 


@view_config(renderer='../templates/transactions.pt',
             route_name='transaction-list',
             permission='view')
class ListTransactions(BaseTransactionView):

    tab = 'finance'

    def __call__(self):
        session = DBSession()
        if 'msg' in self.request.params:
            msg = self.request.params['msg']
        else:
            msg = ''
        if 'confirm-deletion-of' in self.request.params:
            self.cdo = \
                get_transaction(session,
                                self.request.params['confirm-deletion-of'])
        self.month = int(self.request.matchdict['month'])
        self.year = int(self.request.matchdict['year'])
        schedule_date = datetime.date(self.year, self.month, 1)
        self.month_info = month_info(schedule_date) 
        self.days = range(1, self.month_info.days_in_month + 1)
        return dict(msg=msg, transactions=get_transactions(session))


@view_config(renderer='../templates/transactions.pt',
             route_name='transaction-new',
             permission='edit')
class NewTransaction(BaseTransactionView):

    tab = 'finance'

    def __call__(self):
        session = DBSession()
        transaction = Transaction()
        params = self.request.params
        year = int(params['year'])
        month = int(params['month'])
        
        if params['ttype_id'] == '--':
            return self.redir_to_list(year, month, 'Please select a type.')
        ttype = session.query(TransactionType).get(params['ttype_id'])
        transaction.ttype = ttype
        transaction.amount = float(params['amount'])
        if params['mem_id'] == '--':
            return self.redir_to_list(year, month, 'Please select a member.')
        member = session.query(Member).get(params['mem_id'])
        transaction.member = member
        transaction.comment = params['comment']
        if 'ord_no' in params and params['ord_no'] != "":
            transaction.ord_no = int(params['ord_no'])
        if 'late' in params:
            transaction.late = boolean(params['late'])

        day = int(params['day'])
        adate = datetime.date(year, month, day)
        transaction.date = adate
        transaction.validate()
        session.add(transaction)
        session.flush()
        return self.redir_to_list(year, month,
                                  'Transaction "{}" has been added to '\
                                  'the list.'.format(transaction))


@view_config(renderer='../templates/transactions.pt',
             route_name='transaction-edit',
             permission='edit')
class EditTransaction(BaseTransactionView):
    '''
    Perform an action on a transaction and then redirect to the list view.
    This view can be ajaxified pretty easily.
    '''

    tab = 'finance'

    def __call__(self):
        session = DBSession()
        transaction = get_transaction(session, self.request.matchdict['t_id'])
        msg = ''
        if not transaction:
            raise Exception("No transaction with id %d"\
                            % self.request.matchdict['t_id'])
   
        action = self.request.matchdict['action']
        if action == "":
            raise Exception('No action given.')

        if action == "setttype":
            transaction.ttype = session.query(TransactionType)\
                                       .get(request.params['ttype_id'])
            msg = 'Transaction Type was updated.'
        if action == "setmember":
            if not 'mem_id' in self.request.params:
                msg = 'No member selected.'
            else:
                transaction.member = get_member(session, self.request)
                msg = u'Transaction got a new member.'
        if action == "setamount":
            amount = self.request.params['amount']
            try:
                amount = float(amount)
                msg = 'Amount was updated.'
            except:
                msg = 'Invalid amount: {}'.format(amount)
            transaction.amount = amount 
        if action == "setcomment":
            transaction.comment = self.request.params['comment'] 
            msg = "Comment was updated."
        if action == "setdate":
            adate = dateimte.now()
            adate.day = self.request.params['day']
            adate.month = self.request.params['month']
            adate.year = self.request.params['year']
            transaction.date = adate
            msg = "Date was updated."
        if action == "setlate":
            if 'late' in self.request.params:
                transaction.late = bool(self.request.params['late']) 
            else:
                transaction.late = False
            msg = "Late-status of transaction was set to {}."\
                   .format(transaction.late)
        if action == 'setorder':
            transaction.ord_no = int(params['ord_no'])
            msg = "order was set."
        transaction.validate()
        session.flush()
        return self.redir_to_list(transaction.date.year, transaction.date.month,
                                  'Transaction has been saved. {}'\
                                  .format(msg))
 

@view_config(renderer='../templates/transactions.pt',
             route_name='transaction-delete',
             permission='edit')
class DeleteTransaction(BaseTransactionView):

    tab = 'finance'

    def __call__(self):
        session = DBSession()
        t_id = self.request.matchdict['t_id']
        t = get_transaction(session, t_id)
        if t.locked():
            return self.redir_to_list(t.year, t.month, 
                                 'Cannot remove transaction "{}":'\
                                 ' It is locked.'.format(t))
        else:
            session.delete(t)
            session.flush()
            return self.redir_to_list(t.date.year, t.date.month,
                             'Transaction "{}" has been deleted.'\
                              .format(t))
