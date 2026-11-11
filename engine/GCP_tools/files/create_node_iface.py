#!/usr/bin/python3

import json
import sys

net_iface = json.loads(sys.argv[1])
ens_output = str(sys.argv[2])


def create_node_ifaces(net_iface, ens_output):
    ens_output = ens_output.split('\n')
    ens_dict = {}
    for i in range(len(ens_output)-1, 0, -2):
        ens_dict[ens_output[i].split('/')[0]] = (ens_output[i-1])[:-1]

    node_ifaces = {}
    #print(json.dumps(net_iface, indent=3))
    for i in range(0, len(net_iface)):
        internal_ip = net_iface[i]['networkIP']
        node_ifaces[i] = {
            'name': ens_dict[internal_ip],
            'nic': net_iface[i]['name'],
            'internal_ip': internal_ip,
            'network': net_iface[i]['network'].split('/')[-1]
        }
    return node_ifaces


print(create_node_ifaces(net_iface, ens_output))