members app README


INSTALLATION

First, we create a virtaul python environment called "lopy":

# go to your home dir
$ cd
# install virtual environment (in ~/lopy)
$ wget https://raw.github.com/pypa/virtualenv/master/virtualenv.py
$ python virtual-python.py lopy
# install some needed libraries
$ cd lopy/bin
$ ./pip install pyramid

# install subversion if needed
TODO

# check out member app
$ cd <location of member app>
$ svn co TODO

# develop app
$ cd
$ ./lopy/bin/python setup.py develop
TODO: in production mode, what do we do there?

# do some Apache configuration
TODO

# start the server
$ cd <location of member app>
$ ./run 
