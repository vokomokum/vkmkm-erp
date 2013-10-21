from pyramid.view import view_config

import os
import datetime
from sqlalchemy import desc

from members.models.base import DBSession
from members.models.todo import Todo
from members.models.member import Member
from members.models.orders import Order
from members.models.transactions import Transaction
from members.models.transactions import get_ttypeid_by_name
from members.models.workgroups import Workgroup
from members.models.shift import Shift
from members.views.base import BaseView
from members.utils.misc import ascii_save
from members.utils.misc import get_settings


@view_config(renderer='../templates/home.pt', route_name='home')
class HomeView(BaseView):

    def __call__(self):
        session = DBSession()
        self.show_all = False
        if 'show-all-todos' in self.request.params:
            if self.request.params['show-all-todos'] == '1'\
               and self.user.mem_admin:
                self.show_all = True
        if self.logged_in:
            todos = get_todos(session, self.user, self.show_all)
            graphs = get_graphs()
        else:
            todos = graphs = []
        return dict(todos=todos, graphs=graphs)


def get_todos(session, user, show_all):
    '''
    Go through a list of cases to find current TODOs for this user.
    If show_all is true, find all TODOs system-wide
    '''
    todos = []
    all_members = session.query(Member).all()
    act_members = [m for m in all_members if m.mem_active]
    now = datetime.datetime.now()
    def df(i):
        return unicode(i).rjust(2, '0')
    

    # ---- Todos for every user:
    # negative balance
    if user.balance < 0:
        todos.append(Todo(msg='You have a negative balance of {}.'\
                             .format(round(user.balance, 2)),
                          wg='Finance',
                          link_act='member/{}'.format(user.mem_id),
                          link_txt='See the transaction list on your profile.',
                          link_title='You should transfer the missing amount.'))
    # shift user is assigned to
    ass_shifts = session.query(Shift)\
                        .filter(Shift.mem_id == user.mem_id)\
                        .filter(Shift.state == 'assigned')\
                        .order_by(Shift.year, Shift.month).all()
    for s in ass_shifts:
        todos.append(Todo(msg='You are assigned for a shift in "{}" on ({}) '\
                              'in {}/{}.'.format(s.workgroup, 
                                            s.day and s.day or 'any day',
                                            df(s.month), df(s.year)),
                              wg=s.workgroup.name,
                              link_act='workgroup/{}/shifts/{}/{}'\
                                            .format(s.wg_id, s.year, s.month),
                              link_txt='Shift schedule.',
                              link_title="Don't forget :)"))

    # ---- Workgroup Finance:
    if 'Finance' in [w.name for w in user.workgroups] or show_all:
        for m in [m for m in all_members if m.balance < 0]:
            todos.append(Todo(msg='Member {} has a negative balance of EUR {}.'\
                                 .format(ascii_save(m.fullname),
                                        round(m.balance, 2)),
                              wg='Finance',
                              link_act='member/{}'.format(m.mem_id),
                              link_txt='See member profile.',
                              link_title='You should contact the member and '\
                                 'tell them to transfer the missing amount.'))
   
        nov12 = datetime.datetime(2012, 11, 1)
        orders = session.query(Order).order_by(desc(Order.completed)).all()
        new_orders = [o for o in orders if str(o.completed) != ''\
                                        and str(o.completed) > str(nov12)]
        for no in new_orders:
            charges_made = session.query(Transaction)\
                                .filter(Transaction.ord_no == no.id).count()
            if charges_made == 0:
                todos.append(Todo(msg='Order "{}" has yet to be charged.'\
                                       .format(no.label),
                                  wg='Finance',
                                  link_act='charge-order/{}'.format(no.id),
                                  link_txt='Charge members now.',
                                  link_title='There have been no charges made '\
                                    'for this order to members. Clicking this '\
                                    'link will show you a list of charges '\
                                    'that should be made and you can then '\
                                    'confirm to actually make them.'))
            else:
                settings = get_settings()
                order_mail_folder = '{}/order-charges/{}'\
                        .format(settings['vokomokum.mail_folder'], no.id)
                # we might have already sent a mail about firt-time orderers
                if not os.path.exists(order_mail_folder)\
                   or len(os.listdir(order_mail_folder)) <= 1:
                    todos.append(Todo(msg='Members have not gotten mail about '\
                                          'charges for order "{}".'.format(no.label),
                                  wg='Finance',
                                  link_act='mail-order-charges/{}'.format(no.id),
                                  link_txt='Email members now.',
                                  link_title='There have been charges made '\
                                    'for this order to members. If these charges seem '\
                                    'to be correct, you can inform them what they '\
                                    'should pay.'))


    # ---- Workgroup Membership:
    if 'Membership' in [w.name for w in user.workgroups] or show_all:
        # Members without a workgroup
        for m in [am for am in act_members if len(am.workgroups) == 0]:
            # check if they ordered
            mt = session.query(Transaction)\
                .filter(Transaction.mem_id == m.mem_id)\
                .filter(Transaction.ttype_id == \
                        get_ttypeid_by_name('Order Charge')).first()
            if mt:
                todos.append(Todo(msg='Member {} has ordered but is still '\
                                      'without a workgroup.'\
                                      .format(ascii_save(m.fullname)),
                                  wg='Membership',
                                  link_act='member/{}'.format(m.mem_id),
                                  link_txt='See member profile.',
                                  link_title='You should contact the member and '\
                                   'discuss which openings he/she would '\
                                   'like. If they refuse, inactivate him/her.'))
    
    # ---- Todos for coordinators in general:
    # unfilled shifts
    wgs = user.led_workgroups
    if show_all:
        wgs = session.query(Workgroup).all()
    for wg in wgs:
        open_shifts = session.query(Shift)\
                             .filter(Shift.wg_id == wg.id)\
                             .filter(Shift.state == 'open')\
                             .order_by(Shift.year, Shift.month).all()
        for s in open_shifts: 
            todos.append(Todo(msg='Open shift in group "{}" in {}/{}.'\
                                  .format(s.workgroup, df(s.month), df(s.year)),
                              wg=s.workgroup,
                              link_act='workgroup/{}/shifts/{}/{}'\
                                  .format(s.wg_id, df(s.year), df(s.month)),
                              link_txt='Shift schedule.',
                              link_title='Go to the shift schedule and sign '\
                                       'someone up, or mail group members .'\
                                       'to find a volunteer.'))

        # shifts to check upon
        ass_shifts = session.query(Shift)\
                            .filter(Shift.wg_id == wg.id)\
                            .filter(Shift.state == 'assigned')\
                            .order_by(Shift.year, Shift.month).all()
        for s in [s for s in ass_shifts\
                  if s.month < now.month or s.year < now.year]:
            todos.append(Todo(msg='Group "{}": Please write off shift by {} ({}), '\
                                  'in {}/{}.'.format(s.workgroup, 
                                        ascii_save(s.member.fullname), 
                                        s.day and s.day or 'any day',
                                        df(s.month), df(s.year)),
                              wg=s.workgroup.name,
                              link_act='workgroup/{}/shifts/{}/{}'\
                                            .format(s.wg_id, s.year, s.month),
                              link_txt='Shift schedule.',
                              link_title='Go to the shift schedule and put '\
                                  'the shift in "worked" or "no-show" mode.'))
        
    return todos

#TODO: 
# - Membership: no-show shifts?
#               late payments?
#               list all current applicants

def get_graphs():
    graphs = []
    settings = get_settings()
    gfolder = settings['vokomokum.graph_folder']
    omp_path = '{}/orders_money_and_people.json'.format(gfolder)
    if os.path.exists(omp_path):
        gfile = open(omp_path, 'r')
        graphs.append(gfile.read())
    return graphs
 
