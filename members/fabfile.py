from fabric.api import *
from fabric.contrib.console import confirm

'''
This file is very useful in day-to-day Vokomokum development.
It uses fabric to automate common actions. Install fabric by 
$VIRPY/bin/pip install fabric

Then it suffices to issue 
fab develop         # develop the webapp locally
fab serve           # run local dev server
fab test            # run test, add module=test-module-name if you want 
fab commit          # commit changed code (interactively)
fab push            # push commits
fab populate        # populate local test DB (sqlite) with dummy data
fab prepare_deploy  # run tests and if successful, push all code to git
                    # (actually runs fab test, fab commit and fab push)
fab deploy:user=you # deploy latest code on our server and set it 'live'
                    # (you need admin rights for this on the server)

Note: $VIRPY should point at your python environment (see INSTALL.txt)
'''
env.hosts = ['order.vokomokum.nl']
#env.use_ssh_config = True # we may want this

def develop():
    ''' develop the webapp locally '''
    local('$VIRPY/bin/python setup.py develop')

def serve():
    ''' run local dev server '''
    local('$VIRPY/bin/pserve development.ini --reload')

def test(standalone=True, module=None):
    '''
    Perfom tests. You can pick a module (leave members.tests." off and also ".py").
    standalone means other commands follow, so an error prompts if to quit.
    '''
    # Note: The setuptools environment is notorious for uninformative error messages 
    # when imports went bad. It will tell you which module is the problem, but only
    # say sthg about an AttributeError. Do this to find out what is wrong:
    # $ $VIRPY/bin/python setup.py develop
    # $ $VIRPY/bin/python -c "import members.tests.<The module in question>"
    with settings(warn_only=True):
        if not module:
            result = local('$VIRPY/bin/python setup.py test -q', capture=False)
        else:
            result = local('$VIRPY/bin/python setup.py test -s members.tests.{}'.format(module), capture=False)
    if result.failed and not standalone and not confirm("Tests failed. Continue anyway?"):
        abort("Aborting at user request.")

def commit():
    ''' commit changed code (interactively)'''
    local("git add -p && git commit")

def push():
    ''' push commited code to server '''
    local("git push")

def populate():
    ''' populate local test DB (sqlite) with dummy data.
        Uses members-dev.db, which is also named in development.ini as DB
    '''
    local("python scripts/mksqlitedb.py")

def prepare_deploy():
    '''
    run tests and if successful, push all code to git
    (actually runs fab test, fab commit and fab push)
    '''
    test(standalone=False)
    commit()
    push()

def deploy(user='you', mode="test", branch="master"):
    '''
    deploy latest code on our server and set it 'live'
    (you need admin rights for this on the server)
    Be sure to use :user=you for sudo commands to succeed.
    Use :user=you,mode=production to update the production app.
    '''
    test(standalone=False)
    push()
    env.user = user
    code_dir = '/var/voko/git-repo'
    # this is only useful when we'd run multiple server nodes
    with settings(warn_only=True):
        if run("test -d {}".format(code_dir)).failed:
            sudo("git clone git@git.assembla.com:vokomokum.git {}".\
                     format(code_dir), user=user)
    with cd(code_dir):
        sudo("./dev-tools/update-members-site-from-git {} {}".format(mode, branch))
        # no need to restart apache, simply touch wsgi file (when in daemon mode)
        # (see http://code.google.com/p/modwsgi/wiki/ReloadingSourceCode)
        if mode == 'production':
            sudo("touch /var/www/members/pyramid.wsgi", user=user)
        else:
            sudo("touch /var/www/memberstest/pyramid.wsgi", user=user)
        #run(sudo("/etc/init.d/apache2 restart"))
