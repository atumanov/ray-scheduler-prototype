#!/bin/bash


sim_sweep_output_file="sim_sweep.csv"
if [ -f $sim_sweep_out_file ] ; then
  rm $sim_sweep_output_file
fi



#part 1: run real ray with sweep over number of workload type, tasks, scale (these all need to be run with 1 worker, since they are just for generating a test
#part 2: generate trace for each of the previous runs 
#part 3: sweep over simulator (sweet over different schedulers, number of nodes, number of workers per node, data_transfer_cost


#csv title
echo "scheduler,num_nodes,worker_per_node, total workers,data_transfer_cost, total job completion" | paste -sd ',' >> $sim_sweep_output_file



#external real Ray sweep
for t in `seq 1 2` #number of tasks factor (in the case of rnn this is num_steps_
do
    for s in `seq 1 2` #scale factor (object sizes)
    do
       rm -r /tmp/raylogs/*
       echo running ray_rnn with 1 workers $t steps \(tasks factor\) and scale \(object size factor\) $((s*5))
       dot="$(cd "$(dirname "$0")"; pwd)"
       python $dot/rnn/rnn_ray_loop.py -w 1 -s $s -n $t
       #generate trace
       echo generating trace of ray_rnn with 1 worker $t steps \(tasks factor\) and scale \(object size factor\) $((s*5))
       python build_trace.py /tmp/raylogs

       #internal simulator sweep
       for sched in trivial location_aware 
       do
          for n in `seq 1 5` #number of nodes
          do
             for w in `seq 1 5` #number of workers per node
             do
                for dtc_log in `seq -5 3` #data transfer cost as powers of 10: 0.00001, 0.0001, 0.001, 0.01, 0.1 etc.
                do
                   dtc=$(awk "BEGIN{print 10 ^ $dtc_log}")
                   echo running ray-scheduler-prototype with $sched scheduling policy, $n nodes, $w workers per node, and $dtc data transfer cost
                   sim_time_result=`python replaytrace.py $sched $n $w $dtc | tail -n1 | cut -d: -f1 | echo`
                   echo $sched, $n, $w, $(( $n*$w )), $dtc, $sim_time_result | paste -sd ',' >> $sim_sweep_output_file 
                done
             done
          done
       done
       suffix=$t_$s
       mv trace.json trace_rnn_t${t}_s${s}.json
    done
done


 