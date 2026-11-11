#!/usr/bin/python3

# Post-process every single experiment

import argparse
import sys
import time

import processing_descriptor
sys.path.append("../../../scripts")
import scenario_variables
sys.path.append("../../services/tcpdump/files")
import csv_parser_pcap_single as cpps
import plot_pcap_single as pps
import csv_parser_pcap_combined as cppc
import plot_pcap_combined as ppc
sys.path.append("../../services/queue_monitor/files")
import csv_parser_qm as cpqm
import plot_qm as pqm

csv = False
plot = False
sim = False

def map_flows_to_cliserv(cfg):
    ''' Map flows to port and client plus server per stream '''
    flow_to_port_to_cliserv_mapping = {} # {1: {1001: {'client': 'node-1', 'server': 'node-2'}}} # keys are all flow numbers used for iperf services; respective value is dict, keys are ports used by those services, values are the respective client and server nodes
    for n in cfg['nodes']:
        node = cfg['nodes'][n]
        for service in node['services']:
            if service['name'] == 'iperf':
                if service['flow'] not in flow_to_port_to_cliserv_mapping:
                    flow_to_port_to_cliserv_mapping[service['flow']] = {}
                if service['port'] not in flow_to_port_to_cliserv_mapping[service['flow']]:
                    flow_to_port_to_cliserv_mapping[service['flow']][service['port']] = {}
                if service['role'] == 'client':
                    flow_to_port_to_cliserv_mapping[service['flow']][service['port']]['client'] = n
                if service['role'] == 'server':
                    flow_to_port_to_cliserv_mapping[service['flow']][service['port']]['server'] = n
    return flow_to_port_to_cliserv_mapping

def map_cli_to_srv_to_ports(port_to_cliserv_mapping):
    ''' Map client to server and ports for each stream, based on procvided flow specific port to client plus server mapping '''
    cli_to_srv_to_port_mapping = {} # {'node-1': {'node-2': [1001]}} # keys are iperf clients nodes, respective value is a dict mapping server nodes to the list of ports used per server
    for stream in port_to_cliserv_mapping:
        if port_to_cliserv_mapping[stream]['client'] not in cli_to_srv_to_port_mapping:
            cli_to_srv_to_port_mapping[port_to_cliserv_mapping[stream]['client']] = {}
        if port_to_cliserv_mapping[stream]['server'] not in cli_to_srv_to_port_mapping[port_to_cliserv_mapping[stream]['client']]:
            cli_to_srv_to_port_mapping[port_to_cliserv_mapping[stream]['client']][port_to_cliserv_mapping[stream]['server']] = []
        cli_to_srv_to_port_mapping[port_to_cliserv_mapping[stream]['client']][port_to_cliserv_mapping[stream]['server']].append(stream)
    return cli_to_srv_to_port_mapping

def process_queues(pd):
    if csv:
        cpqm.save_qm_to_csv(pd)
    if plot:
        pqm.plotQueueLevelPacketsOrBytesOptWithLog("Packets", pd)
        pqm.plotQueueLevelPacketsOrBytesOptWithLog("Bytes", pd)

# functions to be applied to the result files of a single end point of a stream
def process_endpoint(pd):
    if csv:
        cpps.parse_separate_pcaps(pd)
    if plot:
        pps.plot_all(pd)

# functions to be applied to the combined result files of both end points of a stream
def process_stream(pd_end, pd_start):
    if csv:
        cppc.save_delay_and_jitter_to_csv(pd_end, pd_start)
    if plot:
        ppc.plot_all(pd_end)

def process_exp(folder_scene, nodes, cfg, groups):
    cfg_name = cfg['name']
    flow_to_port_to_cliserv_mapping = map_flows_to_cliserv(cfg)

    ### 1st round: operate on single pcap files by calling functions for plotting etc
    for node, node_value in cfg['nodes'].items():
        for flow, port_to_cliserv_mapping in flow_to_port_to_cliserv_mapping.items():
            cli_to_srv_to_port_mapping = map_cli_to_srv_to_ports(port_to_cliserv_mapping)
            # if node_value['flow_ifaces'] != {}:
            if flow in node_value['flow_ifaces'].keys():
                # if node in cli_to_srv_to_port_mapping.keys(): [...] else: for srv_to_port_mapping in cli_to_srv_to_port_mapping.values(): if node in srv_to_port_mapping.keys():
                if node in cli_to_srv_to_port_mapping.keys() or node in [list(srv_to_port_mapping.keys())[0] for srv_to_port_mapping in cli_to_srv_to_port_mapping.values()]: # iperf client or server
                    ifNum = list(node_value['flow_ifaces'][flow].keys())[0] # for ifNum in node_value['flow_ifaces'][flow]: # There should be only one interface since the node is endpoint
                    pd = processing_descriptor.ProcessingDescriptor(folder_scene, cfg_name, node, str(ifNum) if sim else node_value['flow_ifaces'][flow][ifNum]['iface_info']['name'], sim, flow_to_port_to_cliserv_mapping[flow].keys(), ['cbs'])
                    process_endpoint(pd)
                    # if node in cli_to_srv_to_port_mapping.keys():
                    #     process_queues(pd)

    ### 2nd round: operate on the files of both end points by calling functions for plotting etc
    for flow, port_to_cliserv_mapping in flow_to_port_to_cliserv_mapping.items(): # for each flow with iperf stream
        cli_to_srv_to_port_mapping = map_cli_to_srv_to_ports(port_to_cliserv_mapping)
        for cli in cli_to_srv_to_port_mapping: # for each stream on this flow, i.e. each direction
            iFaceNumSt = list(cfg['nodes'][cli]['flow_ifaces'][flow].keys())[0] # for iFaceNumSt in cfg['nodes'][cli]['flow_ifaces'][flow]: # there should be only one iface, since this node is endpoint
            iFaceStart = cfg['nodes'][cli]['flow_ifaces'][flow][iFaceNumSt]['iface_info']['name']
            srv = list(cli_to_srv_to_port_mapping[cli].keys())[0] # for srv in cli_to_srv_to_port_mapping[cli]: # there should be only one, i.e. the other endpoint for this flow
            iFaceNumEn = list(cfg['nodes'][srv]['flow_ifaces'][flow].keys())[0] # for iFaceNumEn in cfg['nodes'][srv]['flow_ifaces'][flow]: # again, there should be only one iface, since this node is endpoint
            iFaceEnd = cfg['nodes'][srv]['flow_ifaces'][flow][iFaceNumEn]['iface_info']['name']
            pd_end = processing_descriptor.ProcessingDescriptor(folder_scene, cfg_name, srv, str(iFaceNumEn) if sim else iFaceEnd, sim, cli_to_srv_to_port_mapping[cli][srv])
            pd_start = processing_descriptor.ProcessingDescriptor(folder_scene, cfg_name, cli, str(iFaceNumSt) if sim else iFaceStart, sim, cli_to_srv_to_port_mapping[cli][srv])
            process_stream(pd_end, pd_start)

def process(scene, folder_scene, directory):
    scene_dir = directory + "/scenarios/" + scene

    fl = folder_scene+'/pythonLog.txt'
    with open(fl, "w") as myFile:
        print('\n\nStarting Evaluation...\n', file=myFile)
    startTime = time.time()

    nodes, config, groups = scenario_variables.extract(scene_dir)

    for cfg in config.values():
        process_exp(folder_scene, nodes, cfg, groups)

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

    process(scene, folder_scene, directory)

if __name__ == "__main__":
    main()
