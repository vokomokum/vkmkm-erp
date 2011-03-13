import transaction
from pyramid.view import view_config

from members.models.member import Member
from members.models.setup import DBSession
from members.views.base import BaseView


@view_config(renderer='../templates/edit-member.pt', route_name='new_member')
class NewMemberView(BaseView):

    tab = 'members'

    def __call__(self):
        return dict(m = Member('', '', ''), msg='')


@view_config(renderer='../templates/edit-member.pt', route_name='member')
class MemberView(BaseView):

    tab = 'members'

    def __call__(self):

        id = self.request.matchdict['id']
        try:
            id = int(id)
        except:
            return dict(m = None, msg = 'Invalid ID.')
        self.session = DBSession()
        member = self.mkmember(self.request)
        if not member:
            return dict(m=None, msg="No member with id %d" % id)
        if not self.request.params.has_key('action'):
            return dict(m = member, msg='')
        else:
            action = self.request.params['action']
            if action == "save":
                try:
                    self.checkmember(member)
                    self.session.add(member)
                    self.session.flush()
                    new_id = member.id
                    transaction.commit()
                except Exception, e:
                    return dict(m=None, msg=u'Something went wrong: %s' % e)
                # getting member fresh, old one is now detached or sthg
                # after transaction is comitted
                return dict(m = self.mkmember(self.request, id=new_id), msg='Member has been saved.')

            elif action == 'delete':
                try:
                    self.session.delete(self.session.query(Member)\
                        .filter(Member.id == member.id).first()\
                    )
                    self.session.flush()
                    transaction.commit()
                except Exception, e:
                    return dict(m=None, msg=u'Something went wrong: %s' % e)
                return dict(m = None, msg='Member %s has been deleted.' % member)

    def mkmember(self, request=None, id=None):
        if (request and request.matchdict.has_key('id') and\
            int(request.matchdict['id']) >= 0) or id:
                if not id:
                    id = request.matchdict['id']
                member = self.session.query(Member).filter(Member.id==id).first()
                if member:
                    member.exists = True
        else:
            member = Member(fname=u'', prefix=u'', lname='')
        if request and member:
            # overwrite member properties from request
            for attr in [a for a in Member.__dict__.keys() if a.startswith('mem_')]:
                type = str(member.__mapper__.columns._data[attr].type)
                if request.params.has_key(attr):
                    v = request.params[attr]
                    if type == 'BOOLEAN':
                        v = {'on':1, '':0}[v]
                    member.__setattr__(attr, v)
                else:
                    if type == 'BOOLEAN' and member.__dict__.has_key(attr)\
                       and member.__dict__[attr] is True\
                       and self.request.params.has_key('action')\
                       and self.request.params['action'] == 'save':
                        v = False
                        member.__setattr__(attr, v)
        return member

    def checkmember(self, m):
        #TODO: checks on address, bank account, passwords, ...
        pass


@view_config(renderer='../templates/list-members.pt', route_name='memberlist')
class MemberlistView(BaseView):

    tab = 'members'

    def __call__(self):
        dbsession = DBSession()
        m_query = dbsession.query(Member)
        if self.request.params.has_key('active'):
            if self.request.params['active'] != 0:
                m_query = m_query.filter(Member.active==True)

        return dict(members = m_query.all(), msg='')


