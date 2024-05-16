#!/usr/bin/python3

# Post-process every single experiment

import argparse
import sys
import time
import os

sys.path.append("../../../scripts")
import scenario_variables
import process_variables as pv
sys.path.append("../../services/tcpdump/files")
import csv_parser_pcap_single as cpps
import ndn_pcap_parser as npp
import csv_parser_pcap_combined as cppc
import processing_descriptor
import plot_csv_combined as ppc
import plot_csv_single as pps
sys.path.append("../../services/queue_monitor/files")
import csv_parser_qm as cpqm
import plot_qm as pqm
from copy import deepcopy

from multiprocessing import Process, Semaphore

sys.path.append("../../generate_config/files")
import access_variables as av

# the script will create csvs and plots if the corresponding variable is set to true
csv = True
plot = True
sim = False
# if process_on_node is true, the data of individidual nodes will be processed on that node itself
process_on_node = False
node_name = ''
# concurrent limit is the maximum number of concurrent processes that can be run 
concurrent_limit = 8
experiment_name = ''
num_isolated_cores = 0
ndn = False

def process_queues(pd):
    '''plots queue levels of qdiscs, not supported right now'''
    if csv:
        cpqm.save_qm_to_csv(pd)
    if plot:
        pqm.plotQueueLevelPacketsOrBytesOptWithLog("Packets", pd)
        pqm.plotQueueLevelPacketsOrBytesOptWithLog("Bytes", pd)

def process_endpoint_csv(pd, sema):
    '''parses pcaps into csv's, only for single endpoint of a stream (no jitter/delay)'''
    if process_on_node and node_name != pd.node:
        sema.release()
        return
    if csv and not pd.ndn:
        cpps.parse_separate_pcaps(pd)
    if csv and pd.ndn:
        npp.parse(pd)
    sema.release()

def process_stream_csv(pd_end, pd_start, sema):
    '''parses csv's created from process_endpoint_csv to create new csv's for jitter/delay'''
    global csv
    if process_on_node:
        # cannot correlate packets if we only have data of one node currently
        sema.release()
        return
    if csv:
        cppc.save_delay_and_jitter_to_csv(pd_end, pd_start)
    sema.release()

def process_endpoint_plot(pd, sema):
    '''plots results from csv's parsed from process_endpoint_csv'''
    if process_on_node and node_name != pd.node:
        sema.release()
        return
    if plot:
        pps.plot_all(pd)
    sema.release()

def process_stream_plot(pd_end, pd_start, sema):
    '''plots results from csv's parsed from process_stream_csv'''
    if process_on_node:
        # cannot correlate packets if we only have data of one node currently
        sema.release()
        return
    if plot:
        ppc.plot_all(pd_end)
    sema.release()

def iface_with_name(node_to_flow_to_interfaces_mapping, nodes, node, flow):
    '''returns name of the iface of flow endpoints (so only start and end node) from flow id'''
    ifaces = node_to_flow_to_interfaces_mapping[node][flow]
    iface = int(ifaces[0]) # end point only has single interface on flow
    host = nodes['node_mapping'][node]
    iface_name = av.get_host_vars([host])['host_vars'][host]['node_ifaces'][iface]['name']
    return iface, iface_name

def get_free_core(processes):
    '''finds a free core from the isolated cores to run the new process on'''
    if num_isolated_cores <= 1:
        return -1
    cores = [False for i in range(0, num_isolated_cores)]
    for p, core in processes:
        if p.is_alive():
            cores[core] = True
    for i in range(1, num_isolated_cores):
        if not cores[i]:
            return i
    # if there is no free core, return -1, this will run the core on non isolated cores
    return -1

def start_process(target, args, processes):
    '''helper function for starting a new process'''
    global csv
    args[-1].acquire()
    # get a isolated core to run the process on (returns -1 if none available)
    core = get_free_core(processes)
    p = Process(target=target, args=args)
    processes.append((p, core))
    p.start()
    if core > 0 and p.pid != None:
        os.sched_setaffinity(p.pid, {core})

