from members.models.setup import DBSession
from members.models.member import Member

def my_view(request):
    dbsession = DBSession()
    peter = dbsession.query(Member).filter(Member.mem_fname==u'Peter').first()
    return {'members':[peter]}
