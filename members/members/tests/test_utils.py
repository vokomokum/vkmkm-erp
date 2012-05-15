from pyramid import testing
import os

from members.utils import mail
from members.tests.base import VokoTestCase


class TestUtils(VokoTestCase):

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

