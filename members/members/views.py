from members.models import DBSession
from members.models import Member

def my_view(request):
    dbsession = DBSession()
    peter = dbsession.query(Member).filter(Member.mem_fname==u'Peter').first()
    return {'members':[peter]}
