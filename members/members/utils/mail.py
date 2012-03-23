import subprocess

#TODO:
# - configurable way to write email in file when testing
# - different senders needed? What is the best default?

sender = 'systems@vokomokum.nl'
mail_exec = "/usr/sbin/exim"

def sendmail(to, subject, body):
    mailer = subprocess.Popen([mail_exec, "-t"], stdin = subprocess.PIPE)
    print >>mailer.stdin, """From: %s
    To: %s
    Subject: %s

    %s
    """ % (sender, to, subject, body)
    mailer.stdin.close()
    result = mailer.wait()
    return result
