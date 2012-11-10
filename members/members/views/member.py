from __future__ import unicode_literals

from pyramid.view import view_config
from sqlalchemy import asc, desc
import datetime

from members.models.member import Member, get_member
from members.models.orders import Order, MemberOrder
from members.models.base import DBSession
from members.views.base import BaseView
from members.views.pwdreset import send_pwdreset_request


def fill_member_from_request(member, request, user_may_edit_admin_settings):
    '''overwrite member properties from request'''
    admin_fields = ['mem_active', 'mem_adm_comment',
                    'mem_membership_paid', 'mem_adm_adj',
                    'mem_admin']
    ignore_fields = ['mem_id', 'mem_enc_pwd', 'mem_pwd_url', 'mem_active']
    if request and member:
        # overwrite member properties from request, pwds are excluded
        for attr in [a for a in Member.__dict__.keys()\
                     if a.startswith('mem_') and not a in ignore_fields]:
            if attr in admin_fields and not user_may_edit_admin_settings:
                continue
            type = str(member.__mapper__.columns._data[attr].type)
            if attr in request.params:
                v = request.params[attr]
                if type == 'BOOLEAN':
                    v = {'on': True, '': False}[v]
                elif type == 'INTEGER':
                    if v != '':
                        v = int(v)
                    else:
                        v = None
                member.__setattr__(attr, v)
            else:
                if type == 'BOOLEAN':
                    member.__setattr__(attr, False)
    return member


@view_config(renderer='../templates/edit-member.pt',
             route_name='member-new',
             permission='edit')
class NewMemberView(BaseView):

    tab = 'members'

    def __call__(self):
        self.user_may_edit_admin_settings = self.user.mem_admin
        return dict(m=Member('', '', ''), msg='')


@view_config(renderer='../templates/member.pt',
             route_name='member',
             permission='view')
class MemberView(BaseView):

    tab = 'members'

    @property
    def user_can_edit(self):
        return self.user.mem_id == self.m.mem_id or self.user.mem_admin

    def __call__(self):
        session = DBSession()
        self.m = get_member(session, self.request)
        msg = ''
        if 'msg' in self.request.params:
            msg = self.request.params['msg']
        nov12 = datetime.datetime(2012, 12, 1)
        orders = [MemberOrder(self.m, o) for o in session.query(Order)\
                    .order_by(desc(Order.completed)).all()]
        old_orders = [o for o in orders if str(o.order.completed) < str(nov12)]
        return dict(m=self.m, msg=msg, shifts=self.m.shifts, old_orders=orders,
                    transactions=self.m.transactions)


@view_config(renderer='../templates/edit-member.pt',
             route_name='member-edit',
             permission='edit')
class EditMemberView(BaseView):

    tab = 'members'

    def __call__(self):
        session = DBSession()
        member = get_member(session, self.request)
        self.user_may_edit_admin_settings = (self.user.mem_admin 
                                    and not self.user.mem_id == member.mem_id)
        if 'action' in self.request.params:
            action = self.request.params['action']
            if action == "save":
                member = fill_member_from_request(member, self.request, 
                                    self.user_may_edit_admin_settings) 
                member.validate()
                if not member.exists:
                    session.add(member)
                    session.flush() # flush manually so the member gets an ID
                    send_pwdreset_request(member, self.request.application_url,
                                          first=True)
                    return self.redirect('/member/{0:d}?msg=Member has been'\
                                         ' created and got an email to set up'\
                                         ' a password. Note: no membership'\
                                         ' fee has been charged (we do not'\
                                         ' know the household size).'\
                                         .format(member.mem_id))
                return dict(m=member, msg='Member has been saved.')
            elif action == 'toggle-active':
                member = get_member(session, self.request)
                self.confirm_toggle_active = True
                return dict(m=member)
            elif action == 'toggle-active-confirmed':
                member.mem_active = not member.mem_active
                return dict(m=member, msg='Member {} is now {}active.'.\
                         format(member, {False:'in', True:''}[member.mem_active]))
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
