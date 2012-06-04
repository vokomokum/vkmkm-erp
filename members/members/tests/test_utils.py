from pyramid import testing
import os

from members.utils import mail
from members.utils.misc import get_settings
from members.tests.base import VokoTestCase


class TestUtils(VokoTestCase):

    def test_sendmail(self):
        to = 'me@host.de'
        subject = 'A vokomokum test'
        body = 'Bla\nBla'
        mail.sendmail(to, subject, body)
        # look up mail (only file in folder)
        mail_folder = get_settings()['vokomokum.mail_folder']
        mails = [m for m in os.listdir(mail_folder) if m.endswith('.eml')]
        f = open('%s/%s' % (mail_folder, mails[0]), 'r')
        _ = f.readline()
        self.assertEquals(f.readline(), 'To: %s\n' % to)
        self.assertEquals(f.readline(), 'Subject: %s\n' % subject)
        _ = f.readline()
        self.assertEquals(f.readline(), 'Bla\n')
        self.assertEquals(f.readline(), 'Bla\n')

