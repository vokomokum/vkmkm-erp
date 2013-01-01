from sqlalchemy import Table, Column
from sqlalchemy import Integer, Unicode, Boolean, Numeric, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey

from pyramid.security import Allow, DENY_ALL

import datetime
import pytz

from base import Base, VokoValidationError, DBSession
from member import Member
from supplier import Wholesaler, VersSupplier
from orders import Order
from members.utils.misc import ascii_save
from members.utils.misc import month_info


# These types have special meaning and a re therefore protected
reserved_ttype_names = ['Membership Fee', 'Order Charge']


class TransactionType(Base):
    __tablename__ = 'transaction_types'

    id = Column(Integer, primary_key=True)
    # TODO: comment?
    name = Column(Unicode(100), unique=True)
    # Transactions of this type are either all positive or all negative
    pos_neg = Column(Unicode(3), default=u'---')
    # Transactions of this type are between Vokomokum and its members or its
    # suppliers
    mem_sup = Column(Unicode(4), default=u'memb')

    __acl__ = [(Allow, 'group:admins', ('view', 'edit')),
               (Allow, 'group:finance', ('view', 'edit')),
               (Allow, 'group:members', 'view'),
               DENY_ALL]

    def __init__(self, request=None, name='', pos_neg='---', mem_sup='mem'):
        ''' receiving request makes this class a factory for views '''
        self.name = name
        self.pos_neg = pos_neg
        self.mem_sup = mem_sup

    def __repr__(self):
        return self.name

    @property
    def name_js(self):
        ''' Name save to use in js '''
        return self.name.replace("'", "\\'")

    def validate(self):
        ''' validate if this object is valid, raise exception otherwise '''
        if self.name == '':
            raise VokoValidationError('A transaction type needs a name.')
        if not self.pos_neg in ('pos', 'neg', '---'):
            raise VokoValidationError('The field pos_neg should be "pos", "neg"'\
                                      ' or "---".')
        if not self.mem_sup in ('memb', 'whol', 'vers', 'none'):
            raise VokoValidationError('The field mem_sup should be "memb" or'\
                                      ' "whol" or "vers" or "none".')

    @property
    def locked(self):
        ''' Transaction type can't be removed if transactions use it ''' 
        return len(self.transactions) > 0

    @property
    def reserved(self):
        '''
        Returns True if the name of this transaction type cannot be changed
        '''
        return self.name in reserved_ttype_names


def get_ttypeid_by_name(name):
    session = DBSession()
    tt = session.query(TransactionType)\
                .filter(TransactionType.name == name).first()
    return tt.id 


