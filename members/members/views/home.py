from pyramid.view import view_config

from members.views.base import BaseView


@view_config(renderer='../templates/home.pt', route_name='home')
class HomeView(BaseView):

    def __call__(self):
        return dict()

