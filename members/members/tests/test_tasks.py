from pyramid import testing

from members.tests.base import VokoTestCase
from members.views.workgroup import EditWorkgroupView
from members.models.workgroups import Workgroup
from members.models.shift import Shift
from members.models.task import Task
from members.models.member import Member


class TestTasks(VokoTestCase):
    ''' only integration/functional? '''

    def test_create(self):
        wg = self.DBSession.query(Workgroup).filter(Workgroup.name==u'Systems').first()
        self.assertEquals(len(wg.tasks), 0)
        request = testing.DummyRequest()
        request.matchdict = {'wg_id': wg.id}
        request.params['task_label'] = 'program assembler'
        request.params['action'] = 'add-task'
        view = EditWorkgroupView(None, request)
        view_info = view()
        wg = view_info['wg']
        self.assertEquals(len(wg.tasks), 1)
        self.assertEquals(wg.tasks[0].label, 'program assembler')

    def test_toggle_active(self):
        wg = self.DBSession.query(Workgroup).filter(Workgroup.name==u'Besteling').first()
        self.assertEquals(len(wg.tasks), 1)
        self.assertEquals(wg.tasks[0].active, True)
        request = testing.DummyRequest()
        request.matchdict = {'wg_id': wg.id}
        request.params['action'] = 'toggle-task-activity'
        request.params['task_id'] = wg.tasks[0].id
        view = EditWorkgroupView(None, request)
        view_info = view()
        self.assertEquals(view_info['wg'].tasks[0].active, False)
        view = EditWorkgroupView(None, request)
        view_info = view()
        self.assertEquals(view_info['wg'].tasks[0].active, True)

    def test_delete(self):
        wg = self.DBSession.query(Workgroup).filter(Workgroup.name==u'Besteling').first()
        self.assertEquals(len(wg.tasks), 1)
        request = testing.DummyRequest()
        request.matchdict = {'wg_id': wg.id}
        request.params['task_id'] = wg.tasks[0].id
        request.params['action'] = 'delete-task'
        view = EditWorkgroupView(None, request)
        view_info = view()
        self.assertIn('there are shifts in the history', view_info['msg'])
        self.assertEquals(len(view_info['wg'].tasks), 1)
        peter = self.DBSession.query(Member).filter(Member.mem_fname==u'Peter').first()
        shift = self.DBSession.query(Shift).filter(Shift.task_id == Task.id)\
                                           .filter(Shift.mem_id == peter.mem_id)\
                                           .filter(Task.wg_id == wg.id).first()
        self.DBSession.delete(shift)
        self.DBSession.flush()
        view_info = view()
        task = self.DBSession.query(Task).filter(Task.wg_id == wg.id).first()
        self.assertIsNone(task)


