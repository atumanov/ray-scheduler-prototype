import sys

from schedulerbase import *
from itertools import ifilter

class BaseScheduler():

    def __init__(self, time_source, scheduler_db):
        self._ts = time_source
        self._db = scheduler_db

        self._nodes = {}

        self._pending_tasks = []
        self._runnable_tasks = []
        self._executing_tasks = {}
        self._finished_objects = {}
        
        self._pending_needs = {}
        self._awaiting_completion = {}

        self._tasks = {}

    class _NodeStatus:
        def __init__(self, node_id, num_workers):
            self.node_id = node_id
            self.num_workers = num_workers
            self.num_workers_executing = 0

        def inc_executing(self):
            self.num_workers_executing += 1

        def dec_executing(self):
            self.num_workers_executing -= 1

        def __str__(self):
            return 'NodeStatus({},{},{})'.format(self.node_id, self.num_workers, self.num_workers_executing)

    def _register_node(self, node_id, num_workers):
        if node_id in self._nodes.keys():
            print 'already registered node {}'.format(node_id)
            sys.exit(1)
        self._nodes[node_id] = self._NodeStatus(node_id, num_workers)

    def _schedule_locally(self, task, submitting_node_id):
        return False

    def _add_task(self, task, submitting_node_id):
        task_id = task.id()
        self._tasks[task_id] = task
        if self._schedule_locally(task, submitting_node_id):
            return
        pending_needs = []
        for d_object_id in task.get_depends_on():
            if d_object_id not in self._finished_objects.keys():
                pending_needs.append(d_object_id)
                if d_object_id in self._awaiting_completion.keys():
                    self._awaiting_completion[d_object_id].append(task_id)
                else:
                    self._awaiting_completion[d_object_id] = [task_id]
        if len(pending_needs) > 0:
            self._pending_needs[task_id] = pending_needs
            self._pending_tasks.append(task_id)
        else:
            self._runnable_tasks.append(task_id)

    def _finish_task(self, task_id):
        node_id = self._executing_tasks[task_id]
        self._nodes[node_id].dec_executing()
        del self._executing_tasks[task_id]
        for result in self._tasks[task_id].get_results():
            object_id = result.object_id
            # TODO - should be appending to list of object locations
            self._finished_objects[object_id] = node_id
            if object_id in self._awaiting_completion.keys():
                pending_task_ids = self._awaiting_completion[object_id]
                del self._awaiting_completion[object_id]
                for pending_task_id in pending_task_ids:
                    needs = self._pending_needs[pending_task_id]
                    needs.remove(object_id)
                    if not needs:
                        del self._pending_needs[pending_task_id]
                        self._pending_tasks.remove(pending_task_id)
                        self._runnable_tasks.append(pending_task_id)

    def _execute_task(self, node_id, task_id):
        node_status = self._nodes[node_id]
        node_status.inc_executing()
        self._executing_tasks[task_id] = node_id
        self._db.schedule(node_id, task_id)

    def _process_tasks(self):
        for task_id in list(self._runnable_tasks):
            node_id = self._select_node(task_id)
            print "process tasks got node id {} for task id {}".format(node_id, task_id)

            if node_id is not None:
                self._runnable_tasks.remove(task_id)
                self._execute_task(node_id, task_id)
            else:
                # Not able to schedule so return
                print 'unable to schedule'
                return

    def _select_node(self, task_id):
        raise NotImplementedError()

    def run(self):
        is_shutdown = False
        while not is_shutdown:
            for update in self._db.get_updates(10):
                #print 'scheduler update ' + str(update)
                if isinstance(update, SubmitTaskUpdate):
                    print '{} task {} submitted'.format(self._ts.get_time(), update.get_task_id())
                    self._add_task(update.get_task(), update.get_submitting_node_id())
                elif isinstance(update, FinishTaskUpdate):
                    self._finish_task(update.get_task_id())
                elif isinstance(update, RegisterNodeUpdate):
                    self._register_node(update.node_id, update.num_workers)
                elif isinstance(update, ShutdownUpdate):
                    # TODO - not sure whether extra logic in shutdown
                    #        is generally needed, but useful in debugging
                    #        nonetheless.
                    if not self._runnable_tasks and not self._pending_tasks and not self._executing_tasks:
                        is_shutdown = True
                    else:
                        print 'pending: {}'.format(str(self._pending_tasks))
                        print 'runnable: {}'.format(str(self._runnable_tasks))
                        print 'executing: {}'.format(str(self._executing_tasks))
                        print 'nodes: {}'.format(','.join(map(lambda x: str(x), self._nodes.values())))
                else:
                    print 'Unknown update ' + update.__class__.__name__
                    sys.exit(1)
                self._process_tasks()

class TrivialScheduler(BaseScheduler):

    def __init__(self, time_source, scheduler_db):
        BaseScheduler.__init__(self, time_source, scheduler_db)
        #super(TrivialScheduler).__init__(time_source, scheduler_db)

    def _select_node(self, task_id):
        (best_node_id, _) = next(ifilter(lambda (node_id,node_status): node_status.num_workers_executing < node_status.num_workers, self._nodes.items()), None)
        return best_node_id

class LocationAwareScheduler(BaseScheduler):

    def __init__(self, time_source, scheduler_db):
        BaseScheduler.__init__(self, time_source, scheduler_db)

    def _select_node(self, task_id):
        task_deps = self._tasks[task_id].get_depends_on()
        best_node_id = None
        best_cost = sys.maxint
        # TODO short-circuit cost computation if there are no dependencies.
        #      also may optimize lookup strategy for one or two dependencies.
        for (node_id, node_status) in self._nodes.items():
            if node_status.num_workers_executing < node_status.num_workers:
                cost = 0
                for depends_on in task_deps:
                    if self._finished_objects[depends_on] != node_id:
                        cost += 1
                if cost < best_cost:
                    best_cost = cost
                    best_node_id = node_id
        return best_node_id

class TrivialLocalScheduler(TrivialScheduler):

    def __init__(self, time_source, scheduler_db):
        TrivialScheduler.__init__(self, time_source, scheduler_db)

    def _schedule_locally(self, task, submitting_node_id):
        for d_object_id in task.get_depends_on():
            if d_object_id not in self._finished_objects.keys() or self._finished_objects[d_object_id] != submitting_node_id:
                return False
        node_status = self._nodes[submitting_node_id]
        if node_status.num_workers_executing >= node_status.num_workers:
            return False
        self._execute_task(submitting_node_id, task.id())
        return True
