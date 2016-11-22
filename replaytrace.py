import replaystate
from trivialscheduler import *
import json

import sys
import logging

schedulers = {
    'trivial' : TrivialScheduler,
    'location_aware' : LocationAwareScheduler,
    'trivial_local' : TrivialLocalScheduler,
    'delay' : DelayScheduler,
    'transfer_aware' : TransferCostAwareScheduler,
    'basic_threshold' : TrivialThresholdLocalScheduler,
    'transfer_aware_local' : TransferCostAwareLocalScheduler
}

def usage():
    print 'Usage: test_scheduler num_nodes num_workers_per_node object_transfer_time_cost db_message_delay scheduler input.json'
    print 'Available schedulers: '; print schedulers.keys()


def simulate(computation, scheduler_type, system_time, logger, num_nodes, num_workers_per_node, object_transfer_time_cost, db_message_delay):
    object_store = replaystate.ObjectStoreRuntime(system_time, object_transfer_time_cost)
    scheduler_db = replaystate.ReplaySchedulerDatabase(system_time, logger, computation, num_nodes, num_workers_per_node, object_transfer_time_cost, db_message_delay)
    schedulers = scheduler_type(system_time, scheduler_db)
    global_scheduler = schedulers.get_global_scheduler(replaystate.EventLoop(system_time))
    local_runtimes = {}
    local_schedulers = {}
    for node_id in range(0, num_nodes):
        local_runtime = replaystate.NodeRuntime(system_time, object_store, logger, computation, node_id, num_workers_per_node)
        local_runtimes[node_id] = local_runtime
        local_event_loop = replaystate.EventLoop(system_time)
        local_schedulers[node_id] = schedulers.get_local_scheduler(local_runtime, local_event_loop)
    scheduler_db.schedule_root(0)
    system_time.advance_fully()
    num_workers_executing = 0
    for node_id, local_runtime in local_runtimes.items():
        num_workers_executing += local_runtime.num_workers_executing
    if num_workers_executing > 0:
        pylogger = logging.getLogger(__name__+'.simulate')
        pylogger.debug("failed to execute fully".format(
            num_workers_executing),
            extra={'timestamp':system_time.get_time()})
        print "{:.6f}: Simulation Error. Total Number of Tasks: {}, DAG Normalized Critical Path: {}, Total Tasks Durations: {}".format(system_time.get_time(), computation.total_num_tasks, computation.normalized_critical_path, computation.total_tasks_durations)
        print "-1: {} : {} : {} : {} : {}".format(system_time.get_time(), computation.total_num_tasks, computation.total_tasks_durations, computation.total_num_objects, computation.total_objects_size, computation.normalized_critical_path)
        return False
    else:
        print "{:.6f}: Simulation finished successfully. Total Number of Tasks: {}, DAG Normalized Critical Path: {}, Total Tasks Durations: {}".format(system_time.get_time(), computation.total_num_tasks, computation.normalized_critical_path, computation.total_tasks_durations)
        print "{:.6f}: {} : {} : {} : {} : {}".format(system_time.get_time(), computation.total_num_tasks, computation.total_tasks_durations, computation.total_num_objects, computation.total_objects_size, computation.normalized_critical_path)
        return True

def setup_logging():
    logging_format = '%(timestamp).6f %(name)s %(message)s'
    logging.basicConfig(format=logging_format)
    logging.getLogger().setLevel(logging.DEBUG)

def run_replay(args):
    setup_logging()

    if len(args) != 7:
        usage()
        sys.exit(1)

    num_nodes = int(args[1])
    num_workers_per_node = int(args[2])
    object_transfer_time_cost = float(args[3])
    db_message_delay = float(args[4])
    scheduler_str = args[5]
    if scheduler_str not in schedulers.keys():
        usage()
        print 'Error - unrecognized scheduler'
        sys.exit(1)
    input_fn = args[6]
    print input_fn
    f = open(input_fn, 'r')
    computation = json.load(f, object_hook=replaystate.computation_decoder)
    f.close()

    system_time = replaystate.SystemTime()
    logger = replaystate.PrintingLogger(system_time)
    simulate(computation, schedulers[scheduler_str], system_time, logger, num_nodes, num_workers_per_node, object_transfer_time_cost, db_message_delay)


if __name__ == '__main__':
    run_replay(sys.argv)
