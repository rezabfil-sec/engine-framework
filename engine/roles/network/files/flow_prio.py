#!/usr/bin/python3

import subprocess
import json
import sys
import argparse

ARP = 1
PASS = 2
SRC = 3
SINK = 4
START = 5
END = 6

def parse_cli(args):
    """Parse command line arguments """
    parser = argparse.ArgumentParser(prog='ovsflows',
                description='Create and apply Openflow rules')
    parser.add_argument('-n', '--node',
                        help='Node variable (e.g. node-1)')
    parser.add_argument('-v', '--vlanid',
                        help='Interface vlan id')
    parser.add_argument('-f', '--flowfile',
                        help='Json file with all flows')
    parser.add_argument('-p', '--flowprios',
                        help='Json file with priority to flow mappings')

    return parser.parse_args(args)

def get_flow_prio(flow):
    for prio in prios:
        for fl in prios[prio]:
            if int(flow) == int(fl):
                return prio
    return -1

# ---------------- START MAIN ---------------------

parser_args = parse_cli(sys.argv[1:])
name = parser_args.node
vid = parser_args.vlanid
flowfile = parser_args.flowfile
priofile = parser_args.flowprios

with open(flowfile, 'r') as stream:
    flows = json.load(stream)

with open(priofile, 'r') as stream:
    prios = json.load(stream)

flow_ifaces = []
use_ifaces = set()

# store tuples for iface peers; example: :node-1:2,3:node-2: yields [(2, 3, node-2)]
# read as: from current node on iface 2, we want to receive from node-2 via his iface 3
peer_ifaces = set()

for flow in list(flows.keys()) :
    nodes = flows[flow].split(",")
    for (i, node) in enumerate(nodes):
        iface_in, node_name, iface_out = node.split(":")
        if name == node_name:
            prio = get_flow_prio(flow)
            if int(prio) > 0:
                print('flow'+str(flow),str(prio))