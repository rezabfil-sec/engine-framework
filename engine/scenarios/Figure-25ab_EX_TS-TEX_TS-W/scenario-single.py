#!/usr/bin/python3

# Post-process every single experiment

import sys
import argparse
import time

def parse_cli(args):
    """Parse command line arguments """
    parser = argparse.ArgumentParser(prog='iperf_process',
                description='Convert iperf log file to csv and create graphs')
    parser.add_argument('-d', '--dir',
                        help='Playbook directory')
    parser.add_argument('-s', '--scene',
                        help='Scenario')
    parser.add_argument('-f', '--folder_scene',
                        help='Scenario Folder management host')

    return parser.parse_args(args)

# ---------------- START MAIN ---------------------

onlyPlotFlag = False
onlyParseCsv = False
justParsePcap = True
parser_args = parse_cli(sys.argv[1:])
play_dir  = parser_args.dir
scene  = parser_args.scene
scripts_dir = play_dir.replace(play_dir.split("/")[-1], "scripts")
scene_dir = play_dir.replace(play_dir.split("/")[-1], "scenarios/%s" % scene)
folder_scene = parser_args.folder_scene

fl = folder_scene+'/pythonLog.txt'
with open(fl, "w") as myFile:
    print('\n\nStarting Evaluation...\n', file=myFile)
startTime = time.time()

#import local scripts
sys.path.append(scene_dir)
import plot_raw_iperf as pri

# add custom script path and import scripts
sys.path.append(scripts_dir)
import scenario_variables

nodes, config, groups = scenario_variables.extract(scene_dir)

sourceOfPcap = "iperf"
# sourceOfPcap = "send_udp"
for exp in config:
    cfg = config[exp]
    usedFlowPort = {}
    usedFlowPortCliServPair = {}
    nameClientFiles = []
    nameServerFiles = []
    for n in cfg['nodes']:
        node = cfg['nodes'][n]
        for service in node['services']:
            if service['name'] == 'iperf':
                if service['flow'] not in usedFlowPortCliServPair:
                    usedFlowPortCliServPair[service['flow']] = {}
                if service['port'] not in usedFlowPortCliServPair[service['flow']]:
                    usedFlowPortCliServPair[service['flow']][service['port']] = {}
                if service['role'] == 'client':
                    usedFlowPortCliServPair[service['flow']][service['port']]['client'] = n
                if service['role'] == 'server':
                    usedFlowPortCliServPair[service['flow']][service['port']]['server'] = n
                    if service['flow'] not in usedFlowPort:
                        usedFlowPort[service['flow']] = []
                    usedFlowPort[service['flow']].append(service['port'])
            elif service['name'] == 'send_udp':
                print("extracting file name of tcpdump")
                sourceOfPcap = "send_udp"
                print(service)
                if service['flow'][0] not in usedFlowPortCliServPair:
                    usedFlowPortCliServPair[service['flow'][0]] = {}
                tmp = service['filter']
                port = str(tmp.split(" ")[2])
                print(port, type(port))
                if port not in usedFlowPortCliServPair[service['flow'][0]]:
                    print("before")
                    usedFlowPortCliServPair[service['flow'][0]][port] = {}
                    print("in port: ",usedFlowPortCliServPair)
                # identify inbound/outbound
                if 'outbound' in service['filter']:
                    usedFlowPortCliServPair[service['flow'][0]][port]['client'] = n
                    print(service['file'])
                    if service['file'] not in nameClientFiles:
                        nameClientFiles.append(service['file']) 
                    print("in client: ",usedFlowPortCliServPair)
                if 'inbound' in service['filter']:
                    usedFlowPortCliServPair[service['flow'][0]][port]['server'] = n
                    if service['file'] not in nameServerFiles:
                        nameServerFiles.append(service['file']) 
                    print("in server: ",usedFlowPortCliServPair)
                    if service['flow'][0] not in usedFlowPort:
                        usedFlowPort[service['flow'][0]] = []
                    usedFlowPort[service['flow'][0]].append(port) 
    refTS = 0
    for n in cfg['nodes']:
        node = cfg['nodes'][n]
        for flow in usedFlowPortCliServPair:
            cliSrvPorts = {}
            for stream in usedFlowPortCliServPair[flow]:
                if usedFlowPortCliServPair[flow][stream]['client'] not in cliSrvPorts:
                    cliSrvPorts[usedFlowPortCliServPair[flow][stream]['client']] = {}
                if usedFlowPortCliServPair[flow][stream]['server'] not in cliSrvPorts[usedFlowPortCliServPair[flow][stream]['client']]:
                    cliSrvPorts[usedFlowPortCliServPair[flow][stream]['client']][usedFlowPortCliServPair[flow][stream]['server']] = []
                cliSrvPorts[usedFlowPortCliServPair[flow][stream]['client']][usedFlowPortCliServPair[flow][stream]['server']].append(stream)
    for flow in usedFlowPortCliServPair:
        cliSrvPorts = {}
        for stream in usedFlowPortCliServPair[flow]:
            if usedFlowPortCliServPair[flow][stream]['client'] not in cliSrvPorts:
                cliSrvPorts[usedFlowPortCliServPair[flow][stream]['client']] = {}
            if usedFlowPortCliServPair[flow][stream]['server'] not in cliSrvPorts[usedFlowPortCliServPair[flow][stream]['client']]:
                cliSrvPorts[usedFlowPortCliServPair[flow][stream]['client']][usedFlowPortCliServPair[flow][stream]['server']] = []
            cliSrvPorts[usedFlowPortCliServPair[flow][stream]['client']][usedFlowPortCliServPair[flow][stream]['server']].append(stream)

        for cli in cliSrvPorts:
            for iFaceNumSt in cfg['nodes'][cli]['flow_ifaces'][flow]:
                iFaceStart = cfg['nodes'][cli]['flow_ifaces'][flow][iFaceNumSt]['iface_info']['name']
                for srv in cliSrvPorts[cli]:
                    for iFaceNumEn in cfg['nodes'][srv]['flow_ifaces'][flow]:
                        iFaceEnd = cfg['nodes'][srv]['flow_ifaces'][flow][iFaceNumEn]['iface_info']['name']
                        if not onlyPlotFlag:
                            refTS = pri.plotManualDelaycalcMultiFlow(cfg['name'], folder_scene, folder_scene, int(srv.split('-')[1]), iFaceEnd, cliSrvPorts[cli][srv], sourceOfPcap)
                            pri.plotManualJitterCDFcalcMultiFlow(cfg['name'], folder_scene, folder_scene, int(srv.split('-')[1]), iFaceEnd, cliSrvPorts[cli][srv], sourceOfPcap)
                            pri.plotManualPacketLosscalcMultiFlow(cfg['name'], folder_scene, folder_scene, int(srv.split('-')[1]), iFaceEnd, cliSrvPorts[cli][srv], refTS, sourceOfPcap)
                            pri.plotManualIfsCDFcalcMultiFlow(cfg['name'], folder_scene, folder_scene, int(srv.split('-')[1]), iFaceEnd, cliSrvPorts[cli][srv], sourceOfPcap)
                            pri.tableSummarizeAllValuesFlow(cfg['name'], folder_scene, folder_scene, int(srv.split('-')[1]), iFaceEnd, cliSrvPorts[cli][srv], sourceOfPcap)

with open(fl, "a") as myFile:
    print('Evaluation took:', time.time()-startTime, file=myFile)