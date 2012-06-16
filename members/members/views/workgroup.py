from pyramid.view import view_config
from sqlalchemy import asc, desc

from datetime import datetime

from members.models.workgroups import Workgroup, get_wg
from members.models.member import Member
from members.models.base import DBSession
from members.models.shift import Shift
from members.models.task import Task
from members.models.others import Order, get_order_label
from members.views.base import BaseView


def get_possible_members(session):
    ''' get possible members for a(ny) workgroup '''
    return session.query(Member)\
            .filter(Member.mem_active == True)\
            .order_by(Member.mem_fname)\
            .all()


def fill_wg_from_request(wg, request, session):
    '''overwrite workgroup properties from request'''
    if request and wg:
        for attr in ['name', 'desc']:
            if attr in request.params:
                wg.__setattr__(attr, request.params[attr])
        if 'wg_leaders' in request.POST:
            wg.leaders = []
            for mid in request.POST.getall('wg_leaders'):
                m = session.query(Member).get(mid)
                if m:
                    wg.leaders.append(m)
        if 'wg_members' in request.params:
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
        return dict(wg=Workgroup('', ''),
                    msg="You're about to make a new workgroup.")


@view_config(renderer='../templates/workgroup.pt',
             route_name='workgroup',
             permission='view')
class WorkgroupView(BaseView):

    tab = 'workgroups'

    def __call__(self):
        if 'msg' in self.request.params:
            msg = self.request.params['msg']
        else:
            msg = ''

        session = DBSession()
        wg = get_wg(session, self.request)

        self.user_is_wgleader = self.user in wg.leaders

        # we view shifts per-month here (for now, maybe we'll get a nicer overview)
        sdate = datetime.now()
        self.month = sdate.month
        self.year = sdate.year
        if 'month' in self.request.params:
            self.month = int(self.request.params['month'])
        if 'year' in self.request.params:
            self.year = int(self.request.params['year'])
        shifts = session.query(Shift).filter(Shift.task_id == Task.id)\
                                     .filter(Task.wg_id == wg.id)\
                                     .filter(Shift.month == self.month)\
                                     .filter(Shift.year == self.year)\
                                     .all()
        self.tasks = [t for t in wg.tasks if t.active]

        return dict(wg=wg, shifts=shifts, msg=msg)


@view_config(renderer='../templates/edit-workgroup.pt',
             route_name='workgroup-edit',
             permission='edit')
class EditWorkgroupView(BaseView):

    tab = 'workgroups'

    def __call__(self):
        session = DBSession()
        wg = get_wg(session, self.request)
        req = self.request

        self.possible_members = get_possible_members(session)
        if 'action' in req.params:
            action = req.params['action']
            if action == "save":
                wg = fill_wg_from_request(wg, req, session)
                wg.validate()
                if not wg.exists:
                    session.add(wg)
                    session.flush() # flushing manually so the wg gets an ID
                    return self.redirect('/workgroup/%d?msg='\
                                         'Workgroup was created.' % wg.id)
                return dict(wg=wg, msg='Workgrup has been saved.')

            elif action == 'delete':
                wg = get_wg(session, self.request)
                self.confirm_deletion = True
                return dict(wg=wg)
            elif action == 'delete-confirmed':
                tasks = session.query(Task).filter(Task.wg_id == wg.id).all()
                for task in tasks:
                    shifts = session.query(Shift)\
                                    .filter(Shift.task_id == task.id).all()
                    if len(shifts) == 0:
                        session.delete(task)
                    else:
                        raise Exception('Cannot delete workgroup, as there '\
                                        'are shifts in the history for the '\
                                        'task "%s".' % str(task))
                session.delete(wg)
                return dict(wg=None, msg='Workgroup %s has been deleted.'\
                                          % wg.name)

            elif "task" in action:
                msg = ''
                if action == 'add-task':
                    label = req.params['task_label']
                    task = Task(label, wg.id,
                                num_people=req.params['task-no-people'])
                    task.validate(wg.tasks)
                    wg.tasks.append(task)
                    msg = 'Added task "{}".'.format(label)
                elif action == 'toggle-task-activity':
                    task = session.query(Task).get(req.params['task_id'])
                    task.active = not task.active
                    msg = 'Changed activity status of the task.'
                elif action == 'set-task-no-people':
                    task = session.query(Task).get(req.params['task_id'])
                    if 'task-no-people' in req.params:
                        task.num_people = req.params['task-no-people']
                        msg = 'Number of people for task "{}" has been set'\
                              ' (already existing shifts were not affected).'\
                              .format(task)
                elif action == 'delete-task':
                    task = session.query(Task).get(req.params['task_id'])
                    shifts = session.query(Shift)\
                                    .filter(Shift.task_id == task.id).all()
                    if len(shifts) == 0:
                        session.delete(task)
                        msg = 'Deleted task.'
                    else:
                        msg = 'Cannot delete task, as there are shifts in the '\
                              'history with this task.'
                self.possible_members = get_possible_members(session)
                return dict(wg=get_wg(session, req), msg=msg)
        return dict(wg=wg, msg='')


@view_config(renderer='../templates/list-workgroups.pt',
             route_name='workgroup-list')
class ListWorkgroupView(BaseView):

    tab = 'workgroups'

    def __call__(self):
        dbsession = DBSession()
        wg_query = dbsession.query(Workgroup)

        # show msg
        if 'msg' in self.request.params:
            msg = self.request.params['msg']
        else:
            msg = ''

        # -- ordering --
        # direction
        odir = asc
        if 'order_dir' in self.request.params\
           and self.request.params['order_dir'] == 'desc':
            odir = desc
        # ordering choice
        order_name_choice = 'asc'
        if odir == asc:
            order_name_choice = 'desc'

        wg_query = wg_query.order_by(odir('id'))
        return dict(workgroups=wg_query.all(), msg=msg,
                    order_name_choice=order_name_choice,
                    came_from='/workgroups')
