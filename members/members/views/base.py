from webob import Response
from pyramid.renderers import get_renderer
from pyramid.security import authenticated_userid, remember
from pyramid.httpexceptions import HTTPFound

from members.security import authenticated_user
from members.models.setup import VokoValidationError


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

    def redirect(self, loc):
        """
        Redirect request to another location
        :param str loc: location (path after ${portal_url})
        :return: headers which should be returned by view
        """
        headers = remember(self.request, self.user.mem_id)
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
    The exception text could be shown nicer somehow, maybe we can pass sthg else in addition to msg?
    To set the status to 500 is important, so that the WSGI stack knows the issue has not actually
    been resolved, and rolls back any transactions for us.
    '''

    tab = 'home'

    def __call__(self):
        self.request.response.status_int = 500
        if self.context.__class__ == VokoValidationError:
            return dict(msg="Oops, please go back and reconsider. We don't want to save this as it is now.", info=str(self.context))
        else:
            return dict(msg="Sorry, something went wrong. If the error message below is not helpful, you maybe should contact an admin about this.",
                    info="Error message: '%s'" % str(self.context) )



