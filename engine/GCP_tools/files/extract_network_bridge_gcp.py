#!/usr/bin/python3

import json
import sys

subnetwork_nodes = json.loads(sys.argv[1])
node_bridge = json.loads(sys.argv[2])
instance_selflink = json.loads(sys.argv[3])
network_interfaces = json.loads(sys.argv[4])

def create_network_bridge(subnetwork_nodes, node_bridge, instance_selflink, network_interfaces):
    """
    Creates a dictionary containing all the necessary information to configure the VPC network routes for container networking

    Returns:
        network_bridge = {
            VPC_x: [
                bridge: <bridge subnet>,
                network_selflink: <VPC_x selflink>,
                vm_selflink: <node_x_y selflink>,
                vm_name: <node_x_y name>
            ]
        }
    """
    network_bridge = {}
    for subnetwork, nodes in subnetwork_nodes.items():
        network_bridge[subnetwork] = []
        for node in nodes:
            if node in node_bridge.keys():
                network_bridge[subnetwork].append({'bridge': node_bridge[node], 
                                                   'network_selflink': network_interfaces[subnetwork]['network'],
                                                   'vm_selflink': instance_selflink[node],
                                                   'vm_name': node})
    return network_bridge

print(create_network_bridge(subnetwork_nodes, node_bridge, instance_selflink, network_interfaces))