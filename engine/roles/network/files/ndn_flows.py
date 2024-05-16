#!/usr/bin/python3

import subprocess
import json
import sys
import argparse
import time
import copy

def parse_cli(args):
    """Parse command line arguments """
    parser = argparse.ArgumentParser(prog='ndn_flows',
                description='Create and apply NDN faces/routes')
    parser.add_argument('-n', '--node',
                        help='Node variable (e.g. node-1)')
    parser.add_argument('-f', '--flowfile',
                        help='Json file with all flows')
    parser.add_argument('-p', '--flowprios',
                        help='Json file with priority to flow mappings')
    parser.add_argument('-i', '--flowicn',
                        help='Json file with icn-enabled flows mappings')
    parser.add_argument('-s', '--sourcepush', action='store_true', 
                        help='Specify whether this node is a push shource')
    # parser.add_argument('-t', '--forwarders',
    #                     help='Json file with all flows')

    return parser.parse_args(args)

def run_command(cmd):
    subprocess.run(cmd.split(" "), stdout=subprocess.PIPE, check=True)

def get_mac(flow, dir_in):
    mac_suffix = "%s%s" % (str(int(int(flow) / 10)), str(int(flow) % 10))
    if dir_in:
        return "82:a3:c2:4a:a8:%s" % mac_suffix
    else:
        return "82:a3:c2:4a:a9:%s" % mac_suffix

def get_ip(flow, dir_in):
    if dir_in:
        return "10.0.%s.1/24" % flow
    else:
        return "10.0.%s.2/24" % flow
    
def add_edge(edges, node1, iface1, mac2, node2):
    if node1 not in edges.keys():
        edges[node1] = []
    edges[node1].append((iface1, node2, mac2))

def add_face(flow, mac):
    iface = "flow%s" % flow
    cmd = f'nfdc face create remote ether://[{mac}] local dev://{iface}'
    print(cmd)
    run_command(cmd)    

def add_route(mac, path):
    cmd = f'nfdc route add {path} ether://[{mac}]'
    print(cmd)
    run_command(cmd)

# type: 'admit' or 'serve'; state: 'on' or 'off'
def conf_cs(type, state):
    cmd = f'nfdc cs config {type} {state}'
    print(cmd)
    run_command(cmd)

def getNeighorRoutes(allRoutesPrio, node, nodeList):
    # Get reachable prefixes from node
    reachPrefs = list(allRoutesPrio[node])
    # Remove current node from list cause we already checked it
    nodeList.remove(node)
    # Go through prefixes and see if we have any new ones
    for pref in reachPrefs:
        prefName = pref.split('/')[1]
        if prefName in nodeList:
            newReach = getNeighorRoutes(allRoutesPrio, prefName, nodeList)
            reachPrefs.extend([x for x in newReach if x.split('/')[1] in nodeList])
    # print('Node', node, 'reachable prefixes:', reachPrefs)
    return reachPrefs
    

