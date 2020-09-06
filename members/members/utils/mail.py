import subprocess
import os
from datetime import datetime
import logging

from members.utils.misc import get_settings


def sendmail(to, subject, body, folder='other', sender=None):
    '''
    Send a mail using a local mail program (like exim).
    Will save a time-stamped copy in a local folder, as well.

    :param string to: addressee
    :param string subject: subject of mail
    :param string body: content of mail
    :param string folder: a subfolder in which to put a copy
              (within the main mail_folder)
    :param string sender: senders address
    :returns: True if mail could be sent
              (if mail process returned successfully)
    '''
    settings = get_settings()
    mail_exec = settings['vokomokum.mail_exec']
    mail_folder = settings['vokomokum.mail_folder']
    mail_sender = settings['vokomokum.mail_sender']

    if not sender:
        sender = mail_sender
    mail = """From: %s
To: %s
Subject: %s

%s
""" % (sender, to, subject, body)
    error = ""
    mail_time = str(datetime.now()).replace(' ', '_').replace(':', '-')
    try:
        # try to send mail if our little custom test-workaround is not in place 
        if not 'DONOTACTUALLYSEND' in mail_exec:
            mailer = subprocess.Popen([mail_exec, "-t"],
                            stdin=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE)
            print >> mailer.stdin, mail
            mailer.stdin.close()
            result = mailer.wait()
            error = mailer.stderr.read()
            if result != 0:  # specific to exim?
                raise Exception(error)
        # save a copy if mailing succeeded (or if we used the workaround)
        target_folder = '{}/{}'.format(mail_folder, folder)
        if not os.path.exists(target_folder):
            os.mkdir(target_folder)
        mf = open('{}/{}.eml'.format(target_folder, mail_time), 'w')
        mf.write(mail)
        mf.close()
    except OSError as e:
        # log that it didn't work
        log = logging.getLogger(__name__)
        log.warn('Could not send mail to %s, subject "%s"'\
                 '(mail identifier is %s): %s'\
                  % (to, subject, mail_time, error))
        raise e
