import subprocess
from datetime import datetime
import logging

# TODO: these settings should go in some .ini file
#mail_exec = "/usr/sbin/exim"
mail_exec = "/opt/local/sbin/exim"
mail_folder = "/Users/nic/Documents/vokomokum/members/mails"
mail_sender = 'systems@vokomokum.nl'


def sendmail(to, subject, body, sender=mail_sender):
    '''
    Send a mail using a local mail program (like exim).
    Will save a time-stamped copy in a local folder, as well.

    :param string to: addressee
    :param string subject: subject of mail
    :param string body: content of mail
    :param string sender: senders address
    :returns: True if mail could be sent
              (if mail process returned successfully)
    '''
    mail = """From: %s
To: %s
Subject: %s

%s
""" % (sender, to, subject, body)
    error = ""
    mail_time = str(datetime.now()).replace(' ', '_').replace(':', '-')
    try:
        # send mail
        mailer = subprocess.Popen([mail_exec, "-t"],
                        stdin=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE)
        print >> mailer.stdin, mail
        mailer.stdin.close()
        result = mailer.wait()
        error = mailer.stderr.read()
        # save a copy
        mf = open('%s/%s.eml' % (mail_folder, mail_time), 'w')
        mf.write(mail)
        mf.close()
        assert(result)
        return True
    except OSError, e:
        # log that it didn't work
        log = logging.getLogger(__name__)
        log.warn('Could not send mail to %s, subject "%s"'\
                 '(mail identifier is %s): %s'\
                  % (to, subject, mail_time, error))
        print error, e
        return False
