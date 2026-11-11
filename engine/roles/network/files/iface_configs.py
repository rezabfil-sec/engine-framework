#!/usr/bin/python3

import subprocess
import json
import sys
import argparse

def parse_cli(args):
    """Parse command line arguments """
    parser = argparse.ArgumentParser(prog='iface',
                description='Extra virtual interfaces')
    parser.add_argument('-n', '--node',
                        help='Node variable (e.g. node-1)')
    parser.add_argument('-q', '--ifaceconfigfile',
                        help='Json file with all flows')
    parser.add_argument('-i', '--ifaces',
                        help='Provides a list of node interfaces')
    parser.add_argument('-c', '--count',
                        help='Specify how many virtual ifaces are used')
    return parser.parse_args(args)


def get_virtual_interfaces(node_ifaces, viface_count):
    virtual_ifaces = []
    for iface in node_ifaces:
        hw_iface_name = node_ifaces[iface]['name']
        for i in range(0,int(viface_count)):
            virtual_ifaces.append(hw_iface_name+"v"+str(i))
    return virtual_ifaces

def get_interfaces(node_ifaces, ifaces, viface_count):
# format ifaces {'2': ['1', '2'], '3': []}
# 3 : [] - physical iface
    v_ifaces = []
    ph_ifaces = []
    for iface in ifaces:
        list_of_ifaces = ifaces[iface]
        if list_of_ifaces:
            for viface in ifaces[iface]:
                if len(list_of_ifaces) > int(viface_count):
                    print("Too many virtual interfaces defined")
                    sys.exit(1)
                v_ifaces.append(node_ifaces[iface]["name"]+"v"+str(int(viface)-1))
            print("Virtual ifaces", ifaces[iface])
        else:
            ph_ifaces.append(node_ifaces[iface]["name"])
            print("Physical ifaces", ifaces[iface], iface)
    # virtual_ifaces = []
    # for iface in node_ifaces:
    #     hw_iface_name = node_ifaces[iface]['name']
    #     for i in range(0,int(viface_count)):
    #         virtual_ifaces.append(hw_iface_name+"v"+str(i))
    print(v_ifaces, ph_ifaces)
    return v_ifaces, ph_ifaces


# ---------------- START MAIN ---------------------

parser_args = parse_cli(sys.argv[1:])
name = parser_args.node
ifaceconfigfile = parser_args.ifaceconfigfile
nodeifacesfile = parser_args.ifaces
viface_count = parser_args.count

virtual_ifaces = []
physical_ifaces = []
try:
    with open(ifaceconfigfile, 'r') as stream:
        iface_config = json.load(stream)
except FileNotFoundError:
    print("No iface file found-->no tsn to be configured")
    print(virtual_ifaces)
    sys.exit(0)

with open(nodeifacesfile, 'r') as stream:
    node_ifaces = json.load(stream)

print(iface_config, iface_config["ifaces"])
print(node_ifaces)


# Apply on per veth and ph basis
if iface_config["ifaces"]:
    iface_configs = iface_config["ifaces"].split(",")
    print("more than 1 iface")
    ifaces = {}
    for iface in iface_configs:
        if len(iface.split(".")) > 1:
            print("SR-IOV iface")
            ph_iface = iface.split(".")[0]
            if ph_iface in ifaces:
                v_ifaces = ifaces[ph_iface]
                print("Already in", v_ifaces, type(v_ifaces))
                ifaces[ph_iface].append(iface.split(".")[1])
                print(ifaces[ph_iface])
            else:
                print("First addition to dict", iface.split(".")[1])
                ifaces[ph_iface] = [iface.split(".")[1]]
        else:
            ifaces[iface.split(".")[0]] = []
            print("Physical iface")
    print("interfaces", ifaces)
    print("Apply to subset of ifaces")
# Happens when config should be applied to all
else:
    virtual_ifaces = get_virtual_interfaces(node_ifaces, viface_count)
    print("Apply to all ifaces")

virtual_ifaces, physical_ifaces = get_interfaces(node_ifaces, ifaces, viface_count)
# return flow interfaces
print(virtual_ifaces)
print(physical_ifaces)