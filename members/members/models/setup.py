
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()


def initialize_sql(engine):
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    Base.metadata.create_all(engine)
    try:
        session = DBSession()

        # start test for authentication development
        from member import Member
        from shift import Shift
        from workgroups import Workgroup

        import md5
        import transaction
        test_member = Member(fname=u'Peter', prefix=u'de', lname='Pan')
        # TODO: this causes a db problem (only on sqlite when testing?)
        #test_member.mem_enc_pwd = md5.new('PASSWORD').digest()
        test_member.mem_enc_pwd = 'PASSWORD'
        session.add(test_member)
        session.flush()
        transaction.commit()
        # end test

    except IntegrityError:
        DBSession.rollback()
    return session
