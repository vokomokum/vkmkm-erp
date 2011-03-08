from members.models.member import Member
from members.models.workgroups import Workgroup
from members.models.setup import DBSession


def get_member(mem_id, request):
    mem = None
    session = DBSession()
    if userid:
        try:
            mem = session.query(Member).filter(Member.mem_id == mem_id).first()
        except:
            pass
    return mem


def groupfinder(userid, request):
    groups = ['group:members']
    wg_id = request.params.get('wg_id', -1)
    if wg_id >= 0:
        session = get_dbsession()
        wg = session.query(Workgroup).filter(Workgroup.id == wg_id and Workgroup.leader_id == userid).all()
        if len(wgs) > 0:
            groups.append('group:leader')
    if userid in ['nic', 'jes']:
        groups.append('group:admins')
    return groups
