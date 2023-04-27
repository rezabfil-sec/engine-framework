#!/usr/bin/python3

import argparse
import sys

import access_variables as av

# Calculates and provides additional information for ptp configuration,
# for different modes.

def parse_cli():
    parser = argparse.ArgumentParser(prog='generate_ini', description='Generate ini file for scenario')
    parser.add_argument('scene', help='Scene directory (relative to engine/scenarios')
    parser.add_argument('-p', '--path', default='../..', help='Path to engine ansible root directory (relative or absolute)')
    parser.add_argument('-m', '--mode', choices=['mac'], required=True, help='Path to engine ansible root directory (relative or absolute)')
    return parser.parse_args()

def ptp(scene, path, m):
    av.set_path_to_engine(path)
    nodes = av.get_nodes(scene)
    node_mapping = av.get_nodes(scene)['node_mapping']
    host_vars = av.get_host_vars(nodes['nodes'])
    network = av.get_network(scene)
    return mode(m, node_mapping, network, host_vars)

def mode(mode, node_mapping, network, host_vars):
    # add if statement for calling mode specific functions:
    if mode == "mac":
        return mac_flows(node_mapping, network, host_vars)
    else:
        print("Invalid mode.")
        exit()

def map_node_to_taprio_ifaces(net, tsnconfigs):
    '''
        Maps nodes to interfaces where taprio is configured

        Maps nodes to interface numbers where taprio is configured, so that
        these can be ignored for generating the taprio hierarchy. A 0 entry is
        used to indicate that the taprio config is applied to the whole node,
        not only individual interfaces.
    '''
    node_to_taprio_ifaces_mapping = {}
    if 'tsn' in net.keys():
        for tsn_key, node_ifaces_list in net['tsn'].items():
            if len(tsnconfigs[tsn_key]['taprio'])>0:
                for node_ifaces in node_ifaces_list:
                    node, ifaces_raw = node_ifaces.split(':')
                    if node not in node_to_taprio_ifaces_mapping.keys():
                        node_to_taprio_ifaces_mapping[node] = []
                    if len(ifaces_raw) > 1:
                        ifaces = ifaces_raw.split(',')
                    elif len(ifaces_raw) == 1:
                        ifaces = [ifaces_raw]
                    else: 
                        ifaces = [0]
                    node_to_taprio_ifaces_mapping[node].extend(ifaces)
    return node_to_taprio_ifaces_mapping

def mac_flows(node_mapping, network, host_vars):
    net_ports = {}
    for net_key, net_value in network['network'].items():
        net_ports[net_key] = mac(node_mapping, net_value['flows'], map_node_to_taprio_ifaces(net_value, network['tsnconfigs']), host_vars)
    return net_ports

