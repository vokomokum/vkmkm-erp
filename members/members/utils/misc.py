import pyramid


def get_settings():
    '''
    Get settings (from .ini file [app:main] section)
    Can also be accessed from the request object:
    request.registry.settings 
    '''
    registry = pyramid.threadlocal.get_current_registry()
    return registry.settings

