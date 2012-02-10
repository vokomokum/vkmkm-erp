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
The database should take care about the shift data being right.
'''

def get_shift(session, request):
    ''' get shift object from id '''
    if (request and request.matchdict.has_key('s_id') and\
        int(request.matchdict['s_id']) >= 0):
            shift = session.query(Shift).get(request.matchdict['s_id'])
            if shift:
                shift.exists = True
    else:
        shift = None
    return shift


def fill_shift_from_request(shift, request):
    '''overwrite shift properties from request'''
    if request and shift:
        # overwrite shift properties from request
        for attr in ['order_id', 'task_id', 'wg_id', 'mem_id']:
            if request.params.has_key(attr):
                shift.__setattr__(attr, request.params[attr])
        if request.params.has_key('state'):
            shift.set_state(request.params['state'])
    return shift


@view_config(renderer='../templates/workgroup.pt',
             route_name='shift-new',
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
        session.add(shift)
        return self.redirect('/workgroup/%s?msg=%s&order_id=%s' % (wg_id, 'Succesfully added shift', order_id))



@view_config(renderer='../templates/workgroup.pt',
             route_name='shift-edit',
             permission='edit')
class EditShift(BaseView):

    tab = 'workgroups'

    def __call__(self):

        session = DBSession()
        wg_id = self.request.matchdict['wg_id']
        wg = session.query(Workgroup).get(wg_id)
        if not wg:
            raise Exception("Don't know which workgroup this is supposed to be.")

        shift = get_shift(session, self.request)
        if not shift:
            raise Exception("No shift with id %d" % self.request.matchdict['s_id'])
        order_id = shift.order_id

        if self.request.params.has_key('action'):
            action = self.request.params['action']
            if action == "save":
                shift = fill_shift_from_request(shift, self.request)
                session.add(shift)
                return self.redirect('/workgroup/%s?msg=%s&order_id=%s' % (wg_id, 'Shift has been saved.', order_id))

            elif action == 'delete':
                session.delete(shift)
                return self.redirect('/workgroup/%s?msg=%s&order_id=%s' % (wg_id, 'Shift has been deleted.', order_id))
        else:
            raise Exception('No action given.')

