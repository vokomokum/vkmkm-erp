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
    now = datetime.datetime.now()
    lmdate = now - datetime.timedelta(days=-info.days_in_month)
    dipm = monthrange(lmdate.year, lmdate.month)[1]
    one_month_back = date + datetime.timedelta(days=-dipm)
    one_month_ahead = date + datetime.timedelta(days=info.days_in_month)
    info.prev_month = one_month_back.month
    info.prev_year = one_month_back.year
    info.next_month = one_month_ahead.month
    info.next_year = one_month_ahead.year
    info.month_lies_in_past = date.year < now.year\
                                    or (date.year == now.year 
                                        and date.month < now.month) 
    return info