def process_exp(folder_scene, nodes, net, stack, exp):
    '''parses experiments, finds flow endpoints with a service running and plots the results'''
    exp_name = exp['name']
    global concurrent_limit
    sema = Semaphore(concurrent_limit)
    # first step: identify streams, scan the stacks.yml file to store what service is on what port/node
    # flow_to_node_to_port_to_services_mapping structure: 
    # flow_to_node_to_port_to_services_mapping[flow id][node id][port of service] = [services bound to the given flow, node ids and port]
    # below loop extracts only relevant services for post processing
    # !! only store in the array the endpoint which generates the packets (for iperf this is the client, for example)
    # iperf and send_udp the below code only extracts client or source services as the other end of the flow has the 
    # corresponding sink service
    flow_to_node_to_port_to_services_mapping = {} # identify streams by flow, destination port and start node (thus direction) 
    for node, services in stack['services'].items():
        for service in services:
            service_name = service['name']
            if service_name in ['iperf', 'send_udp']:
                service_flow = service['flow']
                service_port = service['port']
                service_role = service['role']
                # consider source service instances only; assume correct setup of tcpdump and sink instances
                if service_role in ['client', 'source', 'push_source']:
                    if service_flow not in flow_to_node_to_port_to_services_mapping.keys():
                        flow_to_node_to_port_to_services_mapping[service_flow] = {}
                    if node not in flow_to_node_to_port_to_services_mapping[service_flow].keys():
                        flow_to_node_to_port_to_services_mapping[service_flow][node] = {}
                    if service_port not in flow_to_node_to_port_to_services_mapping[service_flow][node].keys():
                        flow_to_node_to_port_to_services_mapping[service_flow][node][service_port] = []
                    flow_to_node_to_port_to_services_mapping[service_flow][node][service_port].append(service)
            elif service_name in ['ndn-traffic']:
                continue
                service_flows = service['flows']
                service_role = service['role']
                if service_role in ['client']:
                    for service_flow in service_flows:
                        service_content = '/' + str(service_flow) + service['content']
                        if service_flow not in flow_to_node_to_port_to_services_mapping.keys():
                            flow_to_node_to_port_to_services_mapping[service_flow] = {}
                        if node not in flow_to_node_to_port_to_services_mapping[service_flow].keys():
                            flow_to_node_to_port_to_services_mapping[service_flow][node] = {}
                        if service_content not in flow_to_node_to_port_to_services_mapping[service_flow][node].keys():
                            flow_to_node_to_port_to_services_mapping[service_flow][node][service_content] = []
                        flow_to_node_to_port_to_services_mapping[service_flow][node][service_content].append(service)
            elif service_name == 'tcpdump':
                continue # ignore for now; tcpdump is currently used in combination with iperf / send_udp only
            elif service_name == 'queue_monitor':
                continue # TODO
            else:
                continue # ignore unknown services
    
    streams_csv = []
    plot_single = []
    streams_plot = []
    processes = []
    # second step: do processing
    node_to_flow_to_interfaces_mapping = pv.map_node_to_flow_to_interfaces(net['flows'])
    # loop through flows, and identify service pairs belonging to start/end points of that flow to process
    for flow, node_to_port_to_services_mapping in flow_to_node_to_port_to_services_mapping.items():
        flow_nodes = net['flows'][flow].split(',')
        # get first and last node of the flow
        first = flow_nodes[0].split(':')[1]
        last = flow_nodes[-1].split(':')[1]
        # get the iface names belonging to the flow endpoints
        iface_first, iface_name_first = iface_with_name(node_to_flow_to_interfaces_mapping, nodes, first, flow)
        ifaces_last, iface_name_last = iface_with_name(node_to_flow_to_interfaces_mapping, nodes, last, flow)
        for node, port_to_services_mapping in node_to_port_to_services_mapping.items():
            ports = port_to_services_mapping.keys()
            # create processing descriptor classes for start and endpoint of the flow
            # pd_source is where the packets originate
            if node == first:
                pd_source = processing_descriptor.ProcessingDescriptor(folder_scene, exp_name, node, str(iface_first) if sim else iface_name_first, sim, ndn=ndn)
                pd_sink = processing_descriptor.ProcessingDescriptor(folder_scene, exp_name, last, str(ifaces_last) if sim else iface_name_last, sim, ndn=ndn)
            if node == last:
                pd_source = processing_descriptor.ProcessingDescriptor(folder_scene, exp_name, node, str(ifaces_last) if sim else iface_name_last, sim, ndn=ndn)
                pd_sink = processing_descriptor.ProcessingDescriptor(folder_scene, exp_name, first, str(iface_first) if sim else iface_name_first, sim, ndn=ndn)

            # create csv's for each individual port and service pair
            # the script assumes there is a singular service for a single port
            for port, services in port_to_services_mapping.items():
                # for service in services:
                service = services[0] # FIXME: assume single source per port
                pd_source.dst_ports = [port]
                pd_sink.dst_ports = [port]
                # info dictionary stores the service and all its variables with the key as the port the service belongs to
                # script uses info dictionary to determine which service a port belongs to, for service specific parsing/plotting
                # created csv names also use service name on info dictionary
                pd_source.info = {port: service}
                pd_sink.info = {port: service}
                start_process(process_endpoint_csv, (pd_source, sema), processes)
                start_process(process_endpoint_csv, (pd_sink, sema), processes)
                streams_csv.append((deepcopy(pd_sink), deepcopy(pd_source)))
            # this part is for plotting
            # add every port to the dst_ports of processing descriptor at the same time, so that it will plot all the ports 
            # in the same graph
            pd_source2 = deepcopy(pd_source)
            pd_sink2 = deepcopy(pd_sink)
            pd_source2.dst_ports = list(ports)
            pd_sink2.dst_ports = list(ports)
            for port, services in port_to_services_mapping.items():
                pd_source2.info.update({port: services[0]})
                pd_sink2.info.update({port: services[0]})
            
            plot_single.append(pd_source2)
            plot_single.append(pd_sink2)
            streams_plot.append((pd_sink2, pd_source2))
    
    # the functions are run in this order for every node:
    # process_endpoint_csv -> process_endpoint_plot -> process_stream_csv -> process_stream_plot
    # it is clear why plotting scripts should run after parsing scripts
    # process_stream_csv  uses csv's created from process_endpoint_csv to correlate packets, it does not use pcaps

    for p, _ in processes:
        p.join()
    processes = []
    # process streams after processing endpoints
    for pd in plot_single:
        start_process(process_endpoint_plot, (pd, sema), processes)
    for pd_sink, pd_source in streams_csv:
        start_process(process_stream_csv, (pd_sink, pd_source, sema), processes)
    for p, _ in processes:
        p.join()
    processes = []
    for pd_sink, pd_source in streams_plot:
        start_process(process_stream_plot, (pd_sink, pd_source, sema), processes)
    for p, _ in processes:
        p.join()

