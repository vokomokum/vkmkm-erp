import unittest
import transaction
from subprocess import Popen
import os
from shutil import rmtree

from pyramid import testing

from sqlalchemy import create_engine, engine_from_config
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, OperationalError

from members import models
from members.models.member import Member
from members.models.workgroups import Workgroup
from members.models.shift import Shift
from members.models.transactions import TransactionType
from members.models.transactions import reserved_ttype_names
from members.utils import mail
from members.utils.misc import get_settings
from members.utils.md5crypt import md5crypt


'''
Base class for all our Tests,
Currently supports testing with sqlite database.
A test database is used for each Test.
Potentially, we'd also want to test with Postgres, but
that is more work bcs starting Postgres up is slow, so
we'd use the same db, but rollback everything after each Test
(see http://sontek.net/writing-tests-for-pyramid-and-sqlalchemy)
'''

db_type = 'sqlite'

class VokoTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if db_type == 'postgres':
            #TODO: where to get setting from? maybe:
            # from paste.deploy.loadwsgi import appconfig
            from members.utils.misc import get_settings
            settings = get_settings()
            # settings = appconfig('config:' + os.path.join(here, '../../', 'development.ini'))
            cls.engine = engine_from_config(settings, prefix='sqlalchemy.')
            cls.Session = sessionmaker()

    def setUp(self):
        self.config = testing.setUp()
        if db_type == 'sqlite':
            # initalise a temporary database with some order data the members app relies on
            if os.path.exists('members-test.db'):
                Popen('rm members-test.db', shell=True).wait()
            Popen('sqlite3 members-test.db < members/tests/setup.sql', shell=True).wait()
            self.engine = create_engine('sqlite:///members-test.db')
            self.DBSession = models.base.configure_session(self.engine)
            # create the database model from models/ via CREATE statements
            models.base.Base.metadata.bind = self.engine
            models.base.Base.metadata.create_all(self.engine)
            # turn on Foreign Keys in sqlite (enforcement only works from version 3.6.19 though)
            self.engine.execute('pragma foreign_keys=on')
        else:
            self.DBSession = models.base.configure_session(create_engine('postgres://'))
        self.add_custom_settings()
        self.fill_data()


    def tearDown(self):
        if db_type == 'sqlite':
            self.DBSession.close()
            Popen('rm members-test.db', shell=True).wait()
        super(VokoTestCase, self).tearDown()
        rmtree(get_settings()['vokomokum.mail_folder'])
        testing.tearDown()

    def path_to_here(self):
        return '/'.join(os.path.realpath(__file__).split('/')[:-1])

    def add_custom_settings(self):
        '''
        Add custom settings that the application expects to be in the .ini file 
        (in app[main])
        '''
        # make a mail folder
        mail_folder = '{0}/.testmails'.format(self.path_to_here())
        if os.path.exists(mail_folder):
            rmtree(mail_folder)
        os.mkdir(mail_folder)
        settings = get_settings()
        # workaround: this will not send mails, just save copies in mails-dir
        settings['vokomokum.mail_exec'] = '/opt/local/sbin/eximDONOTACTUALLYSEND'
        settings['vokomokum.mail_folder'] = mail_folder
        settings['vokomokum.mail_sender'] = 'systems@vokomokum.nl'

    def fill_data(self):
        '''
        Fills in dummy content that we will use for testing
        2 members, Peter and Hans.
        2 workgroups, Systems and Besteling.
        Peter is the only member in Systems.
        Both are members in Bestel, with Hans leading that one.
        Bestel has a shift ('do stuff') for Peter.
        '''
        m1 = Member(fname=u'Peter', prefix=u'de', lname='Pan')
        m1.mem_email = 'peter@dePan.nl'
        m1.mem_enc_pwd = md5crypt('notsecret', 'notsecret')
        self.DBSession.add(m1)
        m2 = Member(fname=u'Hans', prefix=u'de', lname='Wit')
        m1.mem_email = 'hans@deWit.nl'
        self.DBSession.add(m2)
        wg1 = Workgroup(name=u'Systems', desc=u'IT stuff')
        self.DBSession.add(wg1)
        wg2 = Workgroup(name=u'Besteling', desc=u'Besteling at wholesale')
        self.DBSession.add(wg2)
        self.DBSession.flush() # flush now to get member and workgroup IDs
        wg1.members.append(m1)
        wg1.leaders.append(m1)
        wg2.members.append(m1)
        wg2.members.append(m2)
        wg2.leaders.append(m2)
        self.DBSession.flush()
        s = Shift(wg2.id, 'do stuff', 2012, 6, member=m1)
        self.DBSession.add(s)
        self.DBSession.flush()
        # reserved transaction types
        for rt in reserved_ttype_names:
            self.DBSession.add(TransactionType(name=rt))
        self.DBSession.flush()

    def get_peter(self):
        return self.DBSession.query(Member).get(1)

    def get_hans(self):
        return self.DBSession.query(Member).get(2)
    


