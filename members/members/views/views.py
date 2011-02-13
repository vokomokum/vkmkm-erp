from members.models.setup import DBSession
from members.models.member import Member
from members.models.workgroups import Workgroup
from members.models.shift import Shift

def my_view(request):
    dbsession = DBSession()
    peter = dbsession.query(Member).filter(Member.mem_fname==u'Peter').first()
    wgs = dbsession.query(Workgroup).all()
    shifts = dbsession.query(Shift.day, Shift.month, Shift.year, Member.mem_fname)\
                             .filter(Shift.mem_id == Member.id)\
                             .filter(Shift.mem_id == peter.id)
    return {'members':[peter], 'workgroups':wgs, 'shifts':shifts}
