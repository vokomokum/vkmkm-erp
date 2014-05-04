import unittest
from splinter import Browser

from members.tests.base import VokoE2ETestCase


class TestShiftsE2E(VokoE2ETestCase):

    def setUp(self):
        '''
        Establish the browser and login the admin user.
        Cleanup: close browser 
        '''
        super(TestShiftsE2E, self).setUp()
        self.year = 2011
        self.month = 5  # there should be no shifts in this month even in test db

    def testCreateShift(self):
        self.browser.visit('http://localhost:6543/workgroup/7/shifts/{y}/{m}'\
                            .format(y=self.year, m=self.month))
        self.browser.find_by_id('shift_creation_toggle').click()
        self.browser.fill('task','blatask')
        self.browser.find_by_id('create-btn').click()
        self.assertTrue(self.browser.is_element_present_by_value('blatask'))

