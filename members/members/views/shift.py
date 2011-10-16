import transaction
from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound
from pyramid.security import remember

from members.models.shift import Shift
from members.models.workgroups import Workgroup
from members.models.setup import DBSession
from members.views.base import BaseView

'''
All shift operations are done on the workgroups
(this is reflected in the URLs to all these views, check __init__.py),
so all access security can be done via the workgroup.
If you have the right to a workgroup, you can edit shifts.
'''

def mkshift(session, request=None, s_id=None):
    ''' make shift object from id from request, with propoerties from actual request if given '''
    if (request and request.matchdict.has_key('s_id') and\
        int(request.matchdict['s_id']) >= 0) or s_id:
            if not s_id:
                s_id = request.matchdict['s_id']
            shift = session.query(Shift).get(s_id)
            if shift:
                shift.exists = True
    else:
        raise ShiftValidationException
    if request and shift:
        # overwrite shift properties from request
        for attr in ['order_id', 'task_id', 'wg_id', 'mem_id']:
            if request.params.has_key(attr):
                shift.__setattr__(attr, request.params[attr])
        if request.params.has_key('state'):
            shift.set_state(request.params['state'])
    return shift


def checkshift(shift, in_future=True):
    '''
    TODO: anything to do here? All content is foreign keys, so the db will check
    '''
    #raise ShiftValidationException('...')
    pass


def redir_to_wg(wg_id, user_id, request, msg, order_id):
    headers = remember(request, user_id)
    return HTTPFound(location = '/workgroup/%s?msg=%s&order_id=%s' % (str(wg_id), msg, str(order_id)), headers = headers)


@view_config(renderer='../templates/workgroup.pt',
             route_name='new_shift',
             permission='edit')
class NewShiftView(BaseView):
    '''this view is called with data already, so it actually inserts'''
    tab = 'workgroups'

    def __call__(self):
        session = DBSession()
        wg_id = self.request.matchdict['wg_id']
        task_id = self.request.params['task_id']
        order_id = self.request.matchdict['o_id']
        mem_id = self.request.params['mem_id']
        shift = Shift(wg_id, mem_id, order_id, task_id)
        try:
            checkshift(shift)
            session.add(shift)
            session.flush()
            new_id = shift.id
            transaction.commit()
        except ShiftValidationException, e:
            return redir_to_wg(wg_id, self.user.id, self.request, e, order_id)
        except Exception, e:
            return redir_to_wg(wg_id, self.user.id, self.request, 'Something went wrong: %s' % e, order_id)
        # getting shift fresh, old one is now detached or sthg
        # after transaction is comitted
        shift = mkshift(session, self.request, s_id=new_id)
        return redir_to_wg(wg_id, self.user.id, self.request, 'Succesfully added shift', order_id)


class ShiftValidationException(Exception):
    pass


@view_config(renderer='../templates/workgroup.pt',
             route_name='edit_shift',
             permission='edit')
class EditShift(BaseView):

    tab = 'workgroups'

    def __call__(self):

        session = DBSession()
        wg_id = self.request.matchdict['wg_id']
        wg = session.query(Workgroup).get(wg_id)
        if not wg:
            return redir_to_wg(wg.id, self.user.id, self.request, u"Don't know which workgroup this is supposed to be.", '')

        s_id = self.request.matchdict['s_id']
        if s_id != 'fresh':
            try:
                s_id = int(s_id)
            except:
                return dict(m = None, msg = 'Invalid ID.')
        shift = mkshift(session, self.request)
        order_id = shift.order_id
        if not shift:
            return redir_to_wg(wg.id, self.user.id, self.request, "No shift with id %d" % s_id, '')

        if not self.request.params.has_key('action'):
            return redir_to_wg(wg.id, self.user.id, self.request, 'No action given.', order_id)
        else:
            action = self.request.params['action']
            if action == "save":
                try:
                    checkshift(shift)
                    session.add(shift)
                    session.flush()
                    new_id = shift.id
                    transaction.commit()
                except ShiftValidationException, e:
                    return redir_to_wg(wg_id, self.user.id, self.request, e, order_id)
                except Exception, e:
                    return redir_to_wg(wg_id, self.user.id, self.request, u'Something went wrong: %s' % e, order_id)
                return redir_to_wg(wg_id, self.user.id, self.request, 'Shift has been saved.', order_id)

            elif action == 'delete':
                try:
                    session.delete(shift)
                    session.flush()
                    transaction.commit()
                except Exception, e:
                    return redir_to_wg(wg_id, self.user.id, self.request, u'Something went wrong: %s' % e, order_id)
                return redir_to_wg(wg_id, self.user.id, self.request, 'Shift has been deleted.', order_id)


