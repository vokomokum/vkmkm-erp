from members.models.setup import DBSession
from members.models.member import Member
from members.models.workgroups import Workgroup
from members.models.shift import Shift

def my_view(request):
    dbsession = DBSession()
    members = dbsession.query(Member).filter(Member.mem_fname==u'Peter').all()
    wgs = dbsession.query(Workgroup).all()
    if len(members) > 0:
        peter = members[0]
        shifts = dbsession.query(Shift.day, Shift.month, Shift.year, Member.mem_fname)\
                             .filter(Shift.mem_id == Member.id)\
                             .filter(Shift.mem_id == peter.id)
    else:
        shifts = []
    return {'members':members, 'workgroups':wgs, 'shifts':shifts}
