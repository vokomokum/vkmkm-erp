from pyramid.view import view_config
from sqlalchemy import distinct, desc, asc

import datetime
import pytz

from members.models.base import DBSession
from members.views.base import BaseView
from members.models.member import Member, get_member
from members.models.supplier import Wholesaler, VersSupplier
from members.models.transactions import Transaction, TransactionType
from members.models.transactions import get_transaction_sums
from members.models.orders import Order
from members.utils.misc import month_info


def get_transaction(session, t_id):
    return session.query(Transaction).get(t_id)


class BaseTransactionView(BaseView):

    @property
    def members(self):
        session = DBSession()
        return session.query(Member).order_by(asc(Member.mem_id)).all()
    
    @property
    def wholesalers(self):
        session = DBSession()
        return session.query(Wholesaler).all()

    @property
    def vers_suppliers(self):
        session = DBSession()
        return session.query(VersSupplier).all()

    @property
    def transaction_types(self):
        session = DBSession()
        return session.query(TransactionType).all()

    @property
    def orders(self):
        ''' return a dict, with order IDs as keys and labels as values'''
        session = DBSession()
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
        now = datetime.datetime.now()
        if self.month == now.month:
            self.today = now.day
        else:
            self.today = 1

        tz = pytz.timezone('Europe/Amsterdam')
        first = tz.localize(datetime.datetime(self.year, self.month, 1, 0, 0, 0))
        last = tz.localize(datetime.datetime(self.year, self.month, 
                                 self.month_info.days_in_month, 23, 59, 59))
        transactions = session.query(Transaction)
        # fitering by type
        self.ttid = None
        if 'ttype' in self.request.params:
            if self.request.params['ttype'] != '':
                self.ttid = int(self.request.params['ttype'])
                transactions = transactions.filter(Transaction.ttype_id == self.ttid)     
        # ordering
        order_by = Transaction.date
        self.order_criterion = 'date'
        if 'order_by' in self.request.params:
            if self.request.params['order_by'] == 'date':
                order_by = Transaction.date
            if self.request.params['order_by'] == 'amount':
                order_by = Transaction.amount
            if self.request.params['order_by'] == 'type':
                order_by = Transaction.ttype_id
            self.order_criterion = self.request.params['order_by']
        transactions = transactions.order_by(order_by)
        self.order_criteria = ('date', 'amount', 'type')
        #    .filter(Transaction.date >= first and Transaction.date <= last)\
        #    .order_by(Transaction.id)\
        #    .all()
        # This is here because the filter above doesn't work for me
        # I only get pure string comparison to work, which works for now
        transactions = [t for t in transactions\
                if (str(t.date.tzinfo and t.date or tz.localize(t.date)) >= str(first))\
                and (str(t.date.tzinfo and t.date or tz.localize(t.date)) <= str(last))]
        self.sums = {}
        for ttype in self.transaction_types:
            self.sums[ttype.name] =\
                         get_transaction_sums(self.year, self.month, ttype)
        self.overall = get_transaction_sums(self.year, self.month, None)

        return dict(msg=msg, transactions=transactions)


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
        member = session.query(Member).get(params['mem_id'])
        transaction.member = member
        transaction.whol_id = params['wh_id']
        transaction.vers_id = params['vers_id']
        transaction.comment = params['comment']
        if 'ord_no' in params and not params['ord_no'] in ('', '--'):
            transaction.ord_no = int(params['ord_no'])
        if 'late' in params:
            transaction.late = bool(params['late'])

        day = int(params['day'])
        adate = datetime.date(year, month, day)
        transaction.date = adate
        transaction.validate()
        session.add(transaction)
        session.flush()
        return self.redir_to_list(year, month, 'Transaction "{}" has been '\
                        'added to the list.'\
                        .format(str(transaction)))


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
                msg = 'No member was selected.'
            else:
                transaction.member = get_member(session, self.request)
                msg = u'Transaction got a new member:{}'\
                        .format(transaction.member)
        if action == "setwholesaler":
            if not 'wh_id' in self.request.params:
                msg = 'No wholesaler was selected.'
            else:
                transaction.whol_id = self.request.params['wh_id']
                msg = u'Transaction got a new wholesaler.'
        if action == "setverssupplier":
            if not 'vers_id' in self.request.params:
                msg = 'No vers supplier was selected.'
            else:
                transaction.vers_id = self.request.params['vers_id']
                msg = u'Transaction got a new vers supplier.'
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



@view_config(renderer='../templates/transaction_year_overview.pt',
             route_name='transactions-year-overview',
             permission='view')
class TransactionsYearOverview(BaseTransactionView):

    tab = 'finance'

    def __call__(self):
        session = DBSession()
        self.year = int(self.request.matchdict['year'])
        start_sec = datetime.datetime(self.year, 1, 1, 0, 0, 0)
        end_sec = datetime.datetime(self.year, 12, 31, 23, 59, 59)
        #self.start_month_info = month_info(start_date) 

        tz = pytz.timezone('Europe/Amsterdam')
        first = tz.localize(start_sec)
        last = tz.localize(end_sec)
        self.all_sums = {}
        self.month_sums = {}
        self.type_sums = {}
        for ttype in self.transaction_types:
            self.type_sums[ttype.name] = 0.0
        self.sum_overall = 0.0
        self.months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug',
                       'Sep', 'Oct', 'Nov', 'Dec']
        for month in self.months:
            self.all_sums[month] = {}
            self.month_sums[month] = 0.0
            for ttype in self.transaction_types:
                smtt = get_transaction_sums(self.year, self.months.index(month)+1, ttype)['amount']
                self.all_sums[month][ttype.name] = smtt
                self.month_sums[month] += smtt
                self.type_sums[ttype.name] += smtt
                self.sum_overall += smtt 
        
        return dict(msg='')


