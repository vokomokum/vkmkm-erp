import os
import sys

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.txt')).read()

requires = [
    'pyramid',
    'SQLAlchemy',
    'transaction',
    'repoze.tm2>=1.0b1', # default_commit_veto
    'zope.sqlalchemy',
    'WebError',
    ]

if sys.version_info[:3] < (2,5,0):
    requires.append('pysqlite')

setup(name='members',
      version='0.1',
      description='members',
      long_description=README,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pylons",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='Nicolas Honing',
      author_email='nhoening@gmail.com',
      url='',
      keywords='vokomokum food cooperative members shifts',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      test_suite='members',
      install_requires = requires,
      entry_points = """\
      [paste.app_factory]
      main = members:main
      """,
      paster_plugins=['pyramid'],
      )

