from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

import transaction


class VokoValidationError(Exception):
    ''' We throw this when an object thinks it should not be saved in its current state.'''
    pass


# The DBSession is for working with SQLAlchemy models (strictly
# preferrable to raw SQL). It makes a lot of regular programming tasks
# in web-app development very easy.
# Working on DB-related objects will lead to SQL statements that
# SQLAlchemy creates (e.g. changing a members' city leads to an UPDATE
# statement on the members table).
# Views can create objects from the DB using the session very easyly
# and straightforward. They do not need to do anything with objects
# in the session but adding, deleting or changing them.
# All changes made on objects that are in the session will
# automatically commited to the DB at the end of a successful request.
#
# What is commiting?
# -------------------
#   A commit makes all SQL statements within a transactions permanent.
#   If one statement fails, thw whole transaction is rolled back.
#   In our context, all that happens within one request is our
#   transaction.
#   Pyramid (via SQLAlchemy and the ZopeTransactionExtension)
#   commits all changed objects in the session after the request has
#   successfully been processed. This is by design, to simplify and
#   reduce transaction handling (see e.g.
#   http://comments.gmane.org/gmane.comp.web.pylons.general/15295)
#   The consequence is that views should simply raise Exceptions (caught
#   by views.base.ErrorView) if anything goes wrong and can rely on a rollback.
#
# What is flushing?
# -------------------
#  A session can be flushed at any point, which simulates a commit on
#  the model in the session. It will fail if the commit would fail
#  (given that the data model in pyramid corresponds to the DB)
#  and it will update things like new IDs coming from auto-increment
#  tables.
#  We set autoflush=True, because this way database errors (e.g. a
#  constraint violation) cause an Exception before the request ended.
#  Then our catch-all ErrorView can still catch it.
#  Read more about autoflush and autocommit settings here:
#  http://mapfish.org/doc/tutorials/sqlalchemy.html#create-the-session
#
# Raw SQL
# ------------------
# Raw SQL can be executed on the session, though it should only be done when
# not possible on the SQLAlchemy model. Here is an example:
# res = DBSession.execute('''SELECT * from workgroups;''')
# print list(res)[0].name
DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension(), autoflush=True, autocommit=False))

# this is used as base model class for SQLAlchemy models
Base = declarative_base()


def configure_session(engine):
    ''' configure the session '''
    DBSession.configure(bind=engine)
    return DBSession


def test_setup(session, engine):
    '''
    For test purposes, create things this app relies on, e.g. one member and things that other apps create
    TODO: this should not be here, we should have real unit/integration tests, but it might be useful for that.
    '''
    # turn on Foreign Keys in sqlite (enforcement only works from version 3.6.19 though)
    engine.execute('pragma foreign_keys=on')

    # these statements create the database model from models/ via CREATE statements
    #Base.metadata.bind = engine
    #Base.metadata.create_all(engine)

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
    try:
        DBSession.execute("""CREATE TABLE order_header (ord_no integer NOT NULL, ord_label character varying NOT NULL)""")
    except OperationalError:
        pass
    try:
        header = DBSession.execute("""SELECT * FROM order_header""")
        if len(list(header)) == 0:
            DBSession.execute("""INSERT INTO order_header (ord_no, ord_label) VALUES (?, ?);""", 1, "current_order")

        from others import Order
        orders = session.query(Order).all()
        if len(orders) == 0:
            for i in xrange(1,6):
                DBSession.execute("""INSERT INTO wh_order (ord_no, ord_label) VALUES (?, ?);""", i, "Order No. %d" % i)
    except IntegrityError:
        transaction.abort()

    transaction.commit()
