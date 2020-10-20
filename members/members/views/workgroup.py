from pyramid.view import view_config
from sqlalchemy import asc, desc

from datetime import datetime

from members.models.workgroups import Workgroup, get_wg
from members.models.member import Member
from members.models.base import DBSession
from members.views.base import BaseView


def get_possible_members(session, wg):
    ''' get possible members for a workgroup '''
    q1 = session.query(Member).filter(Member.mem_active == True)
    wgmids = [m.mem_id for m in wg.members]
    q2 = session.query(Member).filter(Member.mem_id.in_(wgmids))
    return q1.union(q2).order_by(Member.mem_fname).all()


def fill_wg_from_request(wg, request, session):
    '''overwrite workgroup properties from request'''
    if request and wg:
        for attr in ['name', 'desc', 'required_members']:
            if attr in request.params:
                val = request.params[attr]
                if attr == "required_members":
                    val = int(val)
                wg.__setattr__(attr, val)
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
            if not m in wg.members:  # avoid duplicates
                wg.members.append(m)
    return wg


@view_config(renderer='../templates/edit-workgroup.pt',
             route_name='workgroup-new',
             permission='edit')
class NewWorkgroupView(BaseView):

    tab = 'work'

    def __call__(self):
        wg = Workgroup()
        self.possible_members = get_possible_members(DBSession(), wg)
        return dict(wg=wg, msg="You're about to make a new workgroup.")


@view_config(renderer='../templates/workgroup.pt',
             route_name='workgroup',
             permission='view')
class WorkgroupView(BaseView):

    tab = 'work'

    def __call__(self):
        if 'msg' in self.request.params:
            msg = self.request.params['msg']
        else:
            msg = ''

        session = DBSession()
        wg = get_wg(session, self.request)
        self.user_is_wgleader = self.user in wg.leaders

        return dict(wg=wg, msg=msg, now=datetime.now())


@view_config(renderer='../templates/edit-workgroup.pt',
             route_name='workgroup-edit',
             permission='edit')
class EditWorkgroupView(BaseView):

    tab = 'work'

    def __call__(self):
        session = DBSession()
        wg = get_wg(session, self.request)
        req = self.request

        self.possible_members = get_possible_members(session, wg)
        if 'action' in req.params:
            action = req.params['action']
            if action == "save":
                old_name = wg.name
                uwgs = [w.name for w in self.user.workgroups]
                wg = fill_wg_from_request(wg, req, session)
                if wg.exists and not wg.name == old_name\
                   and not 'Systems' in uwgs:
                    raise Exception('Only members of Systems can change the'\
                                    ' name of an existing workgroup, because'\
                                    ' it changes the email addresses of the'\
                                    ' group.')
                wg.validate()
                if not wg.exists:
                    session.add(wg)
                    session.flush() # flushing manually so the wg gets an ID
                    return self.redirect('/workgroup/%d?msg='\
                                         'Workgroup was created.' % wg.id)
                return dict(wg=wg, msg='Workgrup has been saved.')

            elif action == 'toggle-active':
                wg = get_wg(session, self.request)
                self.confirm_toggle_active = True
                return dict(wg=wg)
            elif action == 'toggle-active-confirmed':
                wg.active = not wg.active
                msg='Workgroup {} is now {}active.'.\
                    format(wg.name, {False:'in', True:''}[wg.active])
                return dict(wg=wg, msg=msg)

        return dict(wg=wg, msg='')


@view_config(renderer='../templates/list-workgroups.pt',
             route_name='workgroup-list')
class ListWorkgroupView(BaseView):

    tab = 'work'

    def __call__(self):
        dbsession = DBSession()
        wg_query = dbsession.query(Workgroup)

        # -- inactive workgroups? --
        show_inactive = True
        if not 'include_inactive' in self.request.params\
           or not self.request.params['include_inactive']:
            show_inactive = False
            wg_query = wg_query.filter(Workgroup.active == True)


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
        workgroups = wg_query.all()
        self.wg_count = len(workgroups)
        return dict(workgroups=workgroups, msg=msg,
                    order_name_choice=order_name_choice,
                    show_inactive=show_inactive)
