from pyramid import testing

from members.tests.base import VokoTestCase
from members.views.workgroup import WorkgroupView
from members.models.workgroups import Workgroup
from members.models.member import Member


class TestTasks(VokoTestCase):
    ''' only integration/functional? '''

    def test_tasks(self):
        request = testing.DummyRequest()
        request.params['action'] = 'save'
        view_info = WorkgroupView(None, request)()
        self.assertEqual(1, 2)
