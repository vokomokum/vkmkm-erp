from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

import transaction


# for raw SQL queries
DBEngine = []
def get_connection():
    ''' :returns: a connection to execute("""SELECT ...;""") a raw SQL query on'''
    return DBEngine[0].connect()


# The DBSession is for working with SQLAlchemy models (strictly preferrable)
# The autoflush and autocommit settings are like default, bit good to have explicit
# (see http://mapfish.org/doc/tutorials/sqlalchemy.html#create-the-session)
# Note:
# pyramid commits all changed objects in the session after the request
# has successfully been processed. This is by design, to simplify and
# reduce transaction handling (see e.g. http://comments.gmane.org/gmane.comp.web.pylons.general/15295)
DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension(), autoflush=False, autocommit=False))
Base = declarative_base()


def initialize_sql(engine):
    ''':returns: a session object to work with'''
    DBEngine.append(engine)
    DBSession.configure(bind=engine)
    Base.metadata.bind = engine
    Base.metadata.create_all(engine)
    try:
        session = DBSession()
        test_setup(session, engine)
    except IntegrityError:
        DBSession.rollback()
    return session


def test_setup(session, engine):
    ''' For test purposes, create things this app relies on, e.g. things that other apps create '''
    # turn on Foreign Keys in sqlite (enforcement only works from version 3.6.19 though)
    engine.execute('pragma foreign_keys=on')

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

    # create order_header
    db_conn = get_connection()
    try:
        db_conn.execute("""CREATE TABLE order_header (ord_no integer NOT NULL, ord_label character varying NOT NULL)""")
    except OperationalError:
        pass
    header = db_conn.execute("""SELECT * FROM order_header""")
    if len(list(header)) == 0:
        db_conn.execute("""INSERT INTO order_header (ord_no, ord_label) VALUES (?, ?);""", 1, "current_order")

    from others import Order
    orders = session.query(Order).all()
    if len(orders) == 0:
        for i in xrange(1,6):
            db_conn.execute("""INSERT INTO wh_order (ord_no, ord_label) VALUES (?, ?);""", i, "Order No. %d" % i)

    transaction.commit()
