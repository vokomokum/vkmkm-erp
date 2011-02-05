import unittest
from pyramid.config import Configurator
from pyramid import testing

def _initTestingDB():
    from sqlalchemy import create_engine
    from members.models import initialize_sql
    session = initialize_sql(create_engine('sqlite://'))
    #session = initialize_sql(create_engine('postgres://'))
    return session

class TestMyView(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()
        _initTestingDB()

    def tearDown(self):
        testing.tearDown()

    def test_it(self):
        from members.views import my_view
        request = testing.DummyRequest()
        info = my_view(request)
        self.assertEqual(info['member'].mem_fname, 'Peter')
        #self.assertEqual(info['project'], 'tutorial')
