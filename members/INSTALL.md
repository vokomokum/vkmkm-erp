INSTALLATION
====================

This describes what you need to do to install the members app locally and/or on a webserver. I hope it is complete and correct, contact me if something is wrong, please. -Nic

First, the dependencies:
-------------------------

You should have a modern python (3.6+) and a database on your system.
The production version uses postgres, locally you can also use sqlite3, with maybe not all features working, but a much easier installation.
To get and update the member app code, you also need git.
This app is meant to be run via Apache when in production (installation help for the link from Apache to this app are also below), but can be run locally with the simple, in-built server.

To begin, we create a virtual python environment with all needed Python libraries
------------------------------------------------------------------------------------

In this tutorial, let's pretend that it goes in your home dir (but you can put it anywhere you want):
$ cd ~

Now we get the standard python script that will set up the virtual python environment.
If you have the ``virtualenv`` command, great. Do this:
$ virtualenv --python python3.8 vopy

If not, do this:
$ wget https://raw.github.com/pypa/virtualenv/master/virtualenv.py
Note that if you haven't got ``wget`` or if you have problems with the SSL certificate, you can also access this file with your browser and do a "Save as ..." to get the script.

Also, make sure your virtual environment is built with the python you want. On some systems, several python interpreters are installed, for instance 2.7 and 3.6, or even two installations of the same version (e.g. Apples default vs a manual installation). 
Here, we are explicit and say "python3.8" ("python would just use the first in your path). Also, we call this environment ``vopy``, which makes virtualenv.py create a directory with that name:
$ python3.8 virtualenv.py your_venv

If you downloaded it, you can remove that script now:
$ rm virtualenv.py

We can now activate this python environment for the current console session (which has the same effect as adding the bins to your path, e.g. by doing `export PATH=path/to/your_venv/bin/:$PATH` but this way there will be no interference with the rest of your system):
$ source path/to/your_venv/bin/activate
You should now see the name of the virtual environment in front of your console now, like this:
[your_venv] $
Make sure you always activate your virtual environment, before you work with the web app in this local setup - otherwise, you might end up using different versions of these programs somewhere else on your computer, which can have any number of different outcomes (this kind of developer headache is what virtual environments are here to solve).


Now we're ready to install some libraries into the virtual python environment, which our app might be using:
$ pip install fabric>=2.0   # Unix/SSH scripting environment for Python,
                             # handy to easily do the things described in `fabfile.py`, usually via `fab <command>`.
                             # If you don't install fabric, look inside the fabfile for the actual commands

If there is an error installing fabric, this might help (on Debian, adjust on other systems):
$ sudo apt-get install libssl-dev

$ pip install psycopg2       # Postgres wrapper for Python, install if you are creating a production(-like) system
                             # (otherwise, e.g. for development, you'd use sqlite3 which is built into python).


Now we get the code (if you don't have it already)
----------------------------------------------------

$ cd <location where you want vokomokum code to live>
$ git clone git://git.github.com/vokomokum/vkmkm-erp.git
This will give you a read-only clone of the code.
To get a clone you can commit back to the server as a member of the vokomokum
dev team, you should do this:
$ git clone git@git.github.com:vokomokum/vkmkm-erp.git
However, to authenticate with github, you need an github account and an
authentication setup. See here: https://www.github.com/code/vokomokum/git/repo/instructions


Develop the app 
--------------------
(this also installs all other needed python libs for the webapp, locally in that folder)
$ cd vkmkm-erp/members
$ fab develop


Last step: Initialise the database
----------------------------------------------------------------------------------------------------
If you want to simply create a test environment and if you are happy with some dummy data, then you'll need to install the sqlite database software.

For example, on Debian-based Linux (e.g. Ubuntu):

$ sudo apt-get install sqlite3

On OSX, you might use MacPorts for this.

Then, all you need to do is:

$ fab populate

This will create an sqlite database and fill it with some data, so you can start. You may skip to the next step.

If you want to use an existing sqlite database or run on Postgres, open the .ini file (development.ini [default] or production.ini) and change the database URL. Here is a typical line, when using Postgres:
<<<
sqlalchemy.url = postgresql+psycopg2://user:passwd@localhost:5432/vokotest
>>>
where vokotest is the database, and user and passwd have to be set by you.
It seems reasonable that development.ini uses a different database than production.ini


Now it's time to see if the App is served correctly through its own simple development server 
----------------------------------------------------------------------------------------------------
(if you can access localhost, e.g. on your home PC)

$ fab serve
The Member application should now respond under http://localhost:6543.

If you successfully ran the `fab populate` command in the step above, you can log in with ID 3 and password "notsecret".
This is a convenient way to test if everything is there.
To stop the server, do a CTRL-C.

Note that the fab serve command loads development.ini by default (because the local server is usually used for testing).
You can change that (in the fabfile) if you need production.ini.



We now turn to installation for what we need to let Apache serve the app (via mod_wsgi).
----------------------------------------------------------------------------------------------------

1. Download the latest mod_wsgiX.X.tar.gz from http://code.google.com/p/modwsgi (currently: X.X=3.3)
You can do this in your home dir
$ cd
$ wget http://modwsgi.googlecode.com/files/mod_wsgi-3.3.tar.gz
Untar it to some place, then cd into that dir 
$ tar -zxf mod_wsgi-3.3.tar.gz
$ cd mod_wsgi-3.3
$ ./configure --with-python=/home/nic/vopy/bin/python
$ make
$ sudo make install
(you can remove the downloaded file/directory later, once mod_wsgi has been installed in Apache)
Note that I my virtual environment is called "vopy" here.

2. Now make sure that Apache knows about mod_wsgi - add the following line to /etc/apache2/httpd.conf:
``LoadModule wsgi_module modules/mod_wsgi.so``
Or, on OSX (tested on 10.6, so this might be outdated):
``LoadModule wsgi_module libexec/apache2/mod_wsgi.so``

3. Restart the Apache server
$ sudo /etc/init.d/apache2 restart
Or, on OSX 10.6:
$ sudo /usr/sbin/apachectl restart
In /var/log/apache2/error_log, there should be a mention of mod_wsgi being reconfigured like this:
``[Mon Jan 02 00:06:56 2012] [notice] Apache/2.2.20 (Unix) mod_ssl/2.2.20
OpenSSL/0.9.8r DAV/2 mod_wsgi/3.3 Python/2.7.1 configured -- resuming normal operations``

See also: http://code.google.com/p/modwsgi/wiki/QuickInstallationGuide


Now we do some Apache configuration (this is for Apache2 on OSX, some things might be different on other Unix systems)
------------------------------------------------------------------------------------------------------------------------

1. In the directory where your Apache looks for config files (e.g. /etc/apache2/vhosts.d or /etc/apache2/other), place a file with this content:
<<<
WSGIPythonHome /home/nic/vopy

NameVirtualHost 127.0.0.1
<VirtualHost 127.0.0.1>
    ServerName members.localhost

    <Directory />
        Order allow,deny
        Allow from all
    </Directory>

    WSGIApplicationGroup %{GLOBAL}
    WSGIDaemonProcess pyramid.dev display-name=%{GROUP} 
    #   user=nic group=staff \ 
    #   python-path=/home/nic/vopy/lib/python2.7/site-packages
    WSGIProcessGroup pyramid.dev
    WSGIScriptAlias / /home/nic/Documents/vokomokum/members/pyramid.wsgi
</VirtualHost>
>>>

Replace ``WSGIPythonHome`` with the path to the virtual python environment we made earlier, ``ServerName`` with the URL you want the app to be reachable,
and 127.0.0.1 with *:80 if you are on a web server. Also adapt the path to the ``pyramid.wsgi`` script.
Hint 1: In ``pyramid.wsgi``, ``production.ini`` can be replaced by ``development.ini`` for easier debugging and such niceties. This is useful if you are running a test or developing version.
Hint 2: You can look for documentation on mod_wsgi directives here: ``http://code.google.com/p/modwsgi/wiki/ConfigurationDirectives``

2. You also need to make the URL on which the app should be reachable known to the server.
On my local machine, I want to reach it at 'members.localhost', so I add a line to ``/etc/hosts`` (in this case: ``127.0.0.1      members.localhost``).
On a web server, you might need to add a DNS entry (most likely via your webhosters administration).

3. Now restart the Apache server
$ sudo /usr/sbin/apachectl restart

Note: To make Apache aware of code updates, it is usually enough to touch the `pyramid.wsgi` file
(see also the deploy command within `fabfile.py`), so restarting Apache is usually not necessary.
