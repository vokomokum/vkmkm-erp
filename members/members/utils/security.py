from members.models.member import Member
from members.models.workgroups import Workgroup
from members.models.base import DBSession


def get_member(login):
    '''
    Get a member object
    :param string login: the login can either be the member ID or the email-address
    :returns: The Member object or None if none was found for login information
    '''
    mem = None
    session = DBSession()
    if "@" in str(login): # email address given as login?
        mem = session.query(Member).filter(Member.mem_email == login).first()
    else: # then assume id
        mem = session.query(Member).filter(Member.mem_id == login).first()
    return mem


def authenticated_userid(request):
    '''
    Get authenticated user ID from cookie
    '''
    m = get_member(request.cookies.get("Mem"))
    if m and m.mem_cookie == request.cookies.get("Key"):  # TODO: check IP?
        return m.mem_id


def authenticated_user(request):
    """
    extract logged in userid from request, return associated Account instance
    :param Request request: request object
    :returns: a Member object or None
    """
    userid = authenticated_userid(request)
    if userid:
        return get_member(userid)


def groupfinder(memid, request):
    session = DBSession()
    groups = ['group:members']
    context = request.context
    
    if context.__class__ == Member:
        mem_id = request.matchdict.get('mem_id', -1)
        if not mem_id == 'new':
            if int(mem_id) == memid:
                groups.append('group:this-member')

    if context.__class__ == Workgroup:
        if 'wg_id' in request.matchdict:
            wg_id = request.matchdict['wg_id']
            if not wg_id == 'new':
                wg = session.query(Workgroup).get(wg_id)
                if memid in [m.mem_id for m in wg.leaders]:
                    groups.append('group:wg-leaders')
                if memid in [m.mem_id for m in wg.members]:
                    groups.append('group:wg-members')
    admins = session.query(Member).filter(Member.mem_admin == True).all()
    if memid in [m.mem_id for m in admins]:
        groups.append('group:admins')
    # membership people:
    membership = session.query(Workgroup).\
                    filter(Workgroup.name == 'Membership').first()
    if membership:
        if memid in [m.mem_id for m in membership.members]:
            groups.append('group:membership')
    # finance people:
    finance = session.query(Workgroup).\
                    filter(Workgroup.name == 'Finance').first()
    if finance:
        if memid in [m.mem_id for m in finance.members]:
            groups.append('group:finance')
    
    #print "+++++++++++++++++++++++++++++++++++++++ User is in groups:", groups
    return groups
