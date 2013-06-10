import os
import sys
from sqlalchemy import create_engine
from subprocess import Popen
import random
import transaction

from members import models
from members.models.member import Member
from members.models.applicant import Applicant

from members.models.workgroups import Workgroup
from members.models.shift import Shift
from members.models.transactions import TransactionType
from members.models.transactions import reserved_ttype_names

from members.utils.md5crypt import md5crypt

'''
TODO:
# Adalbert should be in Membership and Systems
# shifts are all open, select some states randomly (mostly worked, some assigned and noshow)
# Add some transactions
# Some shifts and some transactions should be in the current & next month
# Mention this script in the INSTALL file (or a better place)
# Maybe even make a fab command?
'''

dbname = 'members-dev.db'
seed='Miau'
fakenamesname = 'scripts/fakenames.txt'
DBSession = None
default_pwd = 'testtest'


# this could be used to access .ini (for later reference)
#from pyramid.paster import bootstrap
#env = bootstrap('development.ini')
#print env['request'].route_url('home')


def addAdmin():
    admin = Member(fname=u'Adalbert', lname='Adminovic')
    admin.mem_email = 'admin@vokomokum.nl'
    salt = md5crypt('notsecret', '') 
    admin.mem_enc_pwd = md5crypt('notsecret', salt)
    admin.mem_admin = True
    admin.mem_active = True
    DBSession.add(admin)
    DBSession.flush()
    

"""Ensure the backwards compatibility, these settings are used in unit tests"""
def addOldNames():
    m1 = Member(fname=u'Peter', prefix=u'de', lname='Pan')
    m1.mem_email = 'peter@dePan.nl'
    m1.mem_enc_pwd = md5crypt('notsecret', 'notsecret')
    DBSession.add(m1)
    m2 = Member(fname=u'Hans', prefix=u'de', lname='Wit')
    m1.mem_email = 'hans@deWit.nl'
    DBSession.add(m2)
    wg1 = Workgroup(name=u'Systems', desc=u'IT stuff')
    DBSession.add(wg1)
    wg2 = Workgroup(name=u'Besteling', desc=u'Besteling at wholesale')
    DBSession.add(wg2)
    DBSession.flush() # flush now to get member and workgroup IDs
    wg1.members.append(m1)
    wg1.leaders.append(m1)
    wg2.members.append(m1)
    wg2.members.append(m2)
    wg2.leaders.append(m2)
    DBSession.flush()
    s = Shift(wg2.id, 'do stuff', 2012, 6, member=m1)
    DBSession.add(s)
    DBSession.flush()
    

def createWGs():
    wgs = []
    wgs.append(Workgroup(name=u'Systems2', desc=u'IT stuff'))
    wgs.append(Workgroup(name=u'Besteling2', desc=u'Besteling at wholesale'))
    wgs.append(Workgroup(name=u'Cafe', desc=u'Cakes and coffee'))
    wgs.append(Workgroup(name=u'Finance', desc=u'Making sure money is where it is supposed to be'))
    wgs.append(Workgroup(name=u'Vers', desc=u'Fresh food!'))
    wgs.append(Workgroup(name=u'Membership', desc=u'Human resources'))
    for wg in wgs:
        DBSession.add(wg)
    DBSession.flush()
    return wgs
    

def fillDBRandomly(seed):
    random.seed(seed)
    workgroups = createWGs()
    # read in the fakenames
    names = {}
    for l in file(fakenamesname, 'r'):
        fname,lname = l.strip().split()
        names[fname] = lname
    namelist = sorted(list(names.keys()))
    # 20% of the people are applicants
    members = []
    for l in namelist[int(len(namelist) * 0.2):]:
        m = Applicant(fname=l, lname=names[l])
        m.email = "%s@%s.nl"%(l, names[l])
        m.household_size = random.randint(1, 15)
        m.telnr = "06" + unicode(random.randint(10000000, 100000000))
        DBSession.add(m)
        # randomly select a number of workgroups m can be a member of
        DBSession.flush()
    # and the rest are members
    for l in namelist[:int(len(namelist) * 0.8)]:
        prefix = random.choice([u"de", u"van", u"voor", u"van den", u"te"])
        m = Member(fname=l, prefix=prefix, lname=names[l])
        m.mem_email = "%s@%s.nl" % (l, names[l])
        m.mem_enc_pwd = md5crypt(default_pwd, default_pwd)
        m.mem_mobile = "06" + unicode(random.randint(10000000, 100000000))
        m.mem_membership_paid = True
        if random.random() < 0.01:
            m.mem_membership_paid = False
        m.mem_active = True
        if random.random() < 0.05:
            m.mem_active = False
        m.mem_street = random.choice(namelist) + "street"
        m.mem_house = random.randint(1, 200)
        m.mem_postcode = "1000AB"
        m.city = "Amsterdam"
        DBSession.add(m)
        # randomly select a number of workgroups m can be a member of
        for wg in random.sample(workgroups, random.randint(1, len(workgroups))):
            wg.members.append(m)
            # randomly select if m is a leader of the workgroup: only 10 % of all members are leaders
            if random.random() < 0.1:
                wg.leaders.append(m)
        members.append(m)
        DBSession.flush()
    
    # next step: create new shifts with random sequences as descriptions
    shifts = []
    states = ["open", "assigned", "worked", "no-show"]
    for wg in workgroups:
        ### create 50 shifts
        shifts_wg = []
        for i in range(50):
            shift_dec  = random.choice(["clean", "buy", "feed", "fill", "write", "do", "play", "sleep"])
            s = Shift(wg.id, shift_dec, random.choice([2011, 2012, 2013]), random.randint(1,13))    
            shifts_wg.append(s)
            if s.state in states[1:]:
                s.member = random.choice(wg.members)
        for s in shifts_wg:
            DBSession.add(s)
        DBSession.flush()
                
    # create transactions: 
    transactions = [] 


if __name__ == '__main__':
    if len(sys.argv) > 1:
        dbname = sys.argv[1]

    if os.path.exists(dbname):
        print('DB {} already exists. Delete it or pass a different filename '\
              'as argument.'.format(dbname))
        sys.exit(2)

    # initalise database with some external data the members app relies on
    Popen('sqlite3 {} < members/tests/setup.sql'.format(dbname), shell=True).wait()
    engine = create_engine('sqlite:///{}'.format(dbname))
    DBSession = models.base.configure_session(engine)
    # create the database model from models/ via CREATE statements
    models.base.Base.metadata.bind = engine
    models.base.Base.metadata.create_all(engine)
    # turn on Foreign Keys in sqlite
    # (enforcement only works from version 3.6.19 though)
    engine.execute('pragma foreign_keys=on')
    # reserved transaction types
    for rt in reserved_ttype_names:
        DBSession.add(TransactionType(name=rt))

    # add a default admin
    addAdmin()
    # add old names, used in base.py and in testing (ask Nic what to do with it)
    addOldNames()
    # this applicants, members, shifts and transactions
    fillDBRandomly(seed)

    DBSession.flush()
    transaction.commit()

    print('Created database {}'.format(dbname))

