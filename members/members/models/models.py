import transaction

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import Unicode

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker

from zope.sqlalchemy import ZopeTransactionExtension

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()


class Member(Base):
    __tablename__ = 'members'
    id = Column(Integer, primary_key=True)
    mem_fname = Column(Unicode(255))
    mem_prefix = Column(Unicode(255))
    mem_lname = Column(Unicode(255))

    def __init__(self, fname, prefix, lname):
        self.mem_fname = fname
        self.mem_prefix = prefix
        self.mem_lname = lname


def populate():
    session = DBSession()
    test_member = Member(fname=u'Peter', prefix=u'de', lname='Pan')
    session.add(test_member)
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
