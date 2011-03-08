from webob import Response
from pyramid.renderers import get_renderer
from pyramid.security import authenticated_userid
#from security import authenticated_user


class BaseView(object):

    tab = 'members'

    def __init__(self, context, request):
        print "BASEVIEW init"
        self.context = context
        self.request = request
        self.logged_in = authenticated_userid(request)

        self.layout = get_renderer('../templates/base.pt').implementation()

    #@property
    #def user(self):
    #    """
    #    :return: Database User Object associated with the calling user
    #    """
    #    return authenticated_user(self.request)


def NotFoundView(request):

    return Response(status = 404)
