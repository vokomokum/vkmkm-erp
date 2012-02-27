from pyramid.view import view_config
from sqlalchemy import distinct, asc, desc

from members.models.workgroups import Workgroup
from members.models.member import Member
from members.models.base import DBSession
from members.models.shift import Shift
from members.models.task import Task
from members.models.others import Order, get_order_label
from members.views.base import BaseView


def get_possible_members(session):
    ''' get possible members for a(ny) workgroup '''
    return session.query(Member)\
            .filter(Member.mem_active==True)\
            .order_by(Member.mem_fname)\
            .all()

def get_wg(session, request):
    ''' make a Workgroup object, use ID from request if possible '''
    wg = Workgroup('', '')
    if request.matchdict.has_key('wg_id'):
        wg_id = request.matchdict['wg_id']
        if wg_id == 'new':
            return wg
        try:
            wg_id = int(wg_id)
        except ValueError:
            raise Exception("No workgroup with ID %s" % wg_id)
        wg = session.query(Workgroup).get(wg_id)
        if wg:
            wg.exists = True
        else:
            raise Exception("No workgroup with ID %s" % wg_id)
    return wg


def fill_wg_from_request(wg, request, session):
    '''overwrite workgroup properties from request'''
    if request and wg:
        for attr in ['name', 'desc']:
            if request.params.has_key(attr):
                wg.__setattr__(attr, request.params[attr])
        if request.POST.has_key('wg_leaders'):
            wg.leaders = []
            for mid in request.POST.getall('wg_leaders'):
                m = session.query(Member).get(mid)
                if m:
                    wg.leaders.append(m)
        if request.params.has_key('wg_members'):
            wg.members = []
            for mid in request.POST.getall('wg_members'):
                m = session.query(Member).get(mid)
                wg.members.append(m)
        # make sure leaders are also members
        for m in wg.leaders:
            wg.members.append(m)
    return wg


@view_config(renderer='../templates/edit-workgroup.pt',
             route_name='workgroup-new',
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

        self.user_is_wgleader = self.user in wg.leaders

        # look up the order and then the shifts of this group in that order
        order_header = session.execute("""SELECT * FROM order_header;""")
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

        self.possible_members = get_possible_members(session)
        if self.request.params.has_key('action'):
            action = self.request.params['action']
            if action == "save":
                wg = fill_wg_from_request(wg, self.request, session)
                wg.validate()
                if not wg.exists:
                    session.add(wg)
                    session.flush() # flushing manually so the wg gets an ID
                    return self.redirect('/workgroup/%d?msg=Workgroup was created.' % wg.id)
                return dict(wg=wg, msg='Workgrup has been saved.')

            elif action == 'delete':
                wg = get_wg(session, self.request)
                self.confirm_deletion = True
                return dict(wg=wg)
            elif action == 'delete-confirmed':
                tasks = session.query(Task).filter(Task.wg_id==wg.id).all()
                for task in tasks:
                    shifts = session.query(Shift).filter(Shift.task_id==task.id).all()
                    if len(shifts) == 0:
                        session.delete(task)
                    else:
                        raise Exception('Cannot delete workgroup, as there are shifts in the history for the task "%s".' % str(task))
                session.delete(wg)
                return dict(wg=None, msg='Workgroup %s has been deleted.' % wg.name)

            elif "task" in action:
                msg = ''
                if action == 'add-task':
                    task = Task(self.request.params['task_label'], wg.id)
                    task.validate(wg.tasks)
                    wg.tasks.append(task)
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
                self.possible_members = get_possible_members(session)
                return dict(wg = get_wg(session, self.request), msg = msg)
        return dict(wg=wg, msg='')



@view_config(renderer='../templates/list-workgroups.pt', route_name='workgroup-list')
class WorkgrouplistView(BaseView):

    tab = 'workgroups'

    def __call__(self):
        dbsession = DBSession()
        wg_query = dbsession.query(Workgroup)

        # show msg
        if self.request.params.has_key('msg'):
            msg = self.request.params['msg']
        else:
            msg = ''

        # -- ordering --
        # direction
        odir = asc
        if self.request.params.has_key('order_dir')\
           and self.request.params['order_dir'] == 'desc':
            odir = desc
        # ordering choice
        order_name_choice = 'asc'
        if odir == asc:
            order_name_choice = 'desc'

        wg_query = wg_query.order_by(odir('id'))
        return dict(workgroups=wg_query.all(), msg=msg,
                    order_name_choice=order_name_choice, came_from='/workgroups')


