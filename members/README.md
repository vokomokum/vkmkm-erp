The vokomokum members application
==================================


This application governs people, work and money for the Vokomokum food coop.

Members have a workflow (applicant -> members <-> inactive).

Workgroup membership comes with roles: members and coordinators.

Shifts have a workflow (open <-> assigned -> worked or no-show)

Financial transactions have types and always have an opponent (members or suppliers, usually).
In the end, you'll get a double bookkeeping system.



Installation instructions
------------------------------
see INSTALL.md

For the below commands to work, do this:

    pip install 'fabric>=2.0'


Populate local test database with dummy data
---------------------------------------------

    fab populate
 

Starting the internal webserver 
--------------------------------
(use for development)

    fab serve


Running tests
-------------------------------

    fab test


Running version with dummy data as Docker container
----------------------------------------------------

    fab serve --docker

which (other than cleaning containers) does:

    docker pull vokomokum/members
    docker run --name=vkmkm -d -p 6543:6543 vokomokum/members

If you have the authorization, you can re-build and push the image:

    fab build_docker_image
