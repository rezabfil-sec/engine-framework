#!/bin/bash

# Service / command wrapper
# Start a command with this script, the return code and additional metadata
# is stored in a central file which is accessed by other services. This is
# intended to give insights into the outcome of a service / command.
# The first parameter specifies if the command signal was registered.
# The second parameter specifies how long to wait before executing the command
# The third parameter specifies whether to sync the service start with the start of the experiment (1/0)
# The fourth parameter specifies after how many seconds to wait before stopping the service
# The fifth parameter specifies whether to sync the service stop with the experiment end (1/0)
# FOURTH AND FIFTH PARAMETERS ARE MUTUALLY EXCLUSIVE! If fifth parameter set to 1, then fourth one will be ignored
# The service will first wait for wait-sec and then start checking if the experiment started if sync-start set to true.
#
# ./run_service_action.sh <1/0> <start-after-sec> <sync-start> <stop-after-sec> <sync-stop> <cmd>

set -x

# Immediately exit the script on error
#set -e

TIMER_INTERVAL=0.05

RC=1
PID=0

SIGNAL_PATH="{{ file_paths.path_service_signal }}"
LOG_FILE="{{ file_paths.path_log_file }}"
EXPERIMENT_SIGNAL="{{ file_paths.path_experiment_signal }}"

# log function
log()
{
    get_time
    echo "[$TNOW] Service: $@" >> $LOG_FILE
}

get_time()
{
  TNOW=`date +%s.%N`
}

start_func()
{
    log "Start service -> s:$1 d:$3 ds:$2 e:$5 es:$4 cmd:${@:6}"
    # Omit the first five script parameters, execute the rest as a command
    ${@:6} &
    PID=$!
    
    log "Service started with PID $PID -> s:$1 d:$3 ds:$2 e:$5 es:$4 cmd:${@:6}"
    
    stop_func $1 $2 $3 $4 $5 ${@:6} &
    STOP_PID=$! 
   
    wait $PID
    RC=$?
    
    wait $STOP_PID
    RC_STOP=$?

    if [[ $RC -gt 0 ]]; then
        if [[ $RC_STOP -eq 0 ]]; then
            RC=$RC_STOP
        fi
    fi

    # write return code and executed cmd into a central file
    echo "s:$1 d:$3 ds:$2 e:$5 es:$4 rc:$RC cmd:${@:6}" >> $SIGNAL_PATH

    log "Service finished -> s:$1 d:$3 ds:$2 e:$5 es:$4 rc:$RC cmd:${@:6}"
}

stop_func()
{
    log "|NOTE; EXPERIMENTAL| Service stop func -> s:$1 d:$3 ds:$2 e:$5 es:$4 cmd:${@:6}"
    # Check if stop-sync enabled
    if [[ $5 -eq 1 ]]; then
        log "|NOTE; EXPERIMENTAL| Service will end with experiment end -> s:$1 d:$3 ds:$2 e:$5 es:$4 cmd:${@:6}"
        while true;
        do
            if egrep -q "s:stop" $EXPERIMENT_SIGNAL ; then
                break
            fi
            sleep $TIMER_INTERVAL
        done
        log "|NOTE; EXPERIMENTAL| Service with PID $PID will be killed now -> s:$1 d:$3 ds:$2 e:$5 es:$4 cmd:${@:6}"
        kill $PID
        return $?
    elif [[ $4 -gt 0 ]]; then
        log "|NOTE; EXPERIMENTAL| Service will end after $4 seconds -> s:$1 d:$3 ds:$2 e:$5 es:$4 cmd:${@:6}"
        sleep $4
        log "|NOTE; EXPERIMENTAL| Service will be killed now -> s:$1 d:$3 ds:$2 e:$5 es:$4 cmd:${@:6}"
        kill $PID
        return $?
    fi   
    return 2
}

# Check if start-sync enabled
if [[ $3 -eq 1 ]]; then
    log "|NOTE| Service start with experiment start -> s:$1 d:$3 ds:$2 e:$5 es:$4 cmd:${@:6}"
    while true;
    do
        if egrep -q "s:start" $EXPERIMENT_SIGNAL ; then
            break
        fi
        sleep $TIMER_INTERVAL
    done
fi

# wait before execution - delayed start (could be used for actions)
sleep $2

start_func $1 $2 $3 $4 $5 ${@:6}

# # store return code in a variable
# RC=$?

# # write return code and executed cmd into a central file
# echo "s:$1 d:$3 ds:$2 e:$5 es:$4 rc:$RC cmd:${@:6}" >> $SIGNAL_PATH

log "Script finishing -> s:$1 d:$3 ds:$2 e:$5 es:$4 rc:$RC cmd:${@:6}"

# exit this script with the same return code as the command
exit $RC
