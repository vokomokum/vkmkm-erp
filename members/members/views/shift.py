from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound
from pyramid.security import remember

import datetime

from members.models.shift import Shift, get_shift
from members.models.workgroups import Workgroup, get_wg
from members.models.member import Member, get_member
from members.models.base import DBSession, Base
from members.views.base import BaseView
from members.utils.misc import month_info
from members.utils.misc import ascii_save
from members.utils.mail import sendmail


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
        if 'mem_id' in request.params:
            mem_id = request.params['mem_id']
            if mem_id == '--':
                shift.mem_id = shift.member = None
            else:
                shift.mem_id = int(mem_id)
                shift.member = DBSession().query(Member).get(mem_id)
                shift.state = 'assigned'
        if 'day' in request.params:
            shift.day = request.params['day']  # brutally using the strings here
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
    tab = 'work'

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
            shift.validate()
            db_session.add(shift)
            self.added_shifts += 1
            if month:
                shift.month = month
            if year:
                shift.year = year
            if people > 1:
                for _ in xrange(1, people):
                    s = shift.clone()
                    s.validate()
                    db_session.add(s)
                    self.added_shifts += 1
        day = params['day']
        if not str(day).isdigit():
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
            if repeat in ('monthly', 'bi-monthly-startnow',
                            'bi-monthly-startnext'):
                for year in xrange(sdate.year, udate.year + 1):
                    smonth = 1
                    if year == sdate.year:
                        smonth = sdate.month
                    umonth = 12
                    if year == udate.year:
                        umonth = udate.month
                    step = 1
                    if repeat.startswith('bi-monthly'):
                        step = 2
                    if repeat == 'bi-monthly-startnext':
                        smonth += 1
                    for month in xrange(smonth, umonth + 1, step):
                        add_shift(month, year)
                if self.added_shifts == 0:
                    return self.redir_to_shiftlist(wg, sdate.year, sdate.month,
                        "Invalid date range: {}/{} to {}/{}".format(sdate.month,
                            sdate.year, udate.month, udate.year)) 
            else: 
                return self.redir_to_shiftlist(wg, sdate.year, sdate.month, 
                    'Could not create shifts. "repeat"-command unknown.')
        return self.redir_to_shiftlist(wg, sdate.year, sdate.month, 
                    'Succesfully added {} shift(s) for task "{}".'\
                    .format(self.added_shifts, 
                            ascii_save(self.request.params['task'])))


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

    tab = 'work'

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

            # prepare some things for mailing
            schedule_url = '{}/workgroup/{}/shifts/{}/{}'.format(
                        self.request.application_url, shift.workgroup.id,
                        shift.year, shift.month)
            q = 'This email was automatically generated, so please do not '\
                'directly reply to it. You may direct any questions regarding '\
                'the workgroup to your coordinator(s). Only technical questions '\
                'go to systems@vokomokum.nl.'\
                '\n\nBest,\nVokomokum'           
            old_member = shift.member
            def mail_old_assignee():
                # send old assignee an email
                if old_member and not self.user == old_member:
                    subject = 'You have been signed out of a shift.'
                    body = 'Hi,\n\n{} has signed you off a shift that '\
                           'you were previously assigned to.\nThe shift is '\
                           'now:\n\n{}\n\nYou can view the shift '\
                           'schedule at {}.\n{}'.format(
                            ascii_save(self.user.fullname), shift,
                            schedule_url, q) 
                    sendmail(old_member.mem_email, subject, body, 
                             folder='shifts')

            if member:
                shift.member = member
                shift.state = 'assigned'
                shift.validate()
                if not self.user == member:
                    # send new assignee an email
                    subject = 'You have been assigned to a shift.'
                    body = 'Hi,\n\n{} has assigned you to a shift: '\
                           '\n\n{}\n\nYou can view the shift schedule at {}'\
                           '\n\n{}'.format(ascii_save(self.user.fullname),
                            str(shift), schedule_url, q)
                    sendmail(member.mem_email, subject, body, folder='shifts')
                # let coordinator(s) know, as well
                subject = "Task {} on day '{}' in {}/{} is now assigned to {}"\
                    .format(shift.task, shift.day, shift.month, shift.year,
                           ascii_save(shift.member.fullname))
                body = "The assignment was done by member {}\n\n{}"\
                    .format(ascii_save(self.user.fullname), q)
                for c in wg.leaders:
                    if c is not self.user:
                        sendmail(c.mem_email, subject, body, folder='shifts')
                # and inform previous assignee
                mail_old_assignee()
                name = ascii_save(shift.member.fullname)
                return redir(u'{} has been signed up for the shift.'\
                             .format(name))
            else:
                if shift.is_locked and not self.user in wg.leaders:
                    return redir('Shift is already locked. Ask your workgroup admin for help.')
                shift.member = None
                shift.state = 'open' 
                shift.validate()
                mail_old_assignee()
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
                shift.day = self.request.params['day']
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
                return redir('Deleted shift.')
            return redir('You are not allowed to delete a shift.')


