import unittest
import transaction
from pyramid.config import Configurator
from pyramid import testing

from members.models.member import Member
from members.models.workgroups import Workgroup
from members.models.shift import Shift


def _initTestingDB():
    from sqlalchemy import create_engine
    from members.models.setup import initialize_sql
    session = initialize_sql(create_engine('sqlite:///members-test.db'))
    #session = initialize_sql(create_engine('postgres://'))
    return session


class TestModel(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        self.session = _initTestingDB()
        test_member = Member(fname=u'Peter', prefix=u'de', lname='Pan')
        self.session.add(test_member)
        test_workgroup = Workgroup(name=u'Systems', desc=u'IT stuff')
        self.session.add(test_workgroup)
        test_workgroup2 = Workgroup(name=u'Besteling', desc=u'Besteling at wholesale')
        self.session.add(test_workgroup2)
        self.session.flush() # flush now to get member and workgroup IDs
        test_member.workgroups.append(test_workgroup)
        test_shift = Shift(wg_id=test_workgroup.id, mem_id=test_member.id, year=2011, month=2)
        self.session.add(test_shift)
        self.session.flush()
        transaction.commit()

    def tearDown(self):
        s = self.session
        s.delete(s.query(Member).filter(Member.mem_fname == 'Peter').first())
        for wg_name in ['Systems', 'Besteling']:
            wg = s.query(Workgroup).filter(Workgroup.name == wg_name).first()
            for shift in s.query(Shift).filter(Shift.wg_id == wg.id).all():
                s.delete(shift)
            s.delete(wg)
        self.session.flush()
        transaction.commit()
        testing.tearDown()
    
    def test_member_query(self):
        peter = self.session.query(Member).filter(Member.mem_fname==u'Peter').first()
        self.assertEqual(peter.mem_lname, 'Pan')

    def test_wg_query(self):
        wgs = self.session.query(Workgroup).order_by(Workgroup.name).all()
        self.assertEqual(len(wgs), 2)
        self.assertEqual(wgs[0].name, 'Besteling')
    
    def test_member(self):
        peter = self.session.query(Member).filter(Member.mem_fname==u'Peter').first()
        def get_shifts():
            return self.session.query(Shift)\
                                .filter(Shift.mem_id == Member.id)\
                                .filter(Shift.mem_id == peter.id)
        shifts = get_shifts()
        self.assertEqual(shifts.count(), 1)
        shift = shifts.one()
        self.assertEqual(shift.mem_id, peter.id)
        shift.set_day(3)
        self.session.add(shift)
        self.session.flush()
        shifts = get_shifts()
        self.assertEqual(shift.day, 3)
    
    '''
    # TODO: test some view and template, maybe in another test case
    def test_it(self):
        from members.views.views import my_view
        request = testing.DummyRequest()
        info = my_view(request)
        self.assertEqual(info['members'][0].mem_fname, 'Peter')
        #self.assertEqual(info['project'], 'tutorial')
    '''
