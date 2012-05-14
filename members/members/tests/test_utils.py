from pyramid import testing
from shutil import rmtree
import os

from members.utils import mail
from members.tests.base import VokoTestCase


class TestUtils(VokoTestCase):

    def setUp(self):
        super(VokoTestCase, self).setUp()
        path_to_here = '/'.join(os.path.realpath(__file__).split('/')[:-1])
        mail.mail_folder = '%s/.testmails' % path_to_here
        os.mkdir(mail.mail_folder)

    def tearDown(self):
        super(VokoTestCase, self).tearDown()
        rmtree(mail.mail_folder)

    def test_sendmail(self):
        to = 'me@host.de'
        subject = 'A vokomokum test'
        body = 'Bla\nBla'
        self.assertTrue(mail.sendmail(to, subject, body))
        # look up mail (only file in folder)
        mails = [m for m in os.listdir(mail.mail_folder) if m.endswith('.eml')]
        f = open('%s/%s' % (mail.mail_folder, mails[0]), 'r')
        _ = f.readline()
        self.assertEquals(f.readline(), 'To: %s\n' % to)
        self.assertEquals(f.readline(), 'Subject: %s\n' % subject)
        _ = f.readline()
        self.assertEquals(f.readline(), 'Bla\n')
        self.assertEquals(f.readline(), 'Bla\n')

