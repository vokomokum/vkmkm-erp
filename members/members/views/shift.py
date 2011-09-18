import transaction
from pyramid.view import view_config

from members.models.shift import Shift
from members.models.setup import DBSession
from members.views.base import BaseView

'''
All shift operations are done on the workgroups
(this is reflected in the URLs to all these views, check __init__.py),
so all access security can be done via the workgroup.
If you have the right to a workgroup, you can edit shifts.
'''

@view_config(renderer='../templates/edit-workgroup.pt',
             route_name='new_shift',
             permission='edit')
class NewShiftView(BaseView):

    tab = 'workgroups'

    def __call__(self, wg_id, mem_id, year, month):
        wg_id = self.request.matchdict['id']
        mem_id = self.request.matchdict['mem_id']
        year = self.request.matchdict['year']
        month = self.request.matchdict['month']
        shift = Shift(wg_id, mem_id, year, month)

        self.session = DBSession()
        self.session.add(shift)
        self.session.flush()
        new_id = shift.id
        transaction.commit()
        except ShiftCreationException, e:
            return dict(s=shift, msg=e)
        except Exception, e:
            return dict(s=shift, msg=u'Something went wrong: %s' % e)
        # getting shift fresh, old one is now detached or sthg
        # after transaction is comitted
        shift = self.mkshift(self.request, id=new_id)
        return dict(s = shift, came_from='workgroup/{%s}' % wg_id,
                    msg='New shift added for member %s.' % mem_id)


class ShiftCreationException(Exception):
    pass


@view_config(renderer='../templates/edit-workgroup.pt',
             route_name='edit_shift',
             permission='edit')
class ShiftView(BaseView):

    tab = 'workgroups'

    def __call__(self):

        self.session = DBSession()
        wg_id = self.request.matchdict['id']
        s_id = self.request.matchdict['s_id']
        if id != 'fresh':
            try:
                id = int(id)
            except:
                return dict(m = None, msg = 'Invalid ID.')
        shift = self.mkshift(self.request)
        if not shift:
           return dict(m=None, msg="No shift with id %d" % id)
        if not self.request.params.has_key('action'):
            return dict(s = shift, msg='', came_from='/shift/%d' % shift.id)
        else:
            action = self.request.params['action']
            if action == "save":
                try:
                    self.checkshift(shift)
                    self.session.add(shift)
                    self.session.flush()
                    new_id = shift.id
                    transaction.commit()
                except ShiftCreationException, e:
                    return dict(s=shift, msg=e)
                except Exception, e:
                    return dict(s=shift, msg=u'Something went wrong: %s' % e)
                return dict(s = self.mkshift(self.request, id=new_id), msg='Shift has been saved.')

            elif action == 'delete':
                try:
                    self.session.delete(shift)
                    self.session.flush()
                    transaction.commit()
                except Exception, e:
                    return dict(s=None, msg=u'Something went wrong: %s' % e)
                return dict(s=None, msg='Shift %s has been deleted.' % shift)

    def checkshift(self, shift):
        ''' TODO: check valid date and member, wg? '''
        pass

    def mkshift(self, request=None, id=None):
        ''' make shift object from id from request, with propoerties from actual request if given '''
        if (request and request.matchdict.has_key('id') and\
            int(request.matchdict['id']) >= 0) or id:
                if not id:
                    id = request.matchdict['id']
                shift = self.session.query(Shift).filter(Shift.id==id).first()
                if shift:
                    shift.exists = True
        else:
            raise ShiftCreationException
        if request and shift:
            # overwrite shift properties from request
            for attr in ['year', 'month', 'day', 'wg_id', 'mem_id']:
                if request.params.has_key(attr):
                    shift.__setattr__(attr, request.params[attr])
        return shift