def mac(node_mapping, flows, node_to_taprio_ifaces_mapping, host_vars):
    """
        Generates ptp hierarchy by returning master and slave ports per node,
        based on mac addresses, using flow links only

        Chooses node with minimum mac address for interface #1 as master and
        selects connected nodes with next larger mac addresses for interface #1
        as bridge nodes, until all nodes are connected. 
        Doesn't use interfaces on which TAPRIO is configured (to be provided
        via parameter), as these would not be used on the physical testbed.
        Now the hierarchy might not be the same if the resulting topology
        (without taprio interfaces/ links) isn't connected anymore.

        Parameters
        ----------
        flow: dict
            flows for which this ptp hierarchy should be generated
        host_vars : dict
            contents of relevant host_var files;
            format: {'host_vars: {hostname: {[...]}'}

        Returns
        -------
        ports : dict
            lists master and slave ports per node, with slave port being None
            for master node;
            format:{'hostname': {'master': [[...]], slave: [...] }}
    """
    active_links = []
    active_nodes = []
    for flows_key, flows_value in flows.items():
        flow_nodes = flows_value.split(',')
        prev_node = None 
        prev_iface = None
        for flow_node in flow_nodes:
            iface_in, node, iface_out = flow_node.split(':')
            active_nodes.append((host_vars["host_vars"][node_mapping[node]]["node_ifaces"][1]["mac"], node))
            if iface_in:
                if (not (node in node_to_taprio_ifaces_mapping.keys())) or (not (iface_in in node_to_taprio_ifaces_mapping[node])):
                    if (not (prev_node in node_to_taprio_ifaces_mapping.keys())) or (not (prev_iface in node_to_taprio_ifaces_mapping[prev_node])):
                        active_links.append((prev_node, prev_iface, iface_in, node))
            if iface_out:
                prev_node = node
                prev_iface = iface_out
    active_nodes = list(set(active_nodes))

    ports = {}
    for _, node in active_nodes:
        ports[node] = {}
        ports[node]["master"] = []
        ports[node]["slave"] = None

    min_n = min(active_nodes)
    ports[min_n[1]]["slave"] = -1

    work_list = [min_n]
    while work_list:
        _, min_node = work_list.pop(0)
        for start, start_iface, end_iface, end in active_links:
            if min_node == start and ports[end]["slave"] is None:
                ports[start]["master"].append(start_iface)
                ports[end]["slave"] = end_iface
                work_list.append((host_vars["host_vars"][node_mapping[end]]["node_ifaces"][1]["mac"],end))
            if min_node == end and ports[start]["slave"] is None:
                ports[end]["master"].append(end_iface)
                ports[start]["slave"] = start_iface
                work_list.append((host_vars["host_vars"][node_mapping[start]]["node_ifaces"][1]["mac"],start))
        work_list.sort()
    ports[min_n[1]]["slave"] = None
    return ports

def mac_all(topo, nodes, host_vars):
    """
        Generates ptp hierarchy by returning master and slave ports per node,
        based on mac addresses, using all links

        Chooses node with minimum mac address for interface #1 as master and
        selects connected nodes with next larger mac addresses for interface #1
        as bridge nodes, until all nodes are connected

        Parameters
        ----------
        topo : dict
            topology files that provides basic flows for the scene's nodes
        nodes : dict
            node list and node_mapping
        host_vars : dict
            contents of relevant host_var files;
            format: {'host_vars: {hostname: {[...]}'}

        Returns
        -------
        ports : dict
            lists master and slave ports per node, with slave port being None
            for master node;
            format:{'hostname': {'master': [[...]], slave: [...] }}
    """
    # select and process relevant flows
    flows = []
    for flow in topo["basic_flows"].values():
        flow_nodes = flow.split(',')
        _, start_node, start_iface = flow_nodes[0].split(':')
        end_iface, end_node, _ = flow_nodes[-1].split(':')
        if topo['node_mapping'][start_node] in nodes['nodes'] and topo['node_mapping'][end_node] in nodes['nodes']:
            flows.append((topo['node_mapping'][start_node], start_iface, end_iface, topo['node_mapping'][end_node]))

    # initialize result dict, and find node with minimum clock id
    ports = {}
    node_list = []
    for node in nodes['nodes']:
        ports[node] = {}
        ports[node]["master"] = []
        ports[node]["slave"] = None
        node_list.append((host_vars["host_vars"][node]["node_ifaces"][1]["mac"],node))
    min_n = min(node_list)
    ports[min_n[1]]["slave"] = -1

    # find relevant ports and roles
    connected = [min_n]
    while connected:
        _, min_node = connected.pop(0)
        for start, start_iface, end_iface, end in flows:
            if min_node == start and ports[end]["slave"] is None:
                ports[start]["master"].append(start_iface)
                ports[end]["slave"] = end_iface
                connected.append((host_vars["host_vars"][end]["node_ifaces"][1]["mac"],end))
            if min_node == end and ports[start]["slave"] is None:
                ports[end]["master"].append(end_iface)
                ports[start]["slave"] = start_iface
                connected.append((host_vars["host_vars"][start]["node_ifaces"][1]["mac"],start))
        connected.sort()
    ports[min_n[1]]["slave"] = None
    return ports

def main():
    parser_args = parse_cli()
    scene = parser_args.scene
    path = parser_args.path
    mode = parser_args.mode
    print(ptp(scene, path, mode))

if __name__ == "__main__":
    main()
