#!/usr/bin/python3

# Reusably processes variables by calculating additional parameters based on
# existing parameters from scenario variable files.

def map_node_to_flow_to_interfaces(flows):
    node_to_flow_to_interface_mapping = {}
    for flows_key, flows_value in flows.items():
        flow_nodes = flows_value.split(',')
        for flow_node in flow_nodes:
            iface_in, node_name, iface_out = flow_node.split(':')
            if not node_name in node_to_flow_to_interface_mapping.keys():
                node_to_flow_to_interface_mapping[node_name] = {}
            node_to_flow_to_interface_mapping[node_name][flows_key] = []
            if iface_in:
                node_to_flow_to_interface_mapping[node_name][flows_key].append(iface_in)
            if iface_out:
                node_to_flow_to_interface_mapping[node_name][flows_key].append(iface_out) 
    return node_to_flow_to_interface_mapping

def map_node_to_interface_to_tsn(tsn):
    node_to_interface_to_tsn_mapping = {}
    for tsn_key, tsn_value in tsn.items():
        for node_interfaces_string in tsn_value:
            if ':' in node_interfaces_string:
                node, interfaces_string = node_interfaces_string.split(':')
                if not node in node_to_interface_to_tsn_mapping.keys():
                    node_to_interface_to_tsn_mapping[node] = {}
                interfaces = interfaces_string.split(',')
                for interface in interfaces:
                    node_to_interface_to_tsn_mapping[node][interface] = tsn_key
            else:
                node = node_interfaces_string
                if not node in node_to_interface_to_tsn_mapping.keys():
                    node_to_interface_to_tsn_mapping[node] = {}
                node_to_interface_to_tsn_mapping[node][0] = tsn_key
    return node_to_interface_to_tsn_mapping
