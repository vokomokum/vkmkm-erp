import transaction

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()

from member import Member
from shift import Shift
from workgroups import Workgroup


def populate():
    session = DBSession()
    test_member = Member(fname=u'Peter', prefix=u'de', lname='Pan')
    session.add(test_member)
    test_workgroup = Workgroup(name=u'Besteling', desc=u'Besteling at wholesale')
    session.add(test_workgroup)
    session.flush() # flush now to get member and workgroup IDs
    test_member.workgroups.append(test_workgroup)
    test_shift = Shift(wg_id=test_workgroup.id, mem_id=test_member.id, year=2011, month=2)
    test_shift.set_day(3)
    session.add(test_shift)
    session.flush()
    transaction.commit()
    
def initialize_sql(engine):
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    Base.metadata.create_all(engine)
    try:
        populate()
    except IntegrityError:
        DBSession.rollback()
