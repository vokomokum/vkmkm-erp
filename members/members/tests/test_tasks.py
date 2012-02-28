from pyramid import testing

from members.tests.base import VokoTestCase
from members.views.workgroup import WorkgroupEditView
from members.models.workgroups import Workgroup
from members.models.shift import Shift
from members.models.task import Task


class TestTasks(VokoTestCase):
    ''' only integration/functional? '''

    def test_create(self):
        wg = self.DBSession.query(Workgroup).filter(Workgroup.name==u'Systems').first()
        self.assertEquals(len(wg.tasks), 0)
        request = testing.DummyRequest()
        request.matchdict = {'wg_id': wg.id}
        request.params['task_label'] = 'program assembler'
        request.params['action'] = 'add-task'
        view = WorkgroupEditView(None, request)
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
        view = WorkgroupEditView(None, request)
        view_info = view()
        self.assertEquals(view_info['wg'].tasks[0].active, False)
        view = WorkgroupEditView(None, request)
        view_info = view()
        self.assertEquals(view_info['wg'].tasks[0].active, True)

    def test_delete(self):
        wg = self.DBSession.query(Workgroup).filter(Workgroup.name==u'Besteling').first()
        self.assertEquals(len(wg.tasks), 1)
        request = testing.DummyRequest()
        request.matchdict = {'wg_id': wg.id}
        request.params['task_id'] = wg.tasks[0].id
        request.params['action'] = 'delete-task'
        view = WorkgroupEditView(None, request)
        view_info = view()
        self.assertIn('there are shifts in the history', view_info['msg'])
        self.assertEquals(len(view_info['wg'].tasks), 1)
        shift = self.DBSession.query(Shift).filter(Shift.task_id == Task.id)\
                                           .filter(Task.wg_id == wg.id).first()
        self.DBSession.delete(shift)
        self.DBSession.flush()
        view_info = view()
        task = self.DBSession.query(Task).filter(Task.wg_id == wg.id).first()
        self.assertIsNone(task)


