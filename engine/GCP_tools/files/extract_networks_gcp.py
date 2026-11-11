#!/usr/bin/python3

import json
import sys

# flows
flows = json.loads(sys.argv[1])
# mapping
mapping = json.loads(sys.argv[2])
# nodes_all
nodes_all = json.loads(sys.argv[3])
# containers
containers = json.loads(sys.argv[4])

def generate_networks_config(flows, mapping, nodes_all, containers):
    """
    Generates the network configuration, specifiying which nodes are in which network. 
    Also creates a network for ungrouped nodes as well as correlate containers to their respective networks.
    
    
    Args:
        flows (dict): A dictionary containing the flows and the nodes in each of those flows.
        mapping (dict): A dictionary containing the mapping of the nodes to their respective hostnames.
        nodes_all (list): A list of all nodes in the network.
        containers (dict): A dictionary containing the containers and the nodes in each of those containers.
    
    Returns:
        dict: A dictionary containing the network configuration for each node in the network.
        e.g
            subnet_node_dict:
                [VPC_x : [
                    hostname(node-x) for node-x in flows in VPC_x
                    ]
                ]
    """

    used_nodes = set()
    # extract {<network_name> : [mapping[<node_x>], ...], ...} from flows
    subnet_node_dict = {}
    for values in flows.values():
        subnet_name, nodes = values.split(';')
        nodes = {mapping[node.split(':')[1]] for node in nodes.split(',')}
        subnet_node_dict.setdefault(subnet_name, set()).update(nodes)
        used_nodes.update(nodes)

    subnet_container_hosts_dict = {}
    if containers:
        # extract container_dict = {<container_name> : <host_node>, ...} from containers
        container_dict = {}
        for k, v in containers.items():
            for container in v:
                container_dict[container['name']] = k

        # extract subnet_container_hosts_dict = {<network_name> : [<host_node>, ...], ...} from subnet_node_dict
        subnet_container_hosts_dict = {}
        for k, v in subnet_node_dict.items():
            for node in v:
                if node in container_dict.keys():
                    subnet_container_hosts_dict.setdefault(k, set()).add(container_dict[node])
                    used_nodes.add(container_dict[node])
                else:
                    subnet_container_hosts_dict.setdefault(k, set()).add(node)

        # remove container names from subnet_node_dict
        for k, v in subnet_node_dict.items():
            subnet_node_dict[k] = [node for node in v if node not in container_dict.keys()]

        # remove subnets that contain containers all on the same host
        subnet_container_hosts_dict = {k: v for k, v in subnet_container_hosts_dict.items() if len(v) > 1}

    # get nodes that have no flows
    ungrouped_nodes = set(nodes_all) - used_nodes

    # remove <network_name> : [] from subnet_node_dict
    subnet_node_dict = {k: v for k, v in subnet_node_dict.items() if v}

    # Use enumerate for automatic index handling
    for index, node in enumerate(ungrouped_nodes, start=1):
        subnet_node_dict[f"ungrouped-{index}"] = [node]

    # merge subnet_node_dict and subnet_container_hosts_dict
    subnet_node_dict.update(subnet_container_hosts_dict)

    # convert sets to lists
    subnet_node_dict = {k: list(v) for k, v in subnet_node_dict.items()}
    
    return subnet_node_dict

print(generate_networks_config(flows, mapping, nodes_all, containers))