from pyramid.view import view_config
from sqlalchemy import distinct, desc

from datetime import datetime
import calendar

from members.models.workgroups import Workgroup
from members.models.member import Member
from members.models.setup import DBSession, get_connection
from members.models.shift import Shift
from members.models.task import Task
from members.models.others import Order, get_order_label
from members.views.base import BaseView


def get_possible_members(session):
    return session.query(Member)\
            .filter(Member.mem_active==True)\
            .order_by(Member.mem_fname)\
            .all()


def get_wg(session, request):
    ''' make a WorkGroup object, use request if possible '''
    if (request and request.matchdict.has_key('wg_id') and
            request.matchdict['wg_id'] != '-1'):
        wg = session.query(Workgroup).get(request.matchdict['wg_id'])
        if wg:
            wg.exists = True
    else:
        wg = Workgroup('', '')
    return wg


def fill_wg_from_request(wg, request):
    '''overwrite workgroup properties from request'''
    if request and wg:
        for attr in ['name', 'desc', 'leader_id']:
            if request.params.has_key(attr):
                wg.__setattr__(attr, request.params[attr])
    return wg


@view_config(renderer='../templates/edit-workgroup.pt',
             route_name='new_workgroup',
             permission='edit')
class NewWorkgroupView(BaseView):

    tab = 'workgroups'

    def __call__(self):
        self.possible_members = get_possible_members(DBSession())
        return dict(wg = Workgroup('', ''), msg="You're about to make a new workgroup.")


@view_config(renderer='../templates/workgroup.pt',
             route_name='workgroup',
             permission='view')
class WorkgroupView(BaseView):

    tab = 'workgroups'

    def __call__(self):
        if self.request.params.has_key('msg'):
            msg = self.request.params['msg']
        else:
            msg = ''

        session = DBSession()
        wg = get_wg(session, self.request)
        if not wg:
            raise Exception(msg+" No workgroup with id %s" % self.request.matchdict['wg_id'])

        self.user_is_wgleader = wg.leader_id == self.user.mem_id

        # look up the order and then the shifts of this group in that order
        order_header = get_connection().execute("""SELECT * FROM order_header;""")
        order_id = self.request.params.has_key('order_id') and int(self.request.params['order_id'])\
                   or list(order_header)[0].ord_no

        self.order = session.query(Order).get((order_id, get_order_label(order_id)))
        self.orders = session.query(Order.id, Order.label).distinct().order_by(desc(Order.id))
        shifts = session.query(Shift).filter(Shift.wg_id==wg.id)\
                                     .filter(Shift.order_id==order_id)\
                                          .all()
        self.tasks = [t for t in wg.tasks if t.active]

        return dict(wg=wg, shifts=shifts, msg=msg)


@view_config(renderer='../templates/edit-workgroup.pt',
             route_name='workgroup-edit',
             permission='edit')
class WorkgroupEditView(BaseView):

    tab = 'workgroups'

    def __call__(self):
        session = DBSession()
        wg = get_wg(session, self.request)
        if not wg:
            return dict(wg=None, msg="No workgroup with %d" % self.request.matchdict['wg_id'])

        self.possible_members = get_possible_members(session)
        if self.request.params.has_key('action'):
            action = self.request.params['action']
            if action == "save":
                wg = fill_wg_from_request(wg, self.request)
                if self.request.params.has_key('wg_members'):
                    wg.members = []
                    for mid in self.request.POST.getall('wg_members'):
                        m = session.query(Member).get(mid)
                        wg.members.append(m)
                    wg_leader_ids = [m for m in wg.members if m.mem_id == wg.leader_id]
                    # make sure leaders are members
                    if len(wg_leader_ids) == 0:
                        wg.members.append(session.query(Member).get(wg.leader_id))
                session.add(wg) # necessary if new
                return dict(wg=wg, msg='Workgroup has been saved.')

            elif action == 'delete':
                wg_name = wg.name
                session.delete(wg)
                return dict(wg = None, msg='Workgroup %s has been deleted.' % wg.name)

            elif "task" in action:
                msg = ''
                if action == 'add-task':
                    task = Task(self.request.params['task_label'], wg.id)
                    wg.tasks.append(task)
                    session.add(task)
                    msg = 'Added task.'
                elif action == 'toggle-task-activity':
                    task = session.query(Task).get(self.request.params['task_id'])
                    task.active = not task.active
                    msg = 'Changed activity status of the task.'
                elif action == 'delete-task':
                    task = session.query(Task).get(self.request.params['task_id'])
                    shifts = session.query(Shift).filter(Shift.task_id==task.id).all()
                    if len(shifts) == 0:
                        session.delete(task)
                        msg = 'Deleted task.'
                    else:
                        msg = 'Cannot delete task, as there are shifts in the history with this task.'
                # committing, so tasks are fresh
                import transaction
                transaction.commit()
                self.possible_members = get_possible_members(session)
                return dict(wg = get_wg(session, self.request), msg = msg)
        return dict(wg=wg, msg='')



@view_config(renderer='../templates/list-workgroups.pt', route_name='workgrouplist')
class WorkgrouplistView(BaseView):

    tab = 'workgroups'

    def __call__(self):
        dbsession = DBSession()
        wg_query = dbsession.query(Workgroup)

        # ordering
        # key is what the outside world see, value is what SQLAlchemy uses
        order_idxs = {'id': Workgroup.id, 'name': Workgroup.name}
        order_by = 'id'
        if self.request.params.has_key('order_by')\
          and order_idxs.has_key(self.request.params['order_by']):
            order_by = self.request.params['order_by']
        order_alt = (order_by=='id') and 'name' or 'id'
        wg_query = wg_query.order_by(order_idxs[order_by])

        return dict(workgroups=wg_query.all(), msg='', order_by=order_by, order_alt=order_alt, came_from='/workgroups')


