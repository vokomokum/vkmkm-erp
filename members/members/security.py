from members.models.member import Member
from members.models.workgroups import Workgroup
from members.models.setup import DBSession


def get_member(login):
    mem = None
    session = DBSession()
    try:
        if "@" in login: # email address
            mem = session.query(Member).filter(Member.mem_email == login).first()
        else: # then assume id
            mem = session.query(Member).filter(Member.id == login).first()
    except Exception, e:
        print e
    return mem


def groupfinder(memid, request):
    session = DBSession()
    groups = ['group:members']
    wg_id = request.params.get('wg_id', -1)
    if wg_id >= 0:
        wg = session.query(Workgroup).filter(Workgroup.id == wg_id and Workgroup.leader_id == memid).all()
        if len(wgs) > 0:
            groups.append('group:leader')
    admins = session.query(Member).filter(Member.mem_admin == True).all()
    if memid in [m.id for m in admins]:
        groups.append('group:admins')
    return groups
