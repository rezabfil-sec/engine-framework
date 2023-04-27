#!/usr/bin/python3

# Post-process every single experiment

import argparse
import sys
import time

import processing_descriptor
sys.path.append("../../../scripts")
import scenario_variables
import process_variables as pv
sys.path.append("../../services/tcpdump/files")
import csv_parser_pcap_single as cpps
import plot_pcap_single as pps
import csv_parser_pcap_combined as cppc
import plot_pcap_combined as ppc

sys.path.append("../../generate_config/files")
import access_variables as av

csv = False
plot = False
sim = False

def process_endpoint(pd):
    '''functions to be applied to the result files of a single end point of a stream'''
    if csv:
        cpps.parse_separate_pcaps(pd)
    if plot:
        pps.plot_all(pd)
        #pps.plotManualTPcalcMultiFlowOptDiffToTargetBitrate(pd)
        #pps.plotManualIfsCDFcalcMultiFlow(pd)

def process_stream(pd_end, pd_start):
    '''functions to be applied to the combined result files of both end points of a stream'''
    if csv:
        cppc.save_delay_and_jitter_to_csv(pd_end, pd_start)
    if plot:
        ppc.plot_all(pd_end)
        #ppc.plotManualDelaycalcMultiFlow(pd_end)
        #ppc.plotManualJittercalcMultiFlow(pd_end)
        #ppc.plotManualJitterCDFcalcMultiFlow(pd_end)
        #ppc.plotManualPacketLosscalcMultiFlow(pd_end)

def iface_with_name(node_to_flow_to_interfaces_mapping, nodes, node, flow):
        ifaces = node_to_flow_to_interfaces_mapping[node][flow]
        iface = int(ifaces[0]) # end point only has single interface on flow
        host = nodes['node_mapping'][node]
        iface_name = av.get_host_vars([host])['host_vars'][host]['node_ifaces'][iface]['name']
        return iface, iface_name

def process_exp(folder_scene, nodes, net, stack, exp):
    '''process a single experiment'''
    exp_name = exp['name']
    # FIXME: could use additional information like signal mode, timeout, or
    # exp_time = exp['time']

    # first step: identify streams
    flow_to_node_to_port_to_services_mapping = {} # identify streams by flow, destination port and start node (thus direction) 
    for node, services in stack['services'].items():
        for service in services:
            service_name = service['name']
            if service_name in ['iperf', 'send_udp']:
                service_flow = service['flow']
                service_port = service['port']
                service_role = service['role']
                if service_role in ['client', 'source']: # consider source service instances only; assume correct setup of tcpdump and sink instances
                    if service_flow not in flow_to_node_to_port_to_services_mapping.keys():
                        flow_to_node_to_port_to_services_mapping[service_flow] = {}
                    if node not in flow_to_node_to_port_to_services_mapping[service_flow].keys():
                        flow_to_node_to_port_to_services_mapping[service_flow][node] = {}
                    if service_port not in flow_to_node_to_port_to_services_mapping[service_flow][node].keys():
                        flow_to_node_to_port_to_services_mapping[service_flow][node][service_port] = []
                    flow_to_node_to_port_to_services_mapping[service_flow][node][service_port].append(service)
            elif service_name == 'tcpdump':
                continue # ignore for now; tcpdump is currently used in combination with iperf / send_udp only
            else:
                continue # ignore unknown services

    # second step: do processing
    node_to_flow_to_interfaces_mapping = pv.map_node_to_flow_to_interfaces(net['flows'])
    for flow, node_to_port_to_services_mapping in flow_to_node_to_port_to_services_mapping.items():
        flow_nodes = net['flows'][flow].split(',')
        first = flow_nodes[0].split(':')[1]
        last = flow_nodes[-1].split(':')[1]
        iface_first, iface_name_first = iface_with_name(node_to_flow_to_interfaces_mapping, nodes, first, flow)
        iface_last, iface_name_last = iface_with_name(node_to_flow_to_interfaces_mapping, nodes, last, flow)
        for node, port_to_services_mapping in node_to_port_to_services_mapping.items():
            ports = port_to_services_mapping.keys()
            if node == first:
                pd_source = processing_descriptor.ProcessingDescriptor(folder_scene, exp_name, node, str(iface_first) if sim else iface_name_first, sim)
                pd_sink = processing_descriptor.ProcessingDescriptor(folder_scene, exp_name, last, str(iface_last) if sim else iface_name_last, sim)
            if node == last:
                pd_source = processing_descriptor.ProcessingDescriptor(folder_scene, exp_name, node, str(iface_last) if sim else iface_name_last, sim)
                pd_sink = processing_descriptor.ProcessingDescriptor(folder_scene, exp_name, first, str(iface_first) if sim else iface_name_first, sim)
            for port, services in port_to_services_mapping.items():
                # for service in services:
                service = services[0] # FIXME: assume single source per port
                pd_source.dst_ports = [port]
                pd_sink.dst_ports = [port]
                pd_source.info = {port: service}
                pd_sink.info = {port: service}
                process_endpoint(pd_source)
                process_endpoint(pd_sink)
                process_stream(pd_sink, pd_source)
            if len(ports) > 1:
                pd_source.dst_ports = ports
                pd_sink.dst_ports = ports
                for port, services in port_to_services_mapping.items():
                    pd_source.info.update({port: services[0]})
                    pd_sink.info.update({port: services[0]})
                process_endpoint(pd_source)
                process_endpoint(pd_sink)
                process_stream(pd_sink, pd_source)

def process(scene, folder_scene):
    fl = folder_scene+'/pythonLog.txt'
    with open(fl, "w") as myFile:
        print('\n\nStarting Evaluation...\n', file=myFile)
    startTime = time.time()

    nodes = av.get_nodes(scene)
    network_processed = av.get_network_processed(scene)
    stacks_with_service_defaults = av.get_stacks_with_service_defaults(scene)
    # actions = av.get_actions(scene)
    experiments = av.get_experiments(scene)

    for exp in experiments['experiments']:
        net = network_processed['network'][exp['network']]
        stack = stacks_with_service_defaults['stacks'][exp['stack']]
        #action = actions['actions'][exp['action']]
        process_exp(folder_scene, nodes, net, stack, exp)

    with open(fl, "a") as myFile:
        print('Evaluation took:', time.time()-startTime, file=myFile)

def parse_cli(args):
    """Parse command line arguments """
    parser = argparse.ArgumentParser(prog='iperf_process', description='Convert iperf log file to csv and create graphs')
    parser.add_argument('scene', help='Scenario')
    parser.add_argument('-f', '--folder_scene', help='Scenario folder with result files to process')
    parser.add_argument('-d', '--directory', default='../../..', help='EnGINE ansible root dir')
    parser.add_argument('-c', '--csv', action='store_true', help='Create CSV files')
    parser.add_argument('-p', '--plot', action='store_true', help='Create plot files')
    parser.add_argument('-s', '--sim', action='store_true', help='Do simulation specific processing')
    return parser.parse_args(args)

def main():
    parser_args = parse_cli(sys.argv[1:])
    scene  = parser_args.scene
    folder_scene = parser_args.folder_scene
    directory  = parser_args.directory
    global csv, plot, sim
    csv = parser_args.csv
    plot = parser_args.plot
    sim = parser_args.sim

    av.set_path_to_engine(directory)
    process(scene, folder_scene)

if __name__ == "__main__":
    main()
