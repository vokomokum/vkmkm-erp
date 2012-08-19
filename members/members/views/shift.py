from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound
from pyramid.security import remember

import datetime
from calendar import monthrange

from members.models.shift import Shift, get_shift
from members.models.workgroups import Workgroup, get_wg
from members.models.member import Member, get_member
from members.models.base import DBSession, Base
from members.views.base import BaseView

'''
All shift operations are done on the workgroups
(this is reflected in the URLs to all these views, check __init__.py),
so all access security can be done via the workgroup.
If you have the right to a workgroup, you can edit shifts.
The data model should take care about the shift data being correct.
'''


def fill_shift_from_request(shift, request):
    '''overwrite shift properties from request'''
    if request and shift:
        # overwrite shift properties from request
        for attr in ['task', 'state']:
            if attr in request.params:
                shift.__setattr__(attr, request.params[attr])
        for attr in ['wg_id', 'month', 'year']:
            if attr in request.params:
                shift.__setattr__(attr, int(request.params[attr]))
        for attr in ['mem_id', 'day']:
            if attr in request.params:
                val = request.params[attr]
                if val == '--':
                    val = None
                else:
                    val = int(val)
                shift.__setattr__(attr, val)
    return shift


class BaseShiftView(BaseView):

    def redir_to_shiftlist(self, wg, year, month, msg):
        ''' redirect to shift list view '''
        return self.redirect('/workgroup/{}/shifts/{}/{}?msg={}'.format(
                    wg.id, year, month, msg))



@view_config(renderer='../templates/workgroup.pt',
             route_name='shift-new',
             permission='edit')
class NewShiftView(BaseShiftView):
    '''
    this view is called with data already, so it actually inserts
    '''
    tab = 'workgroups'

    def __call__(self):
        db_session = DBSession()
        params = self.request.params
        wg_id = self.request.matchdict['wg_id']
        wg = get_wg(db_session, self.request)
        if not 'people' in params:
            people = 1
        else:
            people = int(params['people'])
        self.added_shifts = 0
        def add_shift(month=None, year=None):
            ''' add a shift object to session, several times if people > 1 '''
            shift = Shift(wg_id, '', None, None, None, None)
            shift = fill_shift_from_request(shift, self.request)
            if month:
                shift.month = month
            if year:
                shift.year = year 
            for _ in xrange(people):
                s = shift.clone()
                s.mem_id = None  # should not be necessary, just to be sure
                s.validate()
                db_session.add(s)
                self.added_shifts += 1
        day = params['day']
        if day == '--':
            day = 1
        else:
            day = int(day)
        sdate = datetime.datetime(int(params['year']), 
                                  int(params['month']), day)
        if not 'repeat' in params:
            repeat = 'once'
        else:
            repeat = params['repeat'] 
        if repeat == 'once':
            add_shift()
        else:
            udate = datetime.datetime(int(params['until_year']),
                                      int(params['until_month']), day)
            # not possible for any-day shifts
            if params['day'] == '--':
                return self.redir_to_shiftlist(wg, sdate.year, sdate.month, 
                        'Cannot repeat shift with with no day set.')
            if repeat == 'weekly':
                pass 
            elif repeat == 'bi-weekly':
                pass
            elif repeat == 'monthly':
                for year in xrange(sdate.year, udate.year + 1):
                    print("year: {}".format(year))
                    smonth = 1
                    if year == sdate.year:
                        smonth = sdate.month
                    umonth = 12
                    if year == udate.year:
                        umonth = udate.month
                    for month in xrange(smonth, umonth + 1):
                        add_shift(month, year)
                if self.added_shifts == 0:
                    return self.redir_to_shiftlist(wg, sdate.year, sdate.month,
                        "Invalid date range: {}/{} to {}/{}".format(sdate.month,
                            sdate.year, udate.month, udate.year)) 
                         
        return self.redir_to_shiftlist(wg, sdate.year, sdate.month, 
                    'Succesfully added {} shift(s) for task "{}".'\
                    .format(self.added_shifts, self.request.params['task']))


@view_config(renderer='../templates/workgroup.pt',
             route_name='shift-edit',
             permission='view')