class Transaction(Base):
    __tablename__ = 'transactions'
    
    id = Column(Integer, primary_key=True)
    ttype_id = Column(Integer, ForeignKey('transaction_types.id'), nullable=False)
    ttype = relationship(TransactionType, backref='transactions')
    amount = Column(Numeric)
    mem_id = Column(Integer, ForeignKey('members.mem_id'), nullable=False)
    member = relationship(Member, backref='transactions')
    whol_id = Column(Integer, ForeignKey('wholesaler.wh_id'), nullable=False)
    wholesaler = relationship(Wholesaler)
    vers_id = Column(Integer, ForeignKey('vers_suppliers.id'), nullable=False)
    vers_supplier = relationship(VersSupplier)
    comment = Column(Unicode(500))
    ord_no = Column(Integer, ForeignKey('wh_order.ord_no'), nullable=True)
    order = relationship(Order, backref='transactions')
    date = Column(DateTime)
    late = Column(Boolean, default=False)

    __acl__ = [(Allow, 'group:admins', ('view', 'edit')),
               (Allow, 'group:finance', ('view', 'edit')),
               DENY_ALL]

    def __init__(self, request=None, ttype_id=None, amount=0, mem_id=None,
                 whol_id=None, vers_id=None, comment='', ord_no=None,
                 date=datetime.datetime.now(), late=False):
        self.ttype_id = ttype_id
        self.amount = amount
        self.mem_id = mem_id
        self.whol_id = whol_id
        self.vers_id = vers_id
        self.comment = comment
        self.ord_no = ord_no
        self.date = date
        self.late = late

    def __repr__(self):
        fromto = {True: 'from', False: 'to'}[self.amount > 0]
        if self.ttype.mem_sup == 'memb':
            partner = ascii_save(self.member.fullname)
        elif self.ttype.mem_sup == 'whol':
            partner = ascii_save(self.wholesaler.wh_name)
        elif self.ttype.mem_sup == 'vers':
            partner = ascii_save(self.vers_supplier.name)
        else:
            partner = 'Other'
        
        return "EUR {} {} {} [{}]".format(round(self.amount, 2), fromto,
                                          partner, self.ttype)

    def locked(self):
        '''
        Transactions can't be removed by the app if they were created
        by the system based on existing data (for now: Order Charge) ''' 
        if self.ttype.name == 'Order Charge':
            return True
        return False

    def validate(self):
        ''' validate if this object is valid, raise exception otherwise '''
        try:
            _ = float(self.amount)
        except Exception, e:
            raise VokoValidationError('The amount is not numeric - maybe it '\
                                      'contains illegal characters (please '\
                                      'write numbers with a dot, e.g. "3.89").')
        if not self.ttype:
            raise VokoValidationError('A transaction needs a type.')
        if self.ttype.mem_sup == 'memb' and not self.member:
            raise VokoValidationError('A transaction of type {} needs a '\
                                      'member.'.format(self.ttype))
        if self.ttype.mem_sup == 'whol' and not self.wholesaler:
            raise VokoValidationError('A transaction of type {} needs a '\
                                      'wholesaler.'.format(self.ttype))
        if self.ttype.mem_sup == 'vers' and not self.vers_supplier:
            raise VokoValidationError('A transaction of type {} needs a '\
                                      'vers supplier.'.format(self.ttype))
        if self.ttype.pos_neg == 'pos' and self.amount < 0:
            raise VokoValidationError('A transaction of this type should by '\
                                      'its definition be benefitting Vokomokum '\
                                      'and thus be positive.')
        if self.ttype.pos_neg == 'neg' and self.amount > 0:
            raise VokoValidationError('A transaction of this type should by '\
                                      'its definition represent something that '\
                                      'Vokomokum gives out or pays and thus '\
                                      'and thus be negative.')
        if (self.member and self.wholesaler) or\
           (self.member and self.vers_supplier):
            raise VokoValidationError('This transaction should not link to '\
                                      'both a member and a supplier.')
        if self.ttype.name == 'Order Charge' and not self.order:
            raise VokoValidationError('This Order Charge has no connected order.')
        if self.ttype.name != 'Order Charge' and self.order:
            raise VokoValidationError('This transaction has a connected order, '\
                                      'but is not an Order Charge.')
           

def get_transaction_sums(year, month, ttype):
    '''
    Get the sum of transaction count and money amounts of this type in this month.
    If month is None, get for the whole year.
    If type is None, get the sum for all types.
    '''
    if not month:
        start_month = 1
        end_month = 12
    else:
        start_month = end_month = month
    tz = pytz.timezone('Europe/Amsterdam')
    end_month_date = datetime.date(year, end_month, 1)
    em_info = month_info(end_month_date) 
    first = tz.localize(datetime.datetime(year, start_month, 1, 0, 0, 0))
    last = tz.localize(datetime.datetime(year, end_month, 
                                         em_info.days_in_month, 23, 59, 59))
    query_filter = " WHERE date >= '{}' AND date <= '{}'".format(first, last)
    if ttype:
        query_filter += " AND ttype_id = {}".format(ttype.id)
    query_a = "SELECT sum(amount) FROM transactions {}".format(query_filter)
    query_c = "SELECT count(*) FROM transactions {}".format(query_filter)
    amount = list(DBSession().connection().engine.execute(query_a))[0][0]
    if not amount:
        amount = 0.0
    count = list(DBSession().connection().engine.execute(query_c))[0][0]
    return {'count': count, 'amount': round(amount, 2)}

 
