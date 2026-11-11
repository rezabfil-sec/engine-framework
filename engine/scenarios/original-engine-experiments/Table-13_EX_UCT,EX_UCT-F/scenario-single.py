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

for exp in config:
    cfg = config[exp]
    # print(cfg)
    usedFlowPort = {}
    usedFlowPortCliServPair = {}
    for n in cfg['nodes']:
        node = cfg['nodes'][n]
        # print(n, node['services'])
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
                
            if node['flow_ifaces'] != {}:
                if flow in node['flow_ifaces']:
                    for ifNum in node['flow_ifaces'][flow]:
                        if n in cliSrvPorts:
                            refTS = pri.plotManualTPcalcMultiFlow(cfg['name'], folder_scene, folder_scene, int(n.split('-')[1]), node['flow_ifaces'][flow][ifNum]['iface_info']['name'], usedFlowPort[flow], float(0.01))
                        else:
                            for nam in cliSrvPorts:
                                if n in cliSrvPorts[nam]:
                                    pri.plotManualTPcalcMultiFlow(cfg['name'], folder_scene, folder_scene, int(n.split('-')[1]), node['flow_ifaces'][flow][ifNum]['iface_info']['name'], usedFlowPort[flow], float(0.01))

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
                        refTS = pri.plotManualDelaycalcMultiFlow(cfg['name'], folder_scene, folder_scene, int(srv.split('-')[1]), iFaceEnd, cliSrvPorts[cli][srv])
                        pri.plotManualJittercalcMultiFlow(cfg['name'], folder_scene, folder_scene, int(srv.split('-')[1]), iFaceEnd, cliSrvPorts[cli][srv])
                        pri.plotManualJitterCDFcalcMultiFlow(cfg['name'], folder_scene, folder_scene, int(srv.split('-')[1]), iFaceEnd, cliSrvPorts[cli][srv])
                        pri.plotManualPacketLosscalcMultiFlow(cfg['name'], folder_scene, folder_scene, int(srv.split('-')[1]), iFaceEnd, cliSrvPorts[cli][srv], refTS)
                        pri.plotManualIfsCDFcalcMultiFlow(cfg['name'], folder_scene, folder_scene, int(srv.split('-')[1]), iFaceEnd, cliSrvPorts[cli][srv])
with open(fl, "a") as myFile:
    print('Evaluation took:', time.time()-startTime, file=myFile)