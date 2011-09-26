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
        self.layout = get_renderer('../templates/base.pt').implementation()

    @property
    def user(self):
        """
        :return: Database Member Object
        """
        return authenticated_user(self.request)


def NotFoundView(request):

    return Response(status = 404)