@view_config(renderer='../templates/shifts.pt',
             route_name='shift-list')
class ListShiftView(BaseView):

    tab = 'work'

    def __call__(self):
        db_session = DBSession()
        
        wg = get_wg(db_session, self.request)
        self.user_is_wgmember = self.user in wg.members
        self.user_is_wgleader = self.user in wg.leaders

        # we view shifts per-month here
        # use parameters to determine month, default is current month
        now = datetime.datetime.now()
        self.month = int(self.request.matchdict['month'])
        self.year = int(self.request.matchdict['year'])
        # we take today's day for simplicity
        schedule_date = datetime.date(self.year, self.month, now.day)
        self.month_info = month_info(schedule_date) 
        q = """SELECT descr FROM shift_days_descriptions ORDER BY id;""" 
        day_literals = [i[0] for i in list(db_session.execute(q))]
        self.days = day_literals + range(1, self.month_info.days_in_month + 1)
        shifts = db_session.query(Shift).filter(Shift.wg_id == wg.id)\
                                     .filter(Shift.month == self.month)\
                                     .filter(Shift.year == self.year)\
                                     .order_by(Shift.day)\
                                     .all()

        # show msg
        if 'msg' in self.request.params:
            msg = self.request.params['msg']
        else:
            msg = ''

        return dict(shifts=shifts, wg=wg, msg=msg)



@view_config(renderer='../templates/shift_year_overview.pt',
             route_name='shift-year-overview',
             permission='view')
class ShiftYearOverview(BaseView):

    tab = 'work'

    def __call__(self):
        session = DBSession()
        self.wg = session.query(Workgroup).get(int(self.request.matchdict['wg_id']))
        self.year = int(self.request.matchdict['year'])

        self.all_shift_data = {}
        self.month_sums = {}
        self.member_sums = {}
        for m in self.wg.members:
            self.member_sums[m.mem_id] = [0, 0]
        self.sum_overall = [0, 0]
        self.sum_open_overall = 0
        self.months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug',
                       'Sep', 'Oct', 'Nov', 'Dec']
        
        q = session.query(Shift).filter(Shift.wg_id == self.wg.id)\
                                .filter(Shift.year == self.year)

        for month in self.months:
            self.all_shift_data[month] = {} 
            self.month_sums[month] = [0, 0]
            qm = q.filter(Shift.month == self.months.index(month)+1)
            for m in self.wg.members:
                qmm = qm.filter(Shift.mem_id == m.mem_id)
                # worked shifts shifts of this member this month
                wmm = qmm.filter(Shift.state == 'worked').count()        
                # all assigned (assigned, worked or not-worked) 
                amm = wmm + qmm.filter(Shift.state == 'assigned').count()        
                amm += qmm.filter(Shift.state == 'no-show').count()        
                self.all_shift_data[month][m.mem_id] = wmm, amm
                self.month_sums[month][0] += wmm
                self.month_sums[month][1] += amm
                self.member_sums[m.mem_id][0] += wmm
                self.member_sums[m.mem_id][1] += amm
                self.sum_overall[0] += wmm 
                self.sum_overall[1] += amm 
            # now open (not assigned) shifts   
            om = qm.filter(Shift.state == 'open').count()
            self.all_shift_data[month][-1] = om
            self.sum_open_overall += om
            
        return dict(msg='')


