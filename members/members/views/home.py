from pyramid.view import view_config

from members.models.base import DBSession
from members.models.todo import Todo
from members.models.member import Member
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

    if 'Membership' in user.workgroups or user.mem_admin:
        # Members without a workgroup
        act_members = session.query(Member)\
                             .filter(Member.mem_active == True).all()
        for m in [am for am in act_members if len(am.workgroups) == 0]:
            todos.append(Todo(msg='Member {} is without a workgroup.'.format(m),
                              wg='Membership',
                              link_act='member/{}'.format(m.mem_id),
                              link_txt='See member profile.',
                              link_title='You should contact the member and '\
                                 'discuss which openings he/she would '\
                                 'like. If they refuse, inactivate him/her.'))
    return todos

