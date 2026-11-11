#!/usr/bin/python3

import json
import sys

network_interfaces = json.loads(sys.argv[1])
node_bridge = json.loads(sys.argv[2])
containers = json.loads(sys.argv[3])
network_bridge = json.loads(sys.argv[4])


def create_vm_container_routes(network_interfaces, node_bridge, containers, network_bridge):
    """
    Used to update IP routes for each container host

    Returns:
        host_ip_routing = {
            host-x: ip route add <IP range> via <gateway IP> && ...,
            ...
        }
    """
    ip_route_config = {node: {"gateways": [], "destinations": []} for node in containers.keys()}
    
    # add routes for incoming traffic destined for the containers
    for node, bridge in node_bridge.items():
        ip = bridge.split('/')[0]
        ip_route_config[node]['destinations'].append([bridge])
        ip_route_config[node]['gateways'].append(f"{ip.split('.')[0]}.{ip.split('.')[1]}.{ip.split('.')[2]}.{int(ip.split('.')[3]) + 1}")
        
        
    # add routes for outgoing traffic from the containers
    for node in node_bridge.keys():
        for subnetwork, values in network_interfaces.items():
            if node not in values['subnetworks'] or len(network_bridge[subnetwork]) <= 1:
                continue
            
            destination_cidrs = []
            for hostname, subnetwork_dict in values['subnetworks'].items():
                if hostname == node:
                    ip = subnetwork_dict['cidr'].split('/')[0]
                    ip_route_config[node]['gateways'].append(f"{ip.split('.')[0]}.{ip.split('.')[1]}.{ip.split('.')[2]}.{int(ip.split('.')[3]) + 1}")
                    continue
                elif hostname != node and hostname in containers.keys():
                    destination_cidrs.append(node_bridge[hostname])
                if hostname in containers.keys():                    
                    destination_cidrs.append(subnetwork_dict['cidr'])
                
            ip_route_config[node]["destinations"].append(destination_cidrs)
                
    for node in node_bridge.keys():
        command_string = []
        for i in range(0, len(ip_route_config[node]['gateways'])):
            for target in ip_route_config[node]['destinations'][i]:
                command_string.append(f"ip route add {target} via {ip_route_config[node]['gateways'][i]}")
        ip_route_config[node] = command_string
    return ip_route_config

print(create_vm_container_routes(network_interfaces, node_bridge, containers, network_bridge))