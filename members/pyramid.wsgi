import os, sys
from pyramid.paster import get_app

# we know where this wsgi script (__file__) is, and the .ini is in the same dir
mem_dir = '/'.join(os.path.realpath(__file__).split('/')[0:-1])
# use production.ini on production systems, development.ini when testing
application = get_app('%s/development.ini' % mem_dir, 'main')