class EditShiftView(BaseShiftView):
    '''
    Perform an action on a shift and then redirect to the shift list view.
    It has generally "view" permission, since the access right has to be judged 
    on a case-by-case basis.
    This view can be ajaxified pretty easily.
    '''

    tab = 'workgroups'

    def __call__(self):
        db_session = DBSession()
        wg = get_wg(db_session, self.request)
        if not wg:
            raise Exception("Don't know which workgroup this is supposed to be.")

        shift = get_shift(db_session, self.request)
        if not shift:
            raise Exception("No shift with id %d" % self.request.matchdict['s_id'])

        def redir(msg):
            return self.redir_to_shiftlist(wg, shift.year, shift.month, msg)
    
        action = self.request.matchdict['action']
        if action == "":
            raise Exception('No action given.')

        if action == "setmember":
            if not 'mem_id' in self.request.params:
                return redir('No member selected.')
            if not self.user in wg.members and not self.user.mem_admin:
                return redir('You are not allowed to assign shifts in this workgroup.')
            if self.request.params['mem_id'] == '--':
                member = None
            else:
                member = get_member(db_session, self.request)
            if member: 
                shift.member = member
                shift.state = 'assigned' 
                return redir('{} has been signed up for the shift.'.format(shift.member))
            else:
                if shift.is_locked and not self.user in wg.leaders:
                    return redir('Shift is already locked. Ask your workgroup admin for help.')
                shift.member = None
                shift.state = 'open' 
                return redir('Shift is now open.')
            return redir('You are not allowed to do this.')

        elif action == "settask":
            if self.user in wg.leaders:
                if not 'task' in self.request.params:
                    return dict(msg='No task given.')
                shift.task = self.request.params['task']
                shift.validate()
                return redir('Changed task of shift.')
            return redir('You are not allowed to edit the task.')

        elif action == "setday":
            if self.user in wg.leaders:
                if not 'day' in self.request.params:
                    return dict(msg='No day given.')
                shift.day = int(self.request.params['day'])
                shift.validate()
                return redir('Changed day of shift to {}.'.format(shift.day))
            return redir('You are not allowed to set the day.')

        elif action == "setstate":
            if self.user in wg.leaders:
                if not 'state' in self.request.params:
                    return redir('No state given.')
                shift.state = self.request.params['state']
                shift.validate()
                return redir('Changed shift state to {}.'.format(shift.state))
            return redir('You are not allowed to set the state.')

        elif action == 'delete':
            if self.user in wg.leaders:
                db_session.delete(shift)
                return redir('Deleted shift')
            return redir('You are not allowed to delete a shift.')


@view_config(renderer='../templates/shifts.pt',
             route_name='shift-list')
class ListShiftView(BaseView):

    tab = 'workgroups'

    def __call__(self):
        db_session = DBSession()
        
        wg = get_wg(db_session, self.request)
        self.user_is_wgmember = self.user in wg.members
        self.user_is_wgleader = self.user in wg.leaders

        # we view shifts per-month here
        now = datetime.datetime.now()
        self.month = now.month
        self.year = now.year
        if 'month' in self.request.matchdict:
            self.month = int(self.request.matchdict['month'])
        if 'year' in self.request.matchdict:
            self.year = int(self.request.matchdict['year'])
        sdate = datetime.date(self.year, self.month, now.day)
        self.days_in_month = monthrange(self.year, self.month)[1]
        lmdate = now - datetime.timedelta(days=-self.days_in_month)
        dipm = monthrange(lmdate.year, lmdate.month)[1]
        one_month_back = sdate + datetime.timedelta(days=-dipm)
        one_month_ahead = sdate + datetime.timedelta(days=self.days_in_month)
        self.prev_month = one_month_back.month
        self.prev_year = one_month_back.year
        self.next_month = one_month_ahead.month
        self.next_year = one_month_ahead.year
        self.days = ['any day'] + range(1, self.days_in_month+1)
        self.month_is_not_in_past = sdate.year >= now.year or sdate.month >= now.month 
        shifts = db_session.query(Shift).filter(Shift.wg_id == wg.id)\
                                     .filter(Shift.month == self.month)\
                                     .filter(Shift.year == self.year)\
                                     .order_by(Shift.day)\
                                     .all()
                                     #.group_by(Shift.day)\

        # show msg
        if 'msg' in self.request.params:
            msg = self.request.params['msg']
        else:
            msg = ''

        return dict(shifts=shifts, wg=wg, msg=msg)
