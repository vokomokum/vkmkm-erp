from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

import transaction

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()


def initialize_sql(engine):
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    Base.metadata.create_all(engine)
    try:
        session = DBSession()

        # Make sure we have at least our default admin
        # import late to avoid circular imports (bcs of Base being used
        # in Member class)
        from member import Member
        member1 = session.query(Member).filter(Member.id==1).first()
        if not member1:
            member1 = Member(fname='Jim', lname='Segrave')
            member1.mem_admin = True
            session.add(member1)
            session.flush()
            transaction.commit()
    except IntegrityError:
        DBSession.rollback()
    return session
