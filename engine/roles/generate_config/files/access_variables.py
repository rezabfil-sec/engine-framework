#!/usr/bin/python3

import sys

import load_variables as lv
import process_variables_sim as pvs
sys.path.append("../../../scripts")
import process_variables as pv

# Provides access to extended variable files.
# Loads the base variable files and includes defaults, contents of referenced
# files, and additional parameters.

def set_path_to_engine(path):
    lv.set_path_to_engine(path)
    return

def get_group_vars():
    group_vars = {}
    group_vars.update({'all': lv.load_group_vars_all()})
    return {'group_vars': group_vars}

def get_host_vars(hosts):
    host_vars = {}
    for host in hosts:
        host_vars.update({host: lv.load_host_vars(host)})
    return { 'host_vars': host_vars }

def get_topology(topology):
    topo = lv.load_topology(topology)
    return topo

# Get nodes with nodes and node_mapping from a topology file, if referenced.
def get_nodes(scene):
    nodes = lv.load_nodes(scene)
    topo = nodes['topology']
    if topo != '': # topology variable should always be defined, but can be left empty
        topology = lv.load_topology(topo)
        nodes['nodes'] = topology['nodes']
        nodes['node_mapping'] = topology['node_mapping']
    return nodes

# Loads the scene's network file and extends flows by basic_flows from the topoflows file, if referenced, and 
def get_network(scene):
    network = lv.load_network(scene)
    nets = network['network']
    for net in nets.values():
        if 'topo_flows' in net:
            topo = net['topo_flows']
            if topo != None: # topo_flows variable is optional
                topology = lv.load_topology(topo)
                net['flows'].update(topology['basic_flows'])
    return network

# includes default values for missing entries.
def get_network_with_defaults(scene):
    network = get_network(scene)
    network_defaults = lv.load_network_defaults()
    network['priority_list'] = network_defaults['priority_list']
    network['remote_flow_file'] = network_defaults['remote_flow_file']
    if 'tsnconfigs' in network.keys():
        tsnconfigs = network['tsnconfigs']
        for tsnconfig in tsnconfigs.values():
            taprio = tsnconfig['taprio']
            if 'delay' not in taprio:
                taprio['delay'] = network_defaults['tsn_txtime_delay']
            queues = tsnconfig['queues']
            for queue in queues.values():
                if 'delta' not in queue:
                    queue['delta'] = network_defaults['tsn_etf_delta']
    return network

# get_network() with processed variables
def get_network_processed(scene):
    network = get_network(scene)
    if 'tsnconfigs' in network.keys():
        tsnconfigs = network['tsnconfigs']
        for tsnconfig in tsnconfigs.values():
            tsnconfig['prio2queue_mapping'] = pvs.prio2queue_mapping(tsnconfig['queues'])
            if 'sched' in tsnconfig['taprio'].keys(): 
                tsnconfig['taprio']['schedule'] = pvs.schedule(len(tsnconfig['queues']), tsnconfig['taprio']['sched'])
    nets = network['network']
    for net in nets.values():
        node_to_flow_to_interface_mapping = pv.map_node_to_flow_to_interfaces(net['flows'])
        net['node_to_flow_to_interface_mapping'] = node_to_flow_to_interface_mapping
        used_interfaces = {}
        for node, flows_to_interface_mapping in node_to_flow_to_interface_mapping.items():
            used_interfaces[node] = []
            for _, interfaces in flows_to_interface_mapping.items():
                used_interfaces[node] = list(set(used_interfaces[node]).union(set(interfaces)))
        net['node_to_used_interfaces_mapping'] = used_interfaces
        net['node_to_interface_to_tsn_mapping'] = pv.map_node_to_interface_to_tsn(net['tsn'])
    return network

def get_stacks(scene):
    stacks = lv.load_stacks(scene)
    return stacks

def get_service_defaults(services):
    service_defaults = {}
    for service in services:
        service_defaults.update({service: lv.load_service_defaults(service)})
    return { 'service_defaults': service_defaults }

def get_stacks_with_service_defaults(scene):
    stacks = lv.load_stacks(scene)
    service_names = set()
    for stack in stacks['stacks'].values():
        for node_services in stack['services'].values():
            for service in node_services:
                service_names.add(service['name'])
    service_defaults = get_service_defaults(service_names)
    stacks.update(service_defaults)
    return stacks

def get_actions(scene):
    actions = lv.load_actions(scene)
    return actions

def get_experiments(scene):
    experiments = lv.load_experiments(scene)
    return experiments

def get_experiments_with_defaults(scene):
    experiments = get_experiments(scene)
    experiment_defaults = lv.load_experiment_defaults()
    for experiment in experiments['experiments']:
        if ( not 'signal' in experiment.keys() or experiment['signal'] is False ) and not 'time' in experiment.keys():
            experiment['time'] = experiment_defaults['experiment_time']
        if ( 'signal' in experiment.keys() and experiment['signal'] is True ) and not 'timeout' in experiment.keys():
            experiment['timeout'] = experiment_defaults['experiment_timeout']
    return experiments

def get_simulation_defaults():
    simulation_defaults = lv.load_simulation_defaults()
    return simulation_defaults

#def get_all