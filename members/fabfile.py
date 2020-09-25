import getpass

from fabric import task
from fabric import Connection, Config
from invoke import Exit
from invocations.console import confirm

'''
This file is very useful in day-to-day Vokomokum development.
It uses fabric to automate common actions. Install fabric with

$ pip install "fabric>=2.0" invocations


Then it suffices to issue 
fab develop         # develop the webapp locally
fab serve           # run local dev server
fab test            # run test
fab commit          # commit changed code (interactively)
fab push            # push commits
fab populate        # populate local test DB (sqlite) with dummy data
fab prepare_deploy  # run tests and if successful, push all code to git
                    # (actually runs fab test, fab commit and fab push)
fab deploy:user=you # deploy latest code on our server and set it 'live'
                    # (you need admin rights for this on the server)

'''
vkmkm_hosts = ['order.vokomokum.nl']
path_to_venv = "/home/nicolas/envs/vkmkm"
venv_activation = "source {}/bin/activate".format(path_to_venv)
docker_image = "nhoening/vokomokum-members"

@task
def develop(c):
    ''' develop the webapp locally '''
    with c.prefix(venv_activation):
        c.run('python setup.py develop')

@task
def serve(c, docker=False):
    ''' Run local dev server.
    If --docker, then the docker imagge with dummy data is pulled and used.
    '''
    if docker:
        print("Stopping and removing existing vkmkm containers ....")
        c.run("docker stop vkmkm", warn=True)
        c.run("docker rm vkmkm", warn=True)
        print("Pulling and serving docker image ...")
        c.run(f"docker pull {docker_image}")
        c.run(f"docker run --name=vkmkm -d -p 6543:6543 {docker_image}")
    else:
        print("Serving via development.ini ...")
        with c.prefix(venv_activation):
            c.run('pserve development.ini --reload')

@task
def test(c, standalone=True):
    '''
    perfom tests
    '''
    with c.prefix(venv_activation):
        c.run("pip install -q pytest multidict")
        result = c.run('pytest', warn=True)
        if result.failed and not standalone and not confirm("Tests failed. Continue anyway?"):
            raise Exit("Aborting at user request.")

@task
def commit(c):
    ''' Commit changed code (interactively)'''
    c.run("git add -p && git commit")

@task
def push(c):
    ''' Push commited code to server '''
    c.run("git push")

@task
def populate(c):
    ''' Populate local test DB (sqlite) with dummy data.
        Uses members-dev.db, which is also named in development.ini as DB
    '''
    with c.prefix(venv_activation):
        c.run("python scripts/mksqlitedb.py")

@task
def build_docker_image(c):
    '''
    Build the Docker image and possibly upload it
    '''
    c.run(f"docker build . --tag {docker_image}")
    if confirm("Upload image to docker registry?"):
        c.run(f"docker push {docker_image}")

@task
def prepare_deploy(c):
    '''
    Run tests and if successful, push all code to git
    (actually runs fab test, fab commit and fab push)
    '''
    test(c, standalone=False)
    commit(c)
    push(c)

@task(hosts=vkmkm_hosts)
def deploy(c, user=None, mode="test", branch="master"):
    '''
    Deploy latest code on our server and set it 'live'
    (you need admin rights for this on the server)
    Be sure to use --user=you for sudo commands to succeed.
    Also, use --mode=production to update the production app.
    Finally, fabric accepts a few parameters so you handle your ssh key
    correctly. For instance, you might need to use:
    --identity=path/to/your/provate/key
    --prompt-for-passphrase
    See Fabrics's (>=2.0) documentation for more details.
    '''
    if not user:
        raise Exit("Please provide a user name for use on the server")

    # make sure we don't deploy untested or outdated code
    #test(c, standalone=False)  # Here, c is a Connection, not a Context, so this would need work
    #push(c)
    if not confirm("Have you tested and pushed your code?? (You can use `fab prepare_deploy`)"):
        raise Exit("Aborting at user request.")
    
    code_dir = "/var/voko/git-repo"
    app_dir = "/var/www"
    
    # make sure we have the code cloned on the server   
    if not c.run(f"test -d {code_dir}", warn=True):
        c.run(f"git clone git@github.com:vokomokum/vkmkm-erp.git {code_dir}", user=user)
    
    # make sure sudo command can be used
    sudo_pass = getpass.getpass(f"What's the sudo password for user {user}?")
    c.config = Config(overrides={'sudo': {'password': sudo_pass}})
    
    #with cd(code_dir):  # not yet implemented in fabric2 and sudo does not remember cd
    c.sudo(f"{code_dir}/dev-tools/update-members-site-from-git {mode} {branch}")
    # no need to restart apache, simply touch wsgi file (when in daemon mode)
    # (see http://code.google.com/p/modwsgi/wiki/ReloadingSourceCode)
    if mode == 'production':
        c.sudo(f"touch {app_dir}/members/pyramid.wsgi")
    else:
        c.sudo(f"touch {app_dir}/memberstest/pyramid.wsgi")
    #c.sudo("/etc/init.d/apache2 restart")
