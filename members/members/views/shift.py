from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound
from pyramid.security import remember

from members.models.shift import Shift, get_shift
from members.models.workgroups import Workgroup
from members.models.member import Member
from members.models.task import Task
from members.models.base import DBSession, Base
from members.views.base import BaseView

'''
All shift operations are done on the workgroups
(this is reflected in the URLs to all these views, check __init__.py),
so all access security can be done via the workgroup.
If you have the right to a workgroup, you can edit shifts.
The database should take care about the shift data being right.
'''


def fill_shift_from_request(shift, request):
    '''overwrite shift properties from request'''
    if request and shift:
        # overwrite shift properties from request
        if 'state' in request.params:
            shift.state = request.params['state']
        for attr in ['wg_id', 'month', 'year']:
            if attr in request.params:
                shift.__setattr__(attr, int(request.params[attr]))
        for attr in ['task_id', 'mem_id', 'day']:
            if attr in request.params:
                val = request.params[attr]
                if val == '--':
                    val = None
                else:
                    val = int(val)
                shift.__setattr__(attr, val)
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
        shift = Shift(None, None, None, None, None)
        shift = fill_shift_from_request(shift, self.request)
        shift.validate()
        session.add(shift)
        return self.redirect('/workgroup/{}?msg={}&month={}&year={}'.format(wg_id, 
                             'Succesfully added shift', shift.month, shift.year))


@view_config(renderer='../templates/workgroup.pt',
             route_name='shift-edit',
             permission='edit')
class EditShiftView(BaseView):

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

        if self.request.params.has_key('action'):
            action = self.request.params['action']
            if action == "save":
                shift = fill_shift_from_request(shift, self.request)
                shift.validate()
                session.add(shift)
                return self.redirect('/workgroup/{}?msg={}&month={}&year={}'\
                                     .format(wg_id, 'Shift has been saved.', 
                                             shift.month, shift.year))

            elif action == 'delete':
                session.delete(shift)
                return self.redirect('/workgroup/{}?msg={}&month={}&year={}'\
                                     .format(wg_id, 'Shift has been deleted.',
                                             shift.month, shift.year))
        else:
            raise Exception('No action given.')

