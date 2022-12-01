#!/bin/bash
# Clean all tc config on the PTP port                                                                                   # PTP port 
PORT=$1
#PORTS=(enp8s0 enp9s0 enp10s0 enp11s0 eno1 eno4 eno5 eno6)
IFS=',' read -ra PORTS <<< $2
PTP=$3
# make sure ptp4l and other are off

pkill ptp4l
pkill phc2sys

# make sure port runs

ip link set $PORT up
# make sure not TC config on the port
# If no config, proceeds
tc qdisc del dev $PORT root
# start PTP daemon on the port

echo 'Starting PTP4L daemon'
ptp4l -i $PORT -f $PTP/configs/gPTP.cfg --step_threshold=1 &

sleep 5

echo 'Set TAI-UTC diff'

pmc -u -b 0 -t 1 -i $PORT "SET GRANDMASTER_SETTINGS_NP clockClass 248 clockAccuracy 0xfe offsetScaledLogVariance 0xffff currentUtcOffset 37 leap61 0 leap59 0 currentUtcOffsetValid 1 ptpTimescale 1 timeTraceable 1 frequencyTraceable 0 timeSource 0xa0"

sleep 5

echo 'Sync system clock - phc2sys'
phc2sys -s $PORT -c CLOCK_REALTIME --step_threshold=1 --transportSpecific=1 -w -x -E pi &


for port in ${PORTS[@]}
do
    echo "Starting $port: sync"
    phc2sys -s $PORT -c $port --step_threshold=1 --transportSpecific=1 -w -x -E pi &
    sleep 2	
done
