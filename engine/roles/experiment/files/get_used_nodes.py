#!/usr/bin/env python3
import json
import sys


def get_flow_nodes(flow_strs):
    """
    Returns set of all nodes that are part of flows in flow_strs

    Parameters:
        flow_dict (list): Has form ["subnet-1;:node-1:1.1,1.1:node-3:", ... ]

    Returns:
        node_set (set): Set of node names (str)
    """
    node_set = set([])
    for flow_str in flow_strs:
        # flow string has format subnet-1;:node-1:1.1,1.1:node-3:
        node_strs = flow_str.split(";")[1].split(",")
        for node_str in node_strs:
            node = node_str.split(":")[1]
            node_set.add(node)

    return node_set


# Load parameters
# flow_strs has form ["subnet-1;:node-1:1.1,1.1:node-3:", ... ]
flow_strs = json.loads(sys.argv[1])
# Stack node is list of nodes e.g. ["node-1", "node-3", "node-7", ...]
stack_nodes = json.loads(sys.argv[2])
# Node mapping dict
node_mapping = json.loads(sys.argv[3])
# Extract set of all nodes appearing in flows
network_nodes = get_flow_nodes(flow_strs)
# List of all used nodes (= union of set of stack nodes and network nodes)
# Node alias is mapped to actual node/container name
all_nodes = [node_mapping[node] for node in list(network_nodes.union(stack_nodes))]
# Output list of nodes (json encoded) to stdout
print(json.dumps(all_nodes))
