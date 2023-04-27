#!/bin/bash

# Service / command wrapper
# Start a command with this script, the return code and additional metadata
# is stored in a central file which is accessed by other services. This is
# intended to give insights into the outcome of a service / command.
# The first parameter specifies if the command signal was registered.
# The second parameter specifies how long to wait before executing the command
# The third parameter specifies whether to sync the service start with the start of the experiment (1/0)
# The service will first wait for wait-sec and then start checking if the experiment started if sync-start set to true.
#
# ./run_service.sh <1/0> <wait-sec> <sync-start> <cmd>

set -x

# Immediately exit the script on error
#set -e

TIMER_INTERVAL=0.05

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

# wait before execution
sleep $2

# Check if start-sync enabled
if [[ $3 -eq 1 ]]; then
    log "|NOTE| Service start with experiment start -> s:$1 d:$3 cmd:${@:4}"
    while true;
    do
        if egrep -q "s:start" $EXPERIMENT_SIGNAL ; then
            break
        fi
        sleep $TIMER_INTERVAL
    done
fi

log "Start service -> s:$1 d:$3 cmd:${@:4}"

# Omit the first script parameter, execute the rest as a command
${@:4}

# store return code in a variable
RC=$?

# write return code and executed cmd into a central file
echo "s:$1 d:$3 rc:$RC cmd:${@:4}" >> $SIGNAL_PATH

log "Service finished -> s:$1 d:$3 rc:$RC cmd:${@:4}"

# exit this script with the same return code as the command
exit $RC
