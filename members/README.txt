members README
==================

Installation instructions
------------------------------
see INSTALL.txt

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

docker pull nhoening/vokomokum-members
docker run --name=vkmkm -d -p 6543:6543 vokomokum-members
