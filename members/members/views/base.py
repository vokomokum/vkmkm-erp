from webob import Response
from pyramid.renderers import get_renderer
from pyramid.security import authenticated_userid

from members.security import authenticated_user


class BaseView(object):

    tab = 'home'

    def __init__(self, context, request):
        self.context = context
        self.request = request
        self.logged_in = authenticated_userid(request)
        # every template asks for the layout to look for the macros
        self.layout = get_renderer('../templates/base.pt').implementation()

    @property
    def user(self):
        """
        :return: Database Member Object
        """
        return authenticated_user(self.request)


class NotFoundView(BaseView):

    tab = 'home'

    def __call__(self):
        return dict(msg="Sorry, I could not find this location.")


class ErrorView(BaseView):

    tab = 'home'

    def __call__(self):
        return dict(msg="Sorry, something went wrong - maybe you should contact an admin about this. Error message: '%s'" % str(self.context) )



