import pyramid

import datetime
from calendar import monthrange


def get_settings():
    '''
    Get settings (from .ini file [app:main] section)
    Can also be accessed from the request object: request.registry.settings 
    '''
    registry = pyramid.threadlocal.get_current_registry()
    return registry.settings

def ascii_save(s):
    '''
    Not exactly perfect way to make Ascii from unicode,
    we might want to use the Unidecode module (see on pypi)
    '''
    return s.encode('ascii', 'replace')

def running_sqlite():
    '''
    True if app is currently running on sqlite (thus, probably in dev mode
    or testing)
    '''
    settings = get_settings()
    return settings['sqlalchemy.url'].startswith('sqlite:')

def month_info(date):
    ''' 
    Return useful info about the month in the given date object:
    A dict containing number of days, previous month index,
    previous year index, next month index, next year index.
    '''
    class MInfo(object):
        days_in_month = 0
        prev_month = 0
        prev_year = 0
        next_month = 0
        next_year = 0
        month_lies_in_past = True

    info = MInfo()
    info.days_in_month = monthrange(date.year, date.month)[1]
    a_pm_date = date + datetime.timedelta(days=-(date.day + 1))
    dipm = monthrange(a_pm_date.year, a_pm_date.month)[1]
    one_month_back = date + datetime.timedelta(days=-dipm)
    one_month_ahead = date + datetime.timedelta(days=info.days_in_month)
    info.prev_month = one_month_back.month
    info.prev_year = one_month_back.year
    info.next_month = one_month_ahead.month
    info.next_year = one_month_ahead.year
    now = datetime.datetime.now()
    info.month_lies_in_past = date.year < now.year\
                                    or (date.year == now.year 
                                        and date.month < now.month) 
    return info
