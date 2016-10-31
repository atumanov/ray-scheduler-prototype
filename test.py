import unittest
import os

# TODO both of these needed?
import replaystate
from replaystate import *

class TestEventLoopTimers(unittest.TestCase):
    def setUp(self):
        self.ts = SystemTime()
        self.event_loop = EventLoop(self.ts)
        self.callback_contexts = []

    class CallbackContext():
        def __init__(self, test, ts_expected):
            self.test = test
            self.did_execute = False
            self.ts_expected = ts_expected
            test.callback_contexts.append(self)

    @staticmethod
    def basic_handler(context):
        context.did_execute = True
        context.ts_executed = context.test.ts.get_time()

    @staticmethod
    def active_handler(context):
        TestEventLoopTimers.basic_handler(context)
        context.fn()

    class ActiveCallback(CallbackContext):
        def __init__(self, test, ts_expected, fn):
            TestEventLoopTimers.CallbackContext.__init__(self, test, ts_expected)
            self.fn = fn

    def check_all_executed(self):
        for callback_context in self.callback_contexts:
            self.assertTrue(callback_context.did_execute)
            self.assertEquals(callback_context.ts_expected, callback_context.ts_expected)

    def test_no_events(self):
        start_time = self.ts.get_time()
        self.assertTrue(self.event_loop.is_stopped)
        self.event_loop.run()
        self.assertTrue(self.event_loop.is_stopped)
        self.assertEquals(start_time, self.ts.get_time())

    def test_one_event(self):
        start_time = self.ts.get_time()
        self.event_loop.add_timer(2, TestEventLoopTimers.basic_handler, TestEventLoopTimers.CallbackContext(self, start_time + 2))
        self.event_loop.run()
        self.check_all_executed()
        self.assertEquals(start_time + 2, self.ts.get_time())

    def test_two_events(self):
        start_time = self.ts.get_time()
        self.event_loop.add_timer(5, TestEventLoopTimers.basic_handler, TestEventLoopTimers.CallbackContext(self, start_time + 5))
        self.event_loop.add_timer(2, TestEventLoopTimers.basic_handler, TestEventLoopTimers.CallbackContext(self, start_time + 2))
        self.event_loop.run()
        self.check_all_executed()
        self.assertEquals(start_time + 5, self.ts.get_time())

    def test_chained_events(self):
        start_time = self.ts.get_time()
        self.assertTrue(self.event_loop.is_stopped)
        def callback_action():
            self.assertFalse(self.event_loop.is_stopped)
            self.event_loop.add_timer(5, TestEventLoopTimers.basic_handler, TestEventLoopTimers.CallbackContext(self, start_time + 7))
        self.event_loop.add_timer(2, TestEventLoopTimers.active_handler, TestEventLoopTimers.ActiveCallback(self, start_time + 2, callback_action))
        self.event_loop.run()
        self.assertTrue(self.event_loop.is_stopped)
        self.check_all_executed()
        self.assertEquals(start_time + 7, self.ts.get_time())

    def test_one_event_cancelled(self):
        start_time = self.ts.get_time()

        def callback_action():
            self.fail('should not have called this')

        callback = TestEventLoopTimers.ActiveCallback(self, start_time + 2, callback_action)
        timer_id = self.event_loop.add_timer(2, TestEventLoopTimers.active_handler, callback)
        self.event_loop.remove_timer(timer_id)
        self.event_loop.run()
        # TODO - not sure that cancelled event should advance the clock, but right now it does
        self.assertEquals(start_time + 2, self.ts.get_time())

    def test_cancel_future(self):
        start_time = self.ts.get_time()

        def failure_action():
            self.fail('should not have called this')

        callback_ts_5 = TestEventLoopTimers.ActiveCallback(self, start_time + 5, failure_action)
        timer_id_ts_5 = self.event_loop.add_timer(5, TestEventLoopTimers.active_handler, callback_ts_5)

        def cancel_action():
            self.event_loop.remove_timer(timer_id_ts_5)

        callback_ts_2 = TestEventLoopTimers.ActiveCallback(self, start_time + 2, cancel_action)
        self.event_loop.add_timer(2, TestEventLoopTimers.active_handler, callback_ts_2)
        self.event_loop.run()
        self.assertFalse(self.callback_contexts[0].did_execute)
        self.assertTrue(self.callback_contexts[1].did_execute)
        # TODO - not sure that cancelled event should advance the clock, but right now it does
        self.assertEquals(start_time + 5, self.ts.get_time())


