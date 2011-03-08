from pyramid.view import view_config

from members.models.setup import DBSession
from members.models.member import Member
from members.models.workgroups import Workgroup
from members.models.shift import Shift

from members.views.base import BaseView


#@view_config(renderer='../templates/mytemplate.pt', route_name='home')
#def test_view(request):

@view_config(renderer='../templates/mytemplate.pt', route_name='home')
class DirView(BaseView):

    def __call__(self):
        print "TESTVIEW!"
        dbsession = DBSession()
        members = dbsession.query(Member).filter(Member.mem_fname==u'Peter').all()
        wgs = dbsession.query(Workgroup).all()
        if len(members) > 0:
            peter = members[0]
            shifts = dbsession.query(Shift.day, Shift.month, Shift.year, Member.mem_fname)\
                                 .filter(Shift.mem_id == Member.id)\
                                 .filter(Shift.mem_id == peter.id)
        else:
            shifts = []
        return dict(logged_in = self.logged_in,
                    members = members,
                    workgroups = wgs,
                    came_from = '/',
                    shifts = shifts)


@view_config(renderer='../templates/test.pt', route_name='test')
class TestView(BaseView):

    def __call__(self):
        return dict(bla = 'Blupp', logged_in=True)