# NOTE, this routing won't scale to massive networks
# NOTE2, this does not support the fast-path yet!
def construct_routing_tables(flows, prios, name):
    nodes = []
    for flow in list(flows.keys()):
        flowList = flows[flow].split(',')
        # for fl in flowList:
        #     # print('fl:', fl, fl.split(':'))
        nodes.extend([x.split(':')[1] for x in flowList])
    nodes = list(dict.fromkeys(nodes))
    # print('All nodes:', nodes)

    # format priority - node - target prefix - remote MAC of next hop
    routes = {}

    # Get initial, direct, routes for all nodes for each priority
    for prio in prios:
        # print('Preparing routes for prio', prio, 'with flows', list(prios[prio]))
        routes[prio] = {}
        for node in nodes:
            nodeRoutes = {}
            # Define routes based on flow endpoints
            for flow in list(prios[prio]):
                flowInfo = flows[flow].split(',')
                flowStart = flowInfo[0].split(':')[1]
                flowEnd = flowInfo[-1].split(':')[1]
                # Need to consider only start and end of the flow for NDN routes
                if node in flowStart:
                    prefix = '/'+flowEnd+'/prio'+str(prio)
                    remMac = get_mac(flow, False)
                    nodeRoutes[prefix] = remMac
                elif node in flowEnd:
                    prefix = '/'+flowStart+'/prio'+str(prio)
                    remMac = get_mac(flow, True)
                    nodeRoutes[prefix] = remMac
            routes[prio][node] = nodeRoutes
    # print('Initial routes:', routes)

    # Get routes for each priority
    currNodeRoutes = {}
    for prio in prios:
        # Make sure we construct routes for all nodes
        checkedNodes = [name]
        # Determine directly reachable prefixes
        currNodeRoutes[prio] = routes[prio][name]
        # Check neighbors and heighbors of neighbors multiple times to ensure all routes are discovered
        while set(nodes) != set(checkedNodes):
            # Ensure proper memory handling
            neighbors = copy.deepcopy(currNodeRoutes[prio])
            # Go through neighbors
            for neigh in neighbors:
                # Verify node not checked yet to avoid repeat routes (might cause problems with more complex topology)
                if neigh.split('/')[1] not in checkedNodes:
                    # Get MAC of the neighbor face
                    neighMac = currNodeRoutes[prio][neigh]
                    # Get all new possibilities reachable via neighbor
                    allNeighReach = getNeighorRoutes(routes[prio],neigh.split('/')[1], copy.deepcopy(nodes))
                    # Ignore routes we already knew before and loops
                    newReach = [x for x in allNeighReach if x not in currNodeRoutes[prio] and name not in x]
                    # Add new routes to the list
                    for elem in newReach:
                        currNodeRoutes[prio][elem] = neighMac
                    # Node is checked so put it to the list
                    checkedNodes.append(neigh.split('/')[1])
            
    # Return all reachable prefixes
    # print('->', currNodeRoutes)
    return currNodeRoutes

# ---------------- START MAIN ---------------------

parser_args = parse_cli(sys.argv[1:])
name = parser_args.node
flowfile = parser_args.flowfile
priofile = parser_args.flowprios
icnflowsfile = parser_args.flowicn
pushsource = parser_args.sourcepush
# forwardersfile = parser_args.forwarders

# print("Executing on", name)

with open(flowfile, 'r') as stream:
    allFlows = json.load(stream)

with open(priofile, 'r') as stream:
    allPrios = json.load(stream)

with open(icnflowsfile, 'r') as stream:
    icnflows = json.load(stream)


# exit(0)

# with open(forwardersfile, 'r') as stream:
#     forwarders = json.load(stream)

# edges = {}
# vis = {}
# queue = []
# p = 0

flows = {}
prios = {}

for flow in icnflows:
    flows[str(flow)] = allFlows[str(flow)]

for prio in allPrios:
    prios[prio] = {}
    for fl in allPrios[prio]:
        if int(fl) in icnflows:
            prios[prio][fl] = allPrios[prio][fl]

for flow in list(flows.keys()):
    print('Working on flow', flow)
    # Sanity Check
    if int(flow) >= 100:
        print("ERROR: python script currently not adapted for more than 100 flows")
        # Limitation in two places: [1] MAC address (~99) [2] IP address (~256)
        sys.exit(1)

    # Flow Format: { 1: ':<node1>:<iface-out>-<iface-in>:<node2>:', 2: '..' }
    # Extract flow nodes and their names
    nodes = flows[flow].split(',')
    # print('Flow', flow, 'invloves nodes:', nodes)
    nodeNames = [x.split(':')[1] for x in nodes]
    # print(nodeNames)
    # Add faces on end-points, but only on the current node!
    print('Working on node', name, 'with flow', flow, '- adding faces')
    first = nodeNames[0]
    last = nodeNames[-1]
    if first == name:
        add_face(flow, get_mac(flow, False))
    if last == name:
        add_face(flow, get_mac(flow, True))
        # add_route(get_mac(flow, False), name+'/'+str(flow)) # Routes are added separately

# Add routes
print('Working on node', name, 'with flow', flow, '- adding routes')
# Get relevant routes for node
nodeRoutes = construct_routing_tables(flows, prios, name)
# Add appropriate routes
for prio in nodeRoutes:
    for route in nodeRoutes[prio]:
        print('Adding route', route, 'on eth face', nodeRoutes[prio][route])
        add_route(nodeRoutes[prio][route], route)

if pushsource:
    print('Working on node', name, ' - node is a push source, not disabling cache')
else:
    print('Working on node', name, ' - node is not a push source, disabling cache')
    conf_cs('admit', 'off')
    conf_cs('serve', 'off')

