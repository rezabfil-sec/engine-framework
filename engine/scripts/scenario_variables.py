#!/usr/bin/python3

import yaml
import os

# TODO: Remove
import pprint

# Extract scenario variables from the repository directory
# prepare them for further usage in python


#### AVAILABLE FUNCTIONS #########

# TODO WIP
# extract_experiments()
#    -> gives all experiments as dict

# Python Function documentation
#    https://www.sphinx-doc.org/en/master/

###################################

# TODO remove debug function
def foo():
    print("WORKING")

scene_files = [
    "00-nodes.yml",
    "01-network.yml",
    "02-stacks.yml",
    "03-actions.yml",
    "04-experiments.yml"
]

# TODO variables needed:
# - nodes + node mapping -> either directly or from pre-defined topologies
# - dictionary with every experiment and all variables for that experiment
#   { exp-1: { network: .(flows)., nodes: { node-1: { service: .., tsn: .., flow_ifaces: .., use_ifaces: ..} node-2: .., ..}}, exp-2: .., exp-3: ..}
# - a dictionary of experiments in the same category
#   { single: [exp-1, exp-2, exp-5], node_failure: [exp-3,exp-5], ... }
def extract(scene_dir):
    nodes  = extract_nodes(scene_dir)
    # TODO identify format of the config and write down..
    config = extract_config(scene_dir)
    
    # Groups not yet implemented
    # groups = extract_groups(scene_dir)
    groups = {}
    # pprint.pprint(nodes)
    # pprint.pprint(config)
    return nodes, config, groups


# nodes + node mapping -> either directly or from pre-defined topologies
def extract_nodes(scene_dir):
    retDict = {'nodes' : [], 'node_mapping' : []}
    with open(scene_dir+'/'+scene_files[0]) as fl:
    # with open(scene_files[0]) as fl:
        loadedNodes = yaml.load(fl, Loader=yaml.FullLoader)
        if loadedNodes['topology'] != '':
            print('Not yet implemented')
            return -1
        else:
            retDict['nodes'] = loadedNodes['nodes']
            retDict['node_mapping'] = loadedNodes['node_mapping']
    return retDict


# - dictionary with every experiment and all variables for that experiment
#   { exp-1: { network: .(flows)., nodes: { node-1: { service: .., tsn: .., flow_ifaces: .., use_ifaces: ..} node-2: .., ..}}, exp-2: .., exp-3: ..}
def extract_config(scene_dir):
    loadedExperiments = {}
    loadedNetworks = {}
    loadedStacks = {}
    loadedNodes = extract_nodes(scene_dir)
    # Load scenario configs
    with open(scene_dir+'/'+scene_files[4]) as fl4:
    # with open(scene_files[4]) as fl4:
        loadedExperiments = yaml.load(fl4, Loader=yaml.FullLoader)
        # print(loadedExperiments)
    with open(scene_dir+'/'+scene_files[1]) as fl1:
    # with open(scene_files[1]) as fl1:
        loadedNetworks = yaml.load(fl1, Loader=yaml.FullLoader)
        # print(loadedNetworks)
    with open(scene_dir+'/'+scene_files[2]) as fl2:
    # with open(scene_files[2]) as fl2:
        loadedStacks = yaml.load(fl2, Loader=yaml.FullLoader)
        # print(loadedStacks)
    resDict = {}
    # Go thorough uncommented experiments
    for num, experiment in enumerate(loadedExperiments['experiments']):
        # print(experiment)
        expIdent = 'exp-' + str(num+1)
        resDict[expIdent] = {} # Create dict entry for experiment
        network = loadedNetworks['network'][experiment['network']] # Get relevant network info for experiment
        relevantStack = loadedStacks['stacks'][experiment['stack']] # Get relevant stack info for experiment
        # pprint.pprint(network)
        # print(relevantStack)
        resDict[expIdent]['network'] = network['flows'] # Fill flows entry for experiment net
        resDict[expIdent]['name'] = experiment['name'] # Save the name of experiment as well
        
        # Go through nodes and fill in data
        resDict[expIdent]['nodes'] = {} 
        for node in loadedNodes['node_mapping']:
            # Prep node entry
            resDict[expIdent]['nodes'][node] = {}
            resDict[expIdent]['nodes'][node]['services'] = {}
            resDict[expIdent]['nodes'][node]['tsn'] = {}
            resDict[expIdent]['nodes'][node]['flow_ifaces'] = {}
            resDict[expIdent]['nodes'][node]['use_ifaces'] = {}

            # Fill only if any services present
            if node in relevantStack['services']:
                resDict[expIdent]['nodes'][node]['services'] = relevantStack['services'][node]
            # nodeName = loadedNodes['node_mapping'][node]
            # nodeInfo = {}
            # with open(scene_dir+'../../host_vars/'+nodeName+'.yml') as flN:
            #     nodeInfo = yaml.load(flN, Loader=yaml.FullLoader)
            # pprint.pprint(nodeInfo)

        
        # Fill tsn data at the end
        for tsn in network['tsn']:
            relevantTsnConfig = loadedNetworks['tsnconfigs'][tsn]
            # print(network['tsn'])
            # print(resDict[expIdent]['nodes'])
            # print(relevantTsnConfig)
            for node in network['tsn'][tsn]:
                if ':' in node:
                    if 'tsn' not in resDict[expIdent]['nodes'][node.split(':')[0]]:
                        resDict[expIdent]['nodes'][node.split(':')[0]]['tsn'] = {}
                    resDict[expIdent]['nodes'][node.split(':')[0]]['tsn'][node] = relevantTsnConfig
                else:
                    resDict[expIdent]['nodes'][node]['tsn'] = relevantTsnConfig
        
        # Fill in the flow_ifaces data
        for flow in network['flows']:
            theFlow = network['flows'][flow]
            for entry in theFlow.split(','):
                values = entry.split(':')
                resDict[expIdent]['nodes'][values[1]]['flow_ifaces'][flow] = {}
                nodeName = loadedNodes['node_mapping'][values[1]]
                nodeInfo = {}
                with open(scene_dir+'/../../host_vars/'+nodeName+'.yml') as flN:
                # with open('../../host_vars/'+nodeName+'.yml') as flN:
                    nodeInfo = yaml.load(flN, Loader=yaml.FullLoader)
                # pprint.pprint(nodeInfo)
                if values[0] != '':
                    resDict[expIdent]['nodes'][values[1]]['flow_ifaces'][flow][int(values[0])] = {}
                    resDict[expIdent]['nodes'][values[1]]['flow_ifaces'][flow][int(values[0])]['iface_flow_position'] = 'left'
                    resDict[expIdent]['nodes'][values[1]]['flow_ifaces'][flow][int(values[0])]['iface_info'] = nodeInfo['node_ifaces'][int(values[0])]
                if values[2] != '':
                    resDict[expIdent]['nodes'][values[1]]['flow_ifaces'][flow][int(values[2])] = {}
                    resDict[expIdent]['nodes'][values[1]]['flow_ifaces'][flow][int(values[2])]['iface_flow_position'] = 'right'
                    resDict[expIdent]['nodes'][values[1]]['flow_ifaces'][flow][int(values[2])]['iface_info'] = nodeInfo['node_ifaces'][int(values[2])]

    return resDict

# - a dictionary of experiments in the same category
#   { single: [exp-1, exp-2, exp-5], node_failure: [exp-3,exp-5], ... }
def extract_groups(scene_dir):
    pass

# print(extract_nodes(os.getcwd()+'/../scenarios/hops-cbs/'))
# pprint.pprint(extract_config(os.getcwd()+'/../scenarios/hops-cbs/'))