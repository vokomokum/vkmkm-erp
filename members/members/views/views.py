from members.models.setup import DBSession
from members.models.member import Member
from members.models.workgroups import Workgroup
from members.models.shift import Shift

def my_view(request):
    dbsession = DBSession()
    peter = dbsession.query(Member).filter(Member.mem_fname==u'Peter').first()
    wgs = dbsession.query(Workgroup).all()
    shifts = dbsession.query(Shift)
    #shifts = dbsession.query('SELECT s.*, m.fname AS mfname, wg.name AS wgname FROM \
    #                          shifts s, members m, workgroups wg \
    #                          WHERE s.mem_id=m.id AND s.wg_id=wg.id')
    return {'members':[peter], 'workgroups':wgs, 'shifts':shifts}
