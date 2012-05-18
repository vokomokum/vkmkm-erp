from pyramid.security import authenticated_userid

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
    try:
        if "@" in str(login): # email address given as login?
            mem = session.query(Member).filter(Member.mem_email == login).first()
        else: # then assume id
            mem = session.query(Member).filter(Member.mem_id == login).first()
    except Exception, e:
        print "Exception while getting a member: %s" % e
    return mem


def authenticated_user(request):
    """
    extract logged in userid from request, return associated Account instance
    :param Request request: request object
    :returns: a Member object or None
    """
    userid = authenticated_userid(request)
    if userid is not None:
        return get_member(userid)


def groupfinder(memid, request):
    session = DBSession()
    groups = ['group:members']
    context = request.context
    #TODO: use id of context object to check workgroup and member
    #if context.__class__ == Workgroup
    #    groups.append('wg-members')
    if context.__class__ == Member:
        mem_id = int(request.matchdict.get('mem_id', -1))
        if mem_id == memid:
            groups.append('group:this-member')

    wg_id = int(request.params.get('wg_id', -1))
    if 'wg_id' in request.matchdict:
        if wg_id == -1:
            wg_id = request.matchdict['wg_id']
    if wg_id >= 0:
        if wg_id in [wg.id for wg in session.query(Member).get(memid).led_workgroups]:
            groups.append('group:wg-leaders')
    admins = session.query(Member).filter(Member.mem_admin == True).all()
    if memid in [m.mem_id for m in admins]:
        groups.append('group:admins')
    #print "User is in groups:", groups
    return groups
