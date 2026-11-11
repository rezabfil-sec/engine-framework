#!/usr/bin/python3

import json
import sys

network_interfaces = json.loads(sys.argv[1])
nodes_all = json.loads(sys.argv[2])

def generate_ip_route_config(network_interfaces, nodes_all):
    """
    Generates the IP route configuration for each node in the network.
    Loops through each node and checks which subnets the node is in and adds the IP route command for each subnet.

    Args:
        network_interfaces (dict): A dictionary containing the VPC networks and the VMs in each of those networks.
        e.g 
        network_interfaces = {
            VPC_x : {
                network: <VPC_x selflink>,
                subnetworks: { #associate each node in VPC_x with its repsective subnets within VPC_x
                    node_x_y: {
                        cidr: <CIDR of subnet_x_y>
                        self_link: <subnet_x_y selflink>
                    }, 
                    ...
                },
            },
            ...
        }

        nodes_all (list): A list of all nodes in the network.

    Returns:
        dict: A dictionary containing the IP route configuration for each node in the network.
        e.g ip_route_config = {
            node-x: ip route add <IP range> via <gateway IP> && ...,
            ...
        }
    """
    ip_route_config = {node: {"gateways": [], "destinations": []} for node in nodes_all}

    for node in nodes_all:
        for subnet, values in network_interfaces.items():
            if node not in values['subnetworks']:
                continue

            destination_cidrs = []
            for hostname, subnetwork_dict in values['subnetworks'].items():
                # Get the gateway address of the current node in this VPC network
                if node == hostname:
                    gateway_address = subnetwork_dict['cidr'].split('/')[0]
                    gateway_address = ".".join(gateway_address.split('.')[0:3]) + '.' + str(int(gateway_address.split('.')[3]) + 1)
                    ip_route_config[node]["gateways"].append(gateway_address)
                # Get the destination VM's CIDR 
                else:
                    destination_cidrs.append(subnetwork_dict['cidr'])

            ip_route_config[node]["destinations"].append(destination_cidrs)
    
    # formulate the IP route command for each node
    for node in nodes_all:
        command_string = []
        for i in range(0, len(ip_route_config[node]['gateways'])):
            for target in ip_route_config[node]['destinations'][i]:
                command_string.append(f"ip route add {target} via {ip_route_config[node]['gateways'][i]}")
        ip_route_config[node] = " && ".join(command_string)
    return ip_route_config

print(generate_ip_route_config(network_interfaces, nodes_all))