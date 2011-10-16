import transaction
from pyramid.view import view_config

from datetime import datetime
import calendar

from members.models.workgroups import Workgroup
from members.models.member import Member
from members.models.setup import DBSession, get_connection
from members.models.shift import Shift
from members.models.task import Task
from members.models.others import Order
from members.views.base import BaseView


def get_possible_members(session):
    return session.query(Member).filter(Member.mem_active==True).all()


def mkworkgroup(session, request=None, wg_id=None):
    ''' make a WorkGroup object, use request if possible '''
    if (request and request.matchdict.has_key('wg_id') and
            request.matchdict['wg_id'] != 'fresh') or wg_id:
        if not wg_id:
            wg_id = request.matchdict['wg_id']
        wg = session.query(Workgroup).get(wg_id)
        if wg:
            wg.exists = True
    else:
        wg = Workgroup('', '')
    if request and wg:
        # overwrite workgroup properties from request
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

        wg_id = self.request.matchdict['wg_id']
        try:
            wg_id = int(wg_id)
        except:
            return dict(wg=None, msg=msg+'Invalid ID.')
        session = DBSession()
        wg = mkworkgroup(session, self.request, wg_id=wg_id)
        if not wg:
            #TODO: redirect to custom 404 view
            return dict(wg=None, shifts=None, msg=msg+" No workgroup with id %d" % wg_id)

        self.user_is_wgleader = wg.leader_id == self.user.id

        # look up the order and then the shifts of this group in that order
        order_header = get_connection().execute("""SELECT * FROM order_header;""")
        order_id = self.request.params.has_key('order_id') and int(self.request.params['order_id'])\
                        or list(order_header)[0].ord_no

        self.order = session.query(Order).get(order_id)
        self.orders = session.query(Order).all()

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
        print 'wg view called.'
        id = self.request.matchdict['wg_id']
        if id != 'fresh':
            try:
                id = int(id)
            except:
                return dict(m = None, msg = 'Invalid ID.')

        session = DBSession()
        wg = mkworkgroup(session, self.request)
        if not wg:
            return dict(wg=None, msg="No workgroup with id %d" % id)

        self.possible_members = get_possible_members(session)
        if not self.request.params.has_key('action'):
            return dict(wg = wg, msg='')
        else:
            action = self.request.params['action']
            if action == "save":
                if self.request.params.has_key('wg_members'):
                    wg.members = []
                    for mid in self.request.POST.getall('wg_members'):
                        m = session.query(Member).get(mid)
                        wg.members.append(m)
                try:
                    session.add(wg)
                    session.flush()
                    new_id = wg.id
                    transaction.commit()
                except Exception, e:
                    return dict(wg = None, msg=u'Something went wrong: %s' % e)
                self.possible_members = get_possible_members(session)
                return dict(wg = mkworkgroup(session, self.request, wg_id=new_id), msg='Workgroup has been saved.')

            elif action == 'delete':
                wg_name = wg.name
                try:
                    session.delete(session.query(Workgroup).get(wg.id))
                    session.flush()
                    transaction.commit()
                except Exception, e:
                    return dict(wg = None, msg=u'Something went wrong: %s' % e)
                return dict(wg = None, msg='Workgroup %s has been deleted.' % wg.name)

            elif "task" in action:
                print action, " =========================================================================="
                msg = ''
                try:
                    if action == 'add-task':
                        task = Task(self.request.params['task_label'], wg.id)
                        wg.tasks.append(task)
                        session.add(task)
                        msg = 'Added task.'
                    elif action == 'toggle-task-activity':
                        task = session.query(Task).get(self.request.params['task_id'])
                        task.active = not task.active
                        session.add(task)
                        msg = 'changed activity status of the task.'
                    elif action == 'delete-task':
                        task = session.query(Task).get(self.request.params['task_id'])
                        shifts = session.query(Shift).filter(Shift.task_id==task.id).all()
                        if len(shifts) == 0:
                            session.delete(task)
                            msg = 'Deleted task.'
                        else:
                            msg = 'Cannot delete task, as there are shifts in the history with this task.'
                    session.flush()
                    transaction.commit()
                except Exception, e:
                    #TODO: redirect to custom 404 view?
                    msg = ' Could not perform %s: %s' % (action, e)
                    #TODO: re-initiating this too often (after each commit), there must be a more elegant way
                self.possible_members = get_possible_members(session)
                return dict(wg = mkworkgroup(session, self.request), msg = msg)



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