class TestInvalidTrace(unittest.TestCase):
    def __init__(self, name):
        self._method_name = 'test_inv_' + name
        super(TestInvalidTrace, self).__init__(self._method_name)
        self._name = name

    def __getattr__(self, name):
        if name == self._method_name:
            return self.runTest

    def runTest(self):
        import json
        input_fn = os.path.join(script_path(), 'traces', 'invalid', self._name + '.json')
        with self.assertRaises(ValidationError):
            try:
                f = open(input_fn, 'r')
                return json.load(f, object_hook=computation_decoder)
            finally:
                f.close()


def invalid_trace_suite():
    import glob
    files = glob.glob(os.path.join(script_path(), 'traces', 'invalid', '*.json'))
    test_names = list(map(lambda x: os.path.splitext(os.path.split(x)[1])[0], files))
    test_names.sort()
    return unittest.TestSuite(map(TestInvalidTrace, test_names))


def script_path():
    return os.path.dirname(os.path.realpath(__file__))


class TestComputationObjects(unittest.TestCase):

    def test_equality_finish_task_update(self):
        self.assertEquals(FinishTaskUpdate(task_id = 1), FinishTaskUpdate(task_id = 1))
        self.assertEquals(FinishTaskUpdate(task_id = 1), FinishTaskUpdate(task_id = '1'))


class TestSchedulerObjects(unittest.TestCase):
    def test_equality(self):
        phase_0_0 = TaskPhase(phase_id = 0, depends_on = [], submits = [], duration = 1.0)
        task_0 = Task(task_id = 1, phases = [phase_0_0], results = [TaskResult(object_id = 0, size = 100)])

        phase_1_0 = TaskPhase(phase_id = 0, depends_on = [], submits = [], duration = 1.0)
        task_1 = Task(task_id = 2, phases = [phase_1_0], results = [TaskResult(object_id = 2, size = 100)])

        self.assertEquals(SubmitTaskUpdate(task_0, 2), SubmitTaskUpdate(task_0, 2))
        self.assertNotEquals(SubmitTaskUpdate(task_0, 2), SubmitTaskUpdate(task_1, 2))
        self.assertNotEquals(SubmitTaskUpdate(task_0, 2), SubmitTaskUpdate(task_0, 3))

        self.assertEquals(RegisterNodeUpdate(node_id = 1, num_workers = 1), RegisterNodeUpdate(node_id = 1, num_workers = 1))
        self.assertNotEquals(RegisterNodeUpdate(node_id = 1, num_workers = 1), RegisterNodeUpdate(node_id = 2, num_workers = 1))
        self.assertNotEquals(RegisterNodeUpdate(node_id = 1, num_workers = 1), RegisterNodeUpdate(node_id = 1, num_workers = 2))

        self.assertItemsEqual([RegisterNodeUpdate(node_id = 1, num_workers = 1)], [RegisterNodeUpdate(node_id = 1, num_workers = 1)])


