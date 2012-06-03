from __future__ import unicode_literals

from pyramid.view import view_config
from sqlalchemy import asc, desc

from members.models.member import Member, get_member
from members.models.base import DBSession
from members.views.base import BaseView
from members.views.pwdreset import send_pwdreset_request


def fill_member_from_request(member, request):
    '''overwrite member properties from request'''
    if request and member:
        # overwrite member properties from request, pwds are excluded
        for attr in [a for a in Member.__dict__.keys()\
                     if a.startswith('mem_') and not a in ['mem_id']]:
            type = str(member.__mapper__.columns._data[attr].type)
            if attr in request.params:
                v = request.params[attr]
                if type == 'BOOLEAN':
                    v = {'on': True, '': False}[v]
                member.__setattr__(attr, v)
            else:
                if type == 'BOOLEAN' and attr in member.__dict__\
                   and member.__dict__[attr] is True\
                   and 'action' in request.params\
                   and request.params['action'] == 'save':
                    member.__setattr__(attr, False)
    return member


@view_config(renderer='../templates/edit-member.pt',
             route_name='member-new',
             permission='edit')
class NewMemberView(BaseView):

    tab = 'members'

    def __call__(self):
        return dict(m=Member('', '', ''), msg='')


@view_config(renderer='../templates/member.pt',
             route_name='member',
             permission='view')
class MemberView(BaseView):

    tab = 'members'

    @property
    def user_can_edit(self):
        if self.user:
            #return self.user.mem_id == m.mem_id or self.user.mem_admin
            # for now, users cannot edit their own data, bcs sensitive
            # settings are also in the member table (e.g. membership fee paid)
            return self.user.mem_admin is True
        else:
            return False

    def __call__(self):
        m = get_member(DBSession(), self.request)
        msg = ''
        if 'msg' in self.request.params:
            msg = self.request.params['msg']
        # assigned and worked shifts
        assigned = [s for s in m.scheduled_shifts if s.state == 'assigned']
        worked = [s for s in m.scheduled_shifts if s.state == 'worked']
        return dict(m=m, msg=msg, assigned_shifts=assigned,
                    worked_shifts=worked)


@view_config(renderer='../templates/edit-member.pt',
             route_name='member-edit',
             permission='edit')
class EditMemberView(BaseView):

    tab = 'members'

    def __call__(self):
        session = DBSession()
        member = get_member(session, self.request)
        if 'action' in self.request.params:
            action = self.request.params['action']
            if action == "save":
                member = fill_member_from_request(member, self.request)
                member.validate()
                if not member.exists:
                    session.add(member)
                    session.flush() # flush manually so the member gets an ID
                    send_pwdreset_request(member, self.request.application_url,
                                          first=True)
                    return self.redirect('/member/{0:d}?msg=Member has been'\
                                         ' created and got an email to set up'\
                                         ' a password.'.format(member.mem_id))
                return dict(m=member, msg='Member has been saved.')
            elif action == 'delete':
                member = get_member(session, self.request)
                self.confirm_deletion = True
                return dict(m=member)
            elif action == 'delete-confirmed':
                session.delete(member)
                return dict(m=None,
                            msg='Member {} has been deleted.'.format(member))
        return dict(m=member, msg='')


@view_config(renderer='../templates/list-members.pt', route_name='member-list')
class ListMemberView(BaseView):

    tab = 'members'

    def __call__(self):
        dbsession = DBSession()
        m_query = dbsession.query(Member)

        # show msg
        if 'msg' in self.request.params:
            msg = self.request.params['msg']
        else:
            msg = ''

        # -- inactive members? --
        show_inactive = True
        if not 'include_inactive' in self.request.params\
           or not self.request.params['include_inactive']:
            show_inactive = False
            m_query = m_query.filter(Member.mem_active == True)

        # -- ordering --
        # direction
        odir = asc
        if 'order_dir' in self.request.params\
           and self.request.params['order_dir'] == 'desc':
            odir = desc
        # order by
        # key is what the outside world sees, value is what SQLAlchemy uses
        order_idxs = {'id': Member.mem_id, 'name': Member.mem_lname}
        order_by = 'id'
        if 'order_by' in self.request.params\
          and self.request.params['order_by'] in order_idxs:
            order_by = self.request.params['order_by']
        # ordering choices
        order_id_choice = 'asc'
        if order_by == 'id' and odir == asc:
            order_id_choice = 'desc'
        order_name_choice = 'asc'
        if order_by == 'name' and odir == asc:
            order_name_choice = 'desc'

        m_query = m_query.order_by(odir(order_idxs[order_by]))
        members = m_query.all()
        self.mem_count = len(members)
        return dict(members=members, msg=msg, order_by=order_by,
                    order_id_choice=order_id_choice,
                    order_name_choice=order_name_choice,
                    show_inactive=show_inactive, came_from='/members')
