import transaction
from pyramid.view import view_config

from members.models.workgroups import Workgroup
from members.models.member import Member
from members.models.setup import DBSession
from members.views.base import BaseView


def get_possible_members(session):
    return session.query(Member).filter(Member.mem_active==True).all()


@view_config(renderer='../templates/edit-workgroup.pt',
             route_name='new_workgroup',
             permission='edit')
class NewWorkgroupView(BaseView):

    tab = 'workgroups'

    def __call__(self):
        self.possible_members = get_possible_members(DBSession())
        return dict(wg = Workgroup('', ''), msg='')

@view_config(renderer='../templates/edit-workgroup.pt',
             route_name='workgroup',
             permission='view')
class WorkgroupView(BaseView):

    tab = 'workgroups'

    def __call__(self):
        id = self.request.matchdict['id']
        try:
            id = int(id)
        except:
            return dict(m = None, msg = 'Invalid ID.')
        self.session = DBSession()
        wg = self.mkworkgroup(self.request)
        if not wg:
            return dict(wg=None, msg="No workgroup with id %d" % id)


@view_config(renderer='../templates/edit-workgroup.pt',
             route_name='workgroup-edit',
             permission='edit')
class WorkgroupView(BaseView):

    tab = 'workgroups'

    def __call__(self):
        print 'wg view called.'
        id = self.request.matchdict['id']
        if id != 'fresh':
            try:
                id = int(id)
            except:
                return dict(m = None, msg = 'Invalid ID.')

        self.session = DBSession()
        wg = self.mkworkgroup(self.request)
        if not wg:
            return dict(wg=None, msg="No workgroup with id %d" % id)
        if not self.request.params.has_key('action'):
            self.possible_members = get_possible_members(self.session)
            return dict(wg = wg, msg='')
        else:
            action = self.request.params['action']
            if action == "save":
                if self.request.params.has_key('wg_members'):
                    wg.members = []
                    for mid in self.request.POST.getall('wg_members'):
                        m = self.session.query(Member).filter(Member.id == mid).first()
                        wg.members.append(m)
                try:
                    self.session.add(wg)
                    self.session.flush()
                    new_id = wg.id
                    transaction.commit()
                    self.session = DBSession()
                except Exception, e:
                    return dict(wg = None, msg=u'Something went wrong: %s' % e)
                self.possible_members = get_possible_members(self.session)
                return dict(wg = self.mkworkgroup(self.request, id=new_id), msg='Workgroup has been saved.')

            elif action == 'delete':
                try:
                    self.session.delete(self.session.query(Workgroup)\
                        .filter(Workgroup.id == wg.id).first()\
                    )
                    self.session.flush()
                    transaction.commit()
                except Exception, e:
                    return dict(wg = None, msg=u'Something went wrong: %s' % e)
                return dict(wg = None, msg='Workgroup %s has been deleted.' % wg)


    def mkworkgroup(self, request=None, id=None):
        if (request and request.matchdict.has_key('id') and\
            int(request.matchdict['id']) >= 0) or id:
                if not id:
                    id = request.matchdict['id']
                wg = self.session.query(Workgroup).filter(Workgroup.id==id).first()
                if wg:
                    wg.exists = True
        else:
            wg = Workgroup('', '')
        if request and wg:
            # overwrite workgroup properties from request
            for attr in ['name', 'desc', 'leader_id']:
                if request.params.has_key(attr):
                    wg.__setattr__(attr, request.params[attr])
        return wg





@view_config(renderer='../templates/list-workgroups.pt', route_name='workgrouplist')
class WorkgrouplistView(BaseView):

    tab = 'workgroups'

    def __call__(self):
        dbsession = DBSession()
        wg_query = dbsession.query(Workgroup)

        # ordering
        # key is what the outside world see, value is what SQLAlchemy uses
        order_idxs = {'id': Workgroup.id, 'name': Workgroup.name}
        order_by = 'id'
        if self.request.params.has_key('order_by')\
          and order_idxs.has_key(self.request.params['order_by']):
            order_by = self.request.params['order_by']
        order_alt = (order_by=='id') and 'name' or 'id'
        wg_query = wg_query.order_by(order_idxs[order_by])

        return dict(workgroups=wg_query.all(), msg='', order_by=order_by, order_alt=order_alt, came_from='/workgroups')


