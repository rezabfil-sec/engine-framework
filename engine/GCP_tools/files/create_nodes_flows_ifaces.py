#!/usr/bin/python3

import json
import sys

nodes_ifaces = json.loads(sys.argv[1])
node_mapping = json.loads(sys.argv[2])
containers = json.loads(sys.argv[3])
flows = json.loads(sys.argv[4])


# create association between nodes and the interfaces for each network they are connected to
def create_nodes_net_ifaces(nodes_ifaces):
    nodes_net_ifaces = {
        node: {
            v['network']: k for k, v in ifaces.items()
        } for node, ifaces in nodes_ifaces.items()
    }
    return nodes_net_ifaces


def create_nodes_flows_ifaces(nodes_net_ifaces, flows, node_mapping, containers, node_ifaces):
    nodes_net_ifaces_keys = set(nodes_net_ifaces.keys())
    container_to_host = {c['name']: host for host, container in containers.items() for c in container}
    nodes = list(node_mapping.values())
    nodes_flows_ifaces = {node: [] for node in nodes}

    for k, v in flows.items():
        network, flow = v.split(';')
        flow = flow[1:-1]
        src, dst = flow.split(',')
        src_node, src_iface = src.split(':')
        dst_iface, dst_node = dst.split(':')

        src_node = node_mapping[src_node]
        dst_node = node_mapping[dst_node]

        original_src_node = src_node
        original_dst_node = dst_node
        # Use pre-calculated keys and mapping
        if containers and (src_node not in nodes_net_ifaces_keys or dst_node not in nodes_net_ifaces_keys):
            src_node = container_to_host.get(src_node, src_node)
            dst_node = container_to_host.get(dst_node, dst_node)

        src_iface = nodes_net_ifaces[src_node][network]
        dst_iface = nodes_net_ifaces[dst_node][network]

        src_container = True if src_node in containers.keys() else False
        dst_container = True if dst_node in containers.keys() else False

        nodes_flows_ifaces[original_src_node].append(
            {
                'flow': k,
                'hw': src_iface,
                'ip_dst': node_ifaces[dst_node][dst_iface]['internal_ip'] if not dst_container else original_dst_node,
                'ip_src': node_ifaces[src_node][src_iface]['internal_ip'] if not src_container else original_src_node,
                'name': 'flow' + str(k),
                'role': 'source',
                'container': src_container
            }
        )
        nodes_flows_ifaces[original_dst_node].append(
            {
                'flow': k,
                'hw': dst_iface,
                'ip_dst': node_ifaces[src_node][src_iface]['internal_ip'] if not src_container else original_src_node,
                'ip_src': node_ifaces[dst_node][dst_iface]['internal_ip'] if not dst_container else original_dst_node,
                'name': 'flow' + str(k),
                'role': 'sink',
                'container': dst_container
            }
        )

    return nodes_flows_ifaces

print(create_nodes_flows_ifaces(create_nodes_net_ifaces(nodes_ifaces), flows, node_mapping, containers, nodes_ifaces))
