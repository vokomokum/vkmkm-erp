from pyramid.view import view_config

from members.models.member import Member
from members.models.setup import DBSession
from members.views.base import BaseView


@view_config(renderer='../templates/edit-member.pt', route_name='member')
class MemberView(BaseView):

    tab = 'members'

    def __call__(self):
        #id = self.request.attribute('id')

        dbsession = DBSession()
        member = dbsession.query(Member).filter(Member.mem_fname==u'Peter').first()
        member.exists = True

        return dict(m = member, msg='')