class TestReplayState(unittest.TestCase):


    def setUp(self):
        self.system_time = SystemTime()
        self.event_loop = EventLoop(self.system_time)
        self.scheduler_db = None
        self.updates_received = []

    def _setup_scheduler_db(self, computation, num_nodes, num_workers_per_node, transfer_time_cost):
        self.scheduler_db = ReplaySchedulerDatabase(self.system_time, self.event_loop, computation, num_nodes, num_workers_per_node, transfer_time_cost)
        self.scheduler_db.get_updates(lambda update: self.updates_received.append(update))

    def _advance_check(self, delta, end_ts_expected, updates_expected):
        self.updates_received = []
        self.event_loop.run_until(delta)
        self.assertEquals(end_ts_expected, self.system_time.get_time())
        self.assertItemsEqual(updates_expected, self.updates_received)

    def _end_check(self):
        start_time = self.system_time.get_time()
        self.updates_received = []
        self.event_loop.run()
        self.assertEquals(start_time, self.system_time.get_time())
        self.assertEquals([], self.updates_received)

    def test_no_tasks(self):
        computation = ComputationDescription(root_task = None, tasks = [])
        num_nodes = 1
        num_workers_per_node = 1
        transfer_time_cost = 0
        self._setup_scheduler_db(computation, num_nodes, num_workers_per_node, transfer_time_cost)

        updates_expected = [RegisterNodeUpdate(node_id = 0, num_workers = num_workers_per_node)]
        self._advance_check(10, 10, updates_expected)

        self._end_check()

    def test_one_task(self):
        phase_0_0 = TaskPhase(phase_id = 0, depends_on = [], submits = [], duration = 1.0)
        task_0 = Task(task_id = 1, phases = [phase_0_0], results = [TaskResult(object_id = 0, size = 100)])
        computation = ComputationDescription(root_task = 1, tasks = [task_0])
        num_nodes = 1
        num_workers_per_node = 1
        transfer_time_cost = 0
        self._setup_scheduler_db(computation, num_nodes, num_workers_per_node, transfer_time_cost)

        updates_expected = [RegisterNodeUpdate(node_id = 0, num_workers = num_workers_per_node), SubmitTaskUpdate(task = task_0, submitting_node_id = 0)]
        self._advance_check(10, 10, updates_expected)
        self._end_check()

        self.scheduler_db.schedule(0, task_0.id())
        updates_expected = [FinishTaskUpdate(task_id = task_0.id())]
        self._advance_check(10, 20, updates_expected)
        self._end_check()

    def test_long_task(self):
        phase_0_0 = TaskPhase(phase_id = 0, depends_on = [], submits = [], duration = 1000.0)
        task_0 = Task(task_id = 1, phases = [phase_0_0], results = [TaskResult(object_id = 0, size = 100)])
        computation = ComputationDescription(root_task = 1, tasks = [task_0])
        num_nodes = 1
        num_workers_per_node = 1
        transfer_time_cost = 0
        self._setup_scheduler_db(computation, num_nodes, num_workers_per_node, transfer_time_cost)

        updates_expected = [RegisterNodeUpdate(node_id = 0, num_workers = num_workers_per_node), SubmitTaskUpdate(task = task_0, submitting_node_id = 0)]
        self._advance_check(100, 100, updates_expected)
        self._advance_check(100, 200, [])

        self.scheduler_db.schedule(0, task_0.id())

        for n in range(2, 11):
            self._advance_check(100, (n + 1) * 100, [])

        self.assertEquals(1100, self.system_time.get_time())
        self._advance_check(100, 1200, [FinishTaskUpdate(task_id = task_0.id())])

        self._end_check()


    def test_chained_tasks(self):
        phase_0_0 = TaskPhase(phase_id = 0, depends_on = [], submits = [TaskSubmit(task_id = 2,time_offset = 0.5)], duration = 1.0)
        task_0 = Task(task_id = 1, phases = [phase_0_0], results = [TaskResult(object_id = 234, size = 100)])

        phase_1_0 = TaskPhase(phase_id = 0, depends_on = [234], submits = [], duration = 1.0)
        task_1 = Task(task_id = 2, phases = [phase_1_0], results = [TaskResult(object_id = 2, size = 100)])

        computation = ComputationDescription(root_task = 1, tasks = [task_0, task_1])
        system_time = SystemTime()
        event_loop = EventLoop(system_time)
        num_nodes = 1
        num_workers_per_node = 1
        transfer_time_cost = 0
        self._setup_scheduler_db(computation, num_nodes, num_workers_per_node, transfer_time_cost)

        updates_expected = [RegisterNodeUpdate(node_id = 0, num_workers = num_workers_per_node), SubmitTaskUpdate(task = task_0, submitting_node_id = 0)]
        self._advance_check(100, 100, updates_expected)
        self._advance_check(100, 200, [])

        self.scheduler_db.schedule(0, task_0.id())

        updates_expected = [FinishTaskUpdate(task_id = task_0.id()), SubmitTaskUpdate(task_1, 0)]
        self._advance_check(100, 300, updates_expected)
        self._advance_check(100, 400, [])

        self.scheduler_db.schedule(0, task_1.id())

        updates_expected = [FinishTaskUpdate(task_id = task_1.id())]
        self._advance_check(100, 500, updates_expected)

        self._end_check()


if __name__ == '__main__':
    tests = unittest.TestSuite([invalid_trace_suite()] + list(map(lambda x: unittest.TestLoader().loadTestsFromTestCase(x), [TestEventLoopTimers, TestComputationObjects, TestSchedulerObjects, TestReplayState])))
    unittest.TextTestRunner(verbosity=2).run(tests)
    