# processing for NDN only
def process_ndn(folder_scene, nodes, net, stack, exp):
    print('Processing NDN')
    exp_name = exp['name']
    global concurrent_limit, ndn, csv
    sema = Semaphore(concurrent_limit)
    processes = []
    # first parse probe pcaps for all nodes
    # it parses probe tcpdumps and creates individual csv's for each name 
    for node in nodes['node_mapping'].keys():
        pd = processing_descriptor.ProcessingDescriptor(folder_scene, exp_name, node, '', sim, ndn=True)
        start_process(process_endpoint_csv, (pd, sema), processes)

    for p, _ in processes:
        p.join()
    processes = []

    for node, services in stack['services'].items():
        pd = processing_descriptor.ProcessingDescriptor(folder_scene, exp_name, node, '', sim, ndn=True, dst_ports=[])
        for service in services:
            service_name = service['name']
            if service_name in ['ndn-traffic']:
                # we parse directly from tcpdump_probe, unlike normal iperf/send_udp individual tcpdumps for each service
                # so can not determine service name while parsing from tcpdump_probe
                # I don't update info dictionary of pd here, service name of any service of ndn will be assumed 'ndn' (for csv naming purposes)
                # because even if 2 different services use NDN, what matters only is the content name 
                content = service['content']
                role = service['role']
                pd.dst_ports.append(content)
            else:
                continue # ignore unknown services
        # plot data that does not need correlating
        start_process(process_endpoint_plot, (pd, sema), processes)

    streams = []

    # the loop checks every node pair, to see if they have packets belonging to same name, if so plots/correlates them
    for node, services in stack['services'].items():
        # first loop is for 'source' nodes
        sources = []
        for service in services:
            service_name = service['name']
            if service_name in ['ndn-traffic'] and (service['role'] == 'source' or service['role'] == 'push_source'):
                sources.append(service['content'])
        for node2, services2 in stack['services'].items(): 
            # second loop is for 'client' nodes
            dst_ports = []
            if node2 == node:
                continue
            for service2 in services2:
                service_name = service2['name']
                # if node2 is the client of a name that the node is source of, to correlate them and create delay csv's
                if service_name in ['ndn-traffic'] and service2['role'] == 'client' and service2['content'] in sources:
                    dst_ports.append(service2['content'])
                    pd1 = processing_descriptor.ProcessingDescriptor(folder_scene, exp_name, node, '', sim, ndn=True, dst_ports=[dst_ports[-1]])
                    pd2 = processing_descriptor.ProcessingDescriptor(folder_scene, exp_name, node2, '', sim, ndn=True, dst_ports=[dst_ports[-1]])
                    # start_process(process_stream_csv, (pd1, pd2, sema), processes) ## Old version
                    start_process(process_stream_csv, (pd2, pd1, sema), processes)
            if dst_ports != []:
                # store pd's with all names in the dst_ports array, to plot them together 
                pdAll1 = processing_descriptor.ProcessingDescriptor(folder_scene, exp_name, node, '', sim, ndn=True, dst_ports=dst_ports)
                pdAll2 = processing_descriptor.ProcessingDescriptor(folder_scene, exp_name, node2, '', sim, ndn=True, dst_ports=dst_ports)
                # streams.append((pdAll1, pdAll2)) ## Old version
                streams.append((pdAll2, pdAll1))

    for p, _ in processes:
        p.join()
    processes = []

    for pd1, pd2 in streams: 
        start_process(process_stream_plot, (pd1, pd2, sema), processes)
    
    for p, _ in processes:
        p.join()
    processes = []

