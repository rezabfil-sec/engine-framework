#!/bin/bash

# Experiment run control
#  Running this script will mark the point where the experiment environment is
# ready (network, stack) and mark the logical start of the experiment by taking
# a timestamp which is a point of reference for later evaluation and
# post-processing. The end of the experiment can be triggered by two
# conditions, which are the two modes of this script:
# 1. Time: Run the experiment for a certain number of seconds.
#   While the timer is running occurring error states trigger an immediate interruption
# 2. Signal: Wait until certain applications are finished, e.g. after sending a
#   fixed amount of data. In this mode applications/services can register that
#   they will send a signal when they are finished. This script is querying a
#   central signal file, if all registered signals were received the experiment
#   is done. After receiving a failure signal the experiment is immediately
#   interrupted.

# ./run_experiment t <seconds>                          : run the experiment in time mode
# ./run_experiment s <num_registered_signals> <timeout> : run the experiment in signal mode

set -x

# Immediately exit the script on error
#set -e

SIGNAL_PATH="{{ file_paths.path_service_signal }}"
LOG_FILE="{{ file_paths.path_log_file }}"
EXPERIMENT_SIGNAL="{{ file_paths.path_experiment_signal }}"

TIMER_INTERVAL=1


# log function
log()
{
    get_time
    echo "[$TNOW] Experiment: $@" >> $LOG_FILE
}

get_time()
{
  TNOW=`date +%s.%N`
}

# Start of the experiment
log "start experiment"
START=$TNOW
echo "s:start t:$START" >> $EXPERIMENT_SIGNAL

# Start experiment actions
# -> Reference point for actions is START
# TODO Implement actions

# TIME mode
if [ "$1" == "t"  ]; then
    RUN_TIME=$2
    while true;
    do
        # sleep for timer interval
        sleep $TIMER_INTERVAL

        get_time
        TDIFF=$(bc -l <<< "$TNOW-$START")
        
        # check error condition
        if egrep -q "rc:1" $SIGNAL_PATH ; then
            ERR=`egrep "rc:1" $SIGNAL_PATH`
            log "experiment failed [$TDIFF] - $ERR"
            echo "s:stop t:$TNOW rc:1" >> $EXPERIMENT_SIGNAL
            exit 1
        fi
        
        # check timer condition
        if (( $(bc -l <<< "$TDIFF > $RUN_TIME") )); then
            log "experiment success [$TDIFF] - time $RUN_TIME"
            echo "s:stop t:$TNOW rc:0" >> $EXPERIMENT_SIGNAL
            exit 0
        fi

        log "experiment running [$TDIFF]"
    done
fi

# SIGNAL mode
if [ "$1" == "s" ]; then
    SIGNAL_COUNT=$2
    TIMEOUT=$3
    while true;
    do
        # sleep for timer interval
        sleep $TIMER_INTERVAL

        # check timeout error condition
        get_time
        TDIFF=$(bc -l <<< "$TNOW-$START")

        if (( $(bc -l <<< "$TDIFF > $TIMEOUT") )); then
            log "experiment failed [$TDIFF] - timeout $TIMEOUT"
            echo "s:stop t:$TNOW rc:1" >> $EXPERIMENT_SIGNAL
            exit 1
        fi
        
        # check service error condition
        if egrep -q "rc:1" $SIGNAL_PATH ; then
            ERR=`egrep "rc:1" $SIGNAL_PATH`
            log "experiment failed [$TDIFF] - error $ERR"
            echo "s:stop t:$TNOW rc:1" >> $EXPERIMENT_SIGNAL
            exit 1
        fi
        
        # check signal condition
        NUM_SIGNALS=$(egrep "s:1" $SIGNAL_PATH | wc -l)
        if (( $(bc -l <<< "$NUM_SIGNALS >= $SIGNAL_COUNT") )); then
            log "experiment success [$TDIFF] - signals $NUM_SIGNALS/$SIGNAL_COUNT"
            echo "s:stop t:$TNOW rc:0" >> $EXPERIMENT_SIGNAL
            exit 0
        fi
        
        log "experiment running [$TDIFF]"
    done
fi
