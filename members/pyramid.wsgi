import os, sys
from pyramid.paster import get_app

# these 3 lines should not be necessary, but they might
# be needed if Apache does not use this dir as working directory
abspath = os.path.dirname(__file__)
sys.path.append(abspath)
os.chdir(abspath)

# we know where this wsgi script (__file__) is, and the .ini is in the same dir
mem_dir = '/'.join(os.path.realpath(__file__).split('/')[0:-1])
# use production.ini on production systems, development.ini when testing
application = get_app('%s/development.ini' % mem_dir, 'main')
