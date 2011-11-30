from pyramid.view import view_config

from datetime import datetime

from members.models.member import Member
from members.models.setup import DBSession
from members.views.base import BaseView



def get_member(session, request):
    ''' make a Member object, use request if possible '''
    member = None
    if (request and request.matchdict.has_key('mem_id') and
            request.matchdict['mem_id'] != 'fresh'):
        member = session.query(Member).get(request.matchdict['mem_id'])
        if member:
            member.exists = True
    elif request.matchdict['mem_id'] == 'fresh':
        member = Member(fname=u'', prefix=u'', lname=u'')
    return member



def fill_member_from_request(member, request):
    '''overwrite member properties from request'''
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
                   and request.params.has_key('action')\
                   and request.params['action'] == 'save':
                    v = False
                    member.__setattr__(attr, v)
    return member


@view_config(renderer='../templates/edit-member.pt',
             route_name='new_member',
             permission='edit')
class NewMemberView(BaseView):

    tab = 'members'

    def __call__(self):
        return dict(m = Member('', '', ''), msg='')


class MemberValidationExceptions(Exception):
    pass


@view_config(renderer='../templates/member.pt',
             route_name='member',
             permission='view')
class MemberView(BaseView):

    tab = 'members'

    def __call__(self):
        m = get_member(DBSession(), self.request)
        if not m:
            raise Exceptions("No member with id %d" % self.request.matchdict['mem_id'])
        self.user_can_edit = self.user.mem_id == m.mem_id or self.user.mem_admin
        # assigned and worked shifts
        assigned = [s for s in m.scheduled_shifts if s.state == 'assigned']
        worked = [s for s in m.scheduled_shifts if s.state == 'worked']
        return dict(m=m, msg='', assigned_shifts=assigned, worked_shifts=worked)


@view_config(renderer='../templates/edit-member.pt',
             route_name='member-edit',
             permission='edit')
class MemberEditView(BaseView):

    tab = 'members'

    def __call__(self):

        session = DBSession()
        member = get_member(session, self.request)
        if not member:
           raise Exception("No member with id %d" % self.request.matchdict['mem_id'])
        if self.request.params.has_key('action'):
            action = self.request.params['action']
            if action == "save":
                member = fill_member_from_request(member, self.request)
                session.add(member)
                self.checkmember(member)
                if self.request.matchdict['mem_id'] == 'fresh':
                    self.checkpwd(self.request)
                    import md5
                    enc_pwd = md5.new(self.request.params['pwd1']).digest()
                    member.mem_enc_pwd = enc_pwd.decode('iso-8859-1')
                    #member.mem_enc_pwd = self.request.params['pwd1']
                if not member.mem_enc_pwd:
                    #TODO: if this happens, we still saves other changed attributes that come in the request?
                    raise MemberValidationExceptions('Member has no password.')
                session.add(member)
                new_id = member.mem_id
                return dict(m = member, msg='Member has been saved.')

            elif action == 'delete':
                session.delete(member)
                return dict(m = None, msg='Member %s has been deleted.' % member)
        return dict(m = member, msg='')


    def checkpwd(self, req):
        if not req.params.has_key('pwd1'):
            raise MemberValidationExceptions('Please specify a password.')
        if not req.params.has_key('pwd2'):
            raise MemberValidationExceptions('Please confirm password.')
        if not req.params['pwd2'] == req.params['pwd1']:
            raise MemberValidationExceptions('Passwords do not match.')
        if not 6 <= len(req.params['pwd1']) <= 30:
            raise MemberValidationExceptions('The password should be between 6 and 30 characters long.')

    def checkmember(self, m):
        ''' checks on address, bank account, passwords, ... '''
        # check missing fields
        missing = []
        for f in ('mem_fname', 'mem_lname', 'mem_email',
                  'mem_street', 'mem_house', 'mem_postcode', 'mem_city',
                  'mem_bank_no'):
            if not m.__dict__.has_key(f) or m.__dict__[f] == '':
                missing.append(f)
        if len(missing) > 0:
            raise MemberValidationExceptions('We still require you to fill in: %s'\
                                    % ', '.join([m[4:] for m in missing]))
        # TODO check email
        if not '@' in m.mem_email:
            raise MemberValidationExceptions('The email address does not seem to be valid.')
        # check postcode
        if not (m.mem_postcode[:4].isdigit() and m.mem_postcode[-2:].isalpha()):
            raise MemberValidationExceptions('The email postcode does not seem to be valid (should be NNNNLL, where N=number and L=letter).')
        # check house no
        if not m.mem_house.isdigit():
            raise MemberValidationExceptions('House number should just be a number.')
        # check bank no
        if len(m.mem_bank_no) < 7 or len(m.mem_bank_no) > 8:
            raise MemberValidationExceptions('Bank number needs to consist of 7 or 8 numbers.')
        if not m.mem_bank_no.isdigit():
            raise MemberValidationExceptions('Bank number needs to consist of only numbers.')
        # at least one telephone number
        ks = m.__dict__.keys()
        if (not 'mem_home_tel' in ks and not 'mem_work_tel' in ks and not 'mem_mobile' in ks) or\
           (m.mem_home_tel == "" and m.mem_work_tel == "" and m.mem_mobile == ""):
            raise MemberValidationExceptions('Please specify at least one telephone number.')


@view_config(renderer='../templates/list-members.pt', route_name='memberlist')
class MemberlistView(BaseView):

    tab = 'members'

    def __call__(self):
        dbsession = DBSession()
        m_query = dbsession.query(Member)
        if self.request.params.has_key('active'):
            if self.request.params['active'] != 0:
                m_query = m_query.filter(Member.active==True)

        # ordering
        # key is what the outside world sees, value is what SQLAlchemy uses
        order_idxs = {'id': Member.mem_id, 'name': Member.mem_lname}
        order_by = 'id'
        if self.request.params.has_key('order_by')\
          and order_idxs.has_key(self.request.params['order_by']):
            order_by = self.request.params['order_by']
        order_alt = (order_by=='id') and 'name' or 'id'
        m_query = m_query.order_by(order_idxs[order_by])

        #TODO: check if non-active members should be here, filter them out in the first place

        return dict(members = m_query.all(), msg='', order_by=order_by, order_alt=order_alt, came_from='/members')


