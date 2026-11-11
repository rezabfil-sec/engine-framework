#!/usr/bin/python3

import json
import sys

flow_ifaces = json.loads(sys.argv[1])
container_ip = json.loads(sys.argv[2])

def adjust_flow_ifaces_containers(flow_ifaces, container_ip):
    for flow in flow_ifaces:
        if flow['container']:
            flow['ip_dst'] = container_ip[flow['ip_dst']]
            flow['ip_src'] = container_ip[flow['ip_src']]
    return flow_ifaces

print(adjust_flow_ifaces_containers(flow_ifaces, container_ip))