from pyramid.view import view_config

import datetime

from members.models.base import DBSession
from members.models.todo import Todo
from members.models.member import Member
from members.models.shift import Shift
from members.views.base import BaseView


@view_config(renderer='../templates/home.pt', route_name='home')
class HomeView(BaseView):

    def __call__(self):
        session = DBSession()
        todos = get_todos(session, self.user)
        return dict(todos=todos)



def get_todos(session, user):
    '''
    Go through a list of cases to find current TODOs for this user
    '''
    todos = []
    act_members = session.query(Member)\
                         .filter(Member.mem_active == True).all()
    now = datetime.datetime.now()

    if 'Membership' in user.workgroups or user.mem_admin:
        # Members without a workgroup
        for m in [am for am in act_members if len(am.workgroups) == 0]:
            todos.append(Todo(msg='Member {} is without a workgroup.'.format(m),
                              wg='Membership',
                              link_act='member/{}'.format(m.mem_id),
                              link_txt='See member profile.',
                              link_title='You should contact the member and '\
                                 'discuss which openings he/she would '\
                                 'like. If they refuse, inactivate him/her.'))
    # coordinators in general
    for led_wg in user.led_workgroups:
        # shifts to check upon
        ass_shifts = session.query(Shift)\
                            .filter(Shift.wg_id == led_wg.id)\
                            .filter(Shift.state == 'assigned').all()
        print ass_shifts
        for s in [s for s in ass_shifts\
                  if s.month < now.month or s.year < now.year]:
            todos.append(Todo(msg='Please write off shift by {} ({}), '\
                                  'in {}/{}.'\
                                  .format(s.member, s.day and s.day or 'any day', s.month, s.year),
                              wg=s.workgroup.name,
                              link_act='workgroup/{}/shifts/{}/{}'\
                                            .format(s.wg_id, s.year, s.month),
                              link_txt='Shift schedule.',
                              link_title='Go to the shift schedule and put '\
                                       'the shift in "worked" or "no-show" mode.'))
        
    return todos

