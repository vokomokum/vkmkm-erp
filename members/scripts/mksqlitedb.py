import os
import sys
from sqlalchemy import create_engine
from subprocess import Popen
import transaction

from members import models
from members.models.member import Member
from members.utils.md5crypt import md5crypt

# this could be used to access .ini (for later reference)
#from pyramid.paster import bootstrap
#env = bootstrap('development.ini')
#print env['request'].route_url('home')

dbname = 'members-dev.db'
if len(sys.argv) > 1:
    dbname = sys.argv[1]

if os.path.exists(dbname):
    print('DB {} already exists. Delete it or pass a different filename '\
          'as argument.'.format(dbname))
    sys.exit(2)

# initalise database with some order data the members app relies on
Popen('sqlite3 {} < members/tests/setup.sql'.format(dbname), shell=True).wait()
engine = create_engine('sqlite:///{}'.format(dbname))
DBSession = models.base.configure_session(engine)
# create the database model from models/ via CREATE statements
models.base.Base.metadata.bind = engine
models.base.Base.metadata.create_all(engine)
# turn on Foreign Keys in sqlite
# (enforcement only works from version 3.6.19 though)
engine.execute('pragma foreign_keys=on')

# add a default admin
admin = Member(fname=u'Adalbert', lname='Adminovic')
admin.mem_email = 'admin@vokomokum.nl'
salt = md5crypt('notsecret', '') 
admin.mem_enc_pwd = md5crypt('notsecret', salt)
DBSession.add(admin)
DBSession.flush()
transaction.commit()

print('Created database {}'.format(dbname))