def process(scene, folder_scene):
    '''loop through experiments of a scenario'''
    fl = folder_scene+'/pythonLog.txt'

    global node_name, experiment_name, ndn

    with open(fl, "a") as myFile:
        print('\n\nStarting Evaluation...\n', file=myFile)
    startTime = time.time()

    nodes = av.get_nodes(scene)

    # extract the name of the current node
    for name_num, inventory_name in nodes['node_mapping'].items():
        if inventory_name == node_name:
            node_name = name_num
            break
    network_processed = av.get_network_processed(scene)
    stacks_with_service_defaults = av.get_stacks_with_service_defaults(scene)
    # actions = av.get_actions(scene)
    experiments = av.get_experiments(scene)

    # check if experiment is a ndn experiment
    if 'ndn' in nodes.keys() and nodes['ndn'] == True:
        ndn = True

    for exp in experiments['experiments']:
        if process_on_node and exp['name'] != experiment_name:
            continue
        net = network_processed['network'][exp['network']]
        stack = stacks_with_service_defaults['stacks'][exp['stack']]
        #action = actions['actions'][exp['action']]
        # if it is an ndn experiment call ndn processing
        if ndn:
            process_ndn(folder_scene, nodes, net, stack, exp)
        process_exp(folder_scene, nodes, net, stack, exp)

    with open(fl, "a") as myFile:
        print('Evaluation took:', time.time()-startTime, file=myFile)

def parse_cli(args):
    """Parse command line arguments """
    parser = argparse.ArgumentParser(prog='process', description='Convert pcaps to csv and create graphs')
    parser.add_argument('scene', help='Scenario')
    parser.add_argument('-f', '--folder_scene', help='Scenario folder with result files to process')
    parser.add_argument('-d', '--directory', default='../../plays', help='EnGINE plays folder')
    parser.add_argument('-c', '--csv', action='store_true', help='Create CSV files')
    parser.add_argument('-p', '--plot', action='store_true', help='Create plot files')
    parser.add_argument('-s', '--sim', action='store_true', help='Do simulation specific processing')
    parser.add_argument('-pn', '--process_on_node', action='store_true', help='Process on nodes')
    parser.add_argument('-n', '--node_name', help='Name of the node if parsing on nodes')
    parser.add_argument('-e', '--experiment_name', help='Name of the experiment if parsing on nodes')
    parser.add_argument('-i', '--isolated_cores', default='0', help='Number of isolated cores for scenario')
    return parser.parse_args(args)

def main():
    parser_args = parse_cli(sys.argv[1:])
    scene  = parser_args.scene
    folder_scene = parser_args.folder_scene
    directory  = parser_args.directory

    global csv, plot, sim, node_name, process_on_node, experiment_name, num_isolated_cores
    num_isolated_cores = int(parser_args.isolated_cores)
    csv = parser_args.csv
    plot = parser_args.plot
    sim = parser_args.sim
    process_on_node = parser_args.process_on_node
    node_name = parser_args.node_name
    experiment_name = parser_args.experiment_name

    av.set_path_to_engine(directory)
    process(scene, folder_scene)

if __name__ == "__main__":
    main()
