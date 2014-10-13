from pyramid.renderers import get_renderer
from pyramid.security import remember
from pyramid.httpexceptions import HTTPFound

import datetime

from members.utils.security import authenticated_user, authenticated_userid
from members.models.base import VokoValidationError
from members.utils.misc import get_settings


class BaseView(object):

    tab = 'home'
    _user = None

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.user = authenticated_user(self.request)
        self.logged_in = authenticated_userid(request) > -1
        # only show content if this is False or user is logged in
        # (otherwise, show login screen)
        self.login_necessary = True
        # came_from is actual path, or a special requested param.
        self.came_from = self.request.path
        # check URLs in came_from parameter against a whitelist if they are URLs    
        if 'came_from' in self.request.params:
            cf = self.request.params.get('came_from')
            if "://" in cf:
                s = get_settings()
                for url in s.get('vokomokum.whitelist_came_from').split(' '):
                    if (cf.startswith('http://{}'.format(url)) \
                        or cf.startswith('https://{}'.format(url))):
                        self.came_from = cf
                        break
            else:            
                self.came_from = cf
        # for submenus
        now = datetime.datetime.now()
        self.year = now.year
        self.month = now.month
        
        # general infos, messages
        if self.user and self.user.balance < 0:
            self.info = ' Your account balance is EUR {}! Please'\
                       ' transfer the missing amount to Vokomokum,'\
                       ' IBAN: NL49 TRIO 0786 8291 09, t.p.v. Amsterdam'\
                       ' (be sure to include your member number)'\
                       ' and contact finance@vokomokum.nl to report'\
                       ' that you have paid.'\
                       .format(round(self.user.balance, 2))   
        if self.user and not self.user.mem_active:
            self.msg = 'Your account is currently not active. This means you'\
                       ' cannot place or change orders. Contact membership@vokomokum.nl'\
                       ' for any questions.' 

        # every template asks for the layout to look for the macros
        self.layout = get_renderer('../templates/base.pt').implementation()

    @property
    def user(self):
        """
        :returns: Database Member Object
        """
        return self._user

    @user.setter    
    def user(self, m):
        """
        Sets the user of the view, useful for testing
        :param Member m: Member to be set as user
        """
        self._user = m

    def redirect(self, loc):
        """
        Redirect request to another location
        :param str loc: location (path after ${portal_url} or full URL)
        :return: headers which should be returned by view
        """
        uid = -1
        if self.user:
            uid = self.user.mem_id
        headers = remember(self.request, uid)
        return HTTPFound(location = loc, headers = headers)


class NotFoundView(BaseView):

    tab = 'home'

    def __call__(self):
        self.request.response.status_int = 404
        return dict(msg="Sorry, I could not find this location.")


class ErrorView(BaseView):
    '''
    A catch-all error view.
    It will simply show the base template and excuse the eception.
    The exception text could be shown nicer somehow, maybe we can pass
    something else in addition to msg?
    To set the status to 500 is important, so that the WSGI stack knows the 
    issue has not actually been resolved, and rolls back any transactions
    for us.
    '''

    tab = 'home'

    def __call__(self):
        self.request.response.status_int = 500
        if self.context.__class__ == VokoValidationError:
            return dict(msg="Oops, please go back and reconsider. We don't "\
                    "want to save this as it is now.", info=str(self.context))
        else:
            return dict(msg="Sorry, something went wrong. If the error "\
                    "message below is not helpful, you maybe should contact "\
                    "an admin about this.",
                    info="Error message: '%s'" % str(self.context) )
