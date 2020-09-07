import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.md')).read()

requires = [
    'pyramid>=1.5',
    'pyramid_chameleon',
    'SQLAlchemy',
    'transaction',
    'pyramid_tm',
    'pyramid_debugtoolbar',
    'zope.sqlalchemy',
    'waitress',
    'pytz',
    'dnspython',
    'passlib',
    'python-magic'
    ]

setup(name='members',
      version='1.0',
      description='Vokomokum members application',
      long_description=README,
      classifiers=[
        "Programming Language :: Python",
        "Framework :: Pylons",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        ],
      author='',
      author_email='',
      url='',
      keywords='web wsgi bfg pylons pyramid',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      test_suite='members',
      install_requires = requires,
      tests_require= requires + ['multidict'],
      entry_points = """\
      [paste.app_factory]
      main = members:main
      [console_scripts]
      populate_members = scripts.mksqlitedb:main
      """,
      )

