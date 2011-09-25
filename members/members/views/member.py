import transaction
from pyramid.view import view_config

from members.models.member import Member
from members.models.setup import DBSession
from members.views.base import BaseView


def mkmember(session, request=None, id=None):
    theid = -1
    member = None
    if request and request.matchdict.has_key('id'):
        theid = request.matchdict['id']
    if id:
        theid = id
    if theid == 'fresh':
        member = Member(fname=u'', prefix=u'', lname=u'')
    elif int(theid) > 0:
        member = session.query(Member).filter(Member.id==theid).first()
        if member:
            member.exists = True
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


class MemberCreationException(Exception):
    pass


@view_config(renderer='../templates/member.pt',
             route_name='member',
             permission='view')
class MemberView(BaseView):

    tab = 'members'

    def __call__(self):
        id = self.request.matchdict['id']
        try:
            id = int(id)
        except:
            return dict(m = None, msg = 'Invalid ID.')
        m = mkmember(DBSession(), self.request, id=id)
        if not m:
            return dict(m=None, msg="No member with id %d" % id)
        self.user_can_edit = self.user.id == m.id or self.user.mem_admin
        return dict(m=m, msg='')


@view_config(renderer='../templates/edit-member.pt',
             route_name='member-edit',
             permission='edit')
class MemberEditView(BaseView):

    tab = 'members'

    def __call__(self):

        self.session = DBSession()
        id = self.request.matchdict['id']
        if id != 'fresh':
            try:
                id = int(id)
            except:
                return dict(m = None, msg = 'Invalid ID.')
        member = mkmember(self.session, self.request)
        if not member:
           return dict(m=None, msg="No member with id %d" % id)
        if not self.request.params.has_key('action'):
            return dict(m = member, msg='', came_from='/member/%d' % member.id)
        else:
            action = self.request.params['action']
            if action == "save":
                try:
                    self.checkmember(member)
                    if id == 'fresh':
                        self.checkpwd(self.request)
                        import md5
                        enc_pwd = md5.new(self.request.params['pwd1']).digest()
                        member.mem_enc_pwd = enc_pwd.decode('iso-8859-1')
                        #member.mem_enc_pwd = self.request.params['pwd1']
                    if not member.mem_enc_pwd:
                        #TODO: if this happens, we still saves other changed attributes that come in the request?
                        raise MemberCreationException('Member has no password.')
                    self.session.add(member)
                    self.session.flush()
                    new_id = member.id
                    transaction.commit()
                except MemberCreationException, e:
                    return dict(m=member, msg=e)
                except Exception, e:
                    return dict(m=member, msg=u'Something went wrong: %s' % e)
                # getting member fresh, old one is now detached or sthg
                # after transaction is comitted
                return dict(m = mkmember(self.session, self.request, id=new_id), msg='Member has been saved.')

            elif action == 'delete':
                try:
                    self.session.delete(member)
                    self.session.flush()
                    transaction.commit()
                except Exception, e:
                    return dict(m=None, msg=u'Something went wrong: %s' % e)
                return dict(m = None, msg='Member %s has been deleted.' % member)


    def checkpwd(self, req):
        if not req.params.has_key('pwd1'):
            raise MemberCreationException('Please specify a password.')
        if not req.params.has_key('pwd2'):
            raise MemberCreationException('Please confirm password.')
        if not req.params['pwd2'] == req.params['pwd1']:
            raise MemberCreationException('Passwords do not match.')
        if not 6 <= len(req.params['pwd1']) <= 30:
            raise MemberCreationException('The password should be between 6 and 30 characters long.')

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
            raise MemberCreationException('We still require you to fill in: %s'\
                                    % ', '.join([m[4:] for m in missing]))
        # TODO check email
        if not '@' in m.mem_email:
            raise MemberCreationException('The email address does not seem to be valid.')
        # check postcode
        if not (m.mem_postcode[:4].isdigit() and m.mem_postcode[-2:].isalpha()):
            raise MemberCreationException('The email postcode does not seem to be valid (should be NNNNLL, where N=number and L=letter).')
        # check house no
        if not m.mem_house.isdigit():
            raise MemberCreationException('House number should just be a number.')
        # check bank no
        if len(m.mem_bank_no) < 7 or len(m.mem_bank_no) > 8:
            raise MemberCreationException('Bank number needs to consist of 7 or 8 numbers.')
        if not m.mem_bank_no.isdigit():
            raise MemberCreationException('Bank number needs to consist of only numbers.')
        # at least one telephone number
        ks = m.__dict__.keys()
        if (not 'mem_home_tel' in ks and not 'mem_work_tel' in ks and not 'mem_mobile' in ks) or\
           (m.mem_home_tel == "" and m.mem_work_tel == "" and m.mem_mobile == ""):
            raise MemberCreationException('Please specify at least one telephone number.')


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
        # key is what the outside world see, value is what SQLAlchemy uses
        order_idxs = {'id': Member.id, 'name': Member.mem_lname}
        order_by = 'id'
        if self.request.params.has_key('order_by')\
          and order_idxs.has_key(self.request.params['order_by']):
            order_by = self.request.params['order_by']
        order_alt = (order_by=='id') and 'name' or 'id'
        m_query = m_query.order_by(order_idxs[order_by])

        #TODO: check if non-active members should be here, filter them out in the first place

        return dict(members = m_query.all(), msg='', order_by=order_by, order_alt=order_alt, came_from='/members')


