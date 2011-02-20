=======================
Maintenance scripts
=======================

Jim made some scripts to ease development by updating code and database instances for the order application. You can find them in the `dev-tools` directory. I'll mostly copy his words here.

They are initially conceived to make maintaining the app on our server easier. But you can also copy these scripts to your home machine (maybe you have to alter the paths etc.). With the scripts, so I can test at home knowing I'm using the svn version of the site (I also copy the database backups once per day, so I can test with a fairly current copy of the database)

-----------------------------------
Updating the server from svn
-----------------------------------

They check out the repository in a temporary directory and do some cleanups. Then in the checked-out repository, the script sets the ownership and permissions, as a last step it will copy everything into the web servers pages. 

For example::

    jes:/var/voko$ sudo ./update-test-from-svn
    Password:
    Removing previous svn-install directory if it exists
    A    vokomokum/trunk
    A    vokomokum/trunk/data
    ... snip svn checkout list ...
    Checked out revision 19.
    Temporary fixups - remove templates/templates/, remove RCS directories
    Set ownership apache:apache, premissions 775 on everything in order
    make template files group permissions 644
    make all directories under order/ 775
    now move everything onto the vokotest server
    jes:/var/voko$

The script update-main-from-svn works the same, but asks for confirmation before copying the files into the main site.


----------------------------
Updating the test database
----------------------------

There is also a script to help with testing. It allows you to copy one of the backups of either the test or the main database onto the test server. For example, if there's a problem report which occurred just after the order closed and you want to investigate the problem, you can simply fetch a copy of the main site database from before the order was closed (limit is one week of backups) and have it installed on the test site. You can do this repeatedly if you need to test solutions, you can move the order forward on the test site to see that things will work, etc.

The script begins by asking if you want to restore a backup of the main site database or the test site database (you might be testing some changes and have a modified test site database which you want to roll back, rather than fetching the main database and re-applying the database changes) It then gives a list of what should be available to restore, you specify the dat from from the list and the hour of the backup and it will do the rest. Run the script with sudo, otherwise you get asked 3 times for your password while it is running. I believe it all works correctly, but it would help if you also tried it because I can't check that the sudo su - jes -c some command will do what's needed, namely as root su to become me, then carry out the command (the database has ownership by user jes, because I originally created it, creating it as someone else will probably break things within the database)

An example of running it::

    $ sudo ./load-vokotest-db
    Password:
    Load a copy of the test-site database or a copy of the main site [TM]?M
    no  Day          First   Last
     1: Previous Sun 16:00 - 23:00
     2: Mon          00:00 - 23:00
     3: Tue          00:00 - 23:00
     4: Wed          00:00 - 23:00
     5: Thu          00:00 - 23:00
     6: Fri          00:00 - 23:00
     7: Sat          00:00 - 23:00
     8: Sun          00:00 - 15:00
    Enter the day number [1..8] and the hour - for example
     2 17
    would be 17:00 on the second day in the list
    Selection: 1 18
    DROP DATABASE
    CREATE DATABASE
    SET
    SET
    SET
    COMMENT
    ...[snip lots of psql output as the database is installed]...

And now the test site is in the exact state the main site was in just after 18:00 on the Sunday a week ago.

.. note: The script is hardcoded to the user jes, we should change that :)
