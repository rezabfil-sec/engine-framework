#!/usr/bin/python3

import subprocess
import json
import sys
import argparse

CONTAINERD_IFACE_ID = "1"

def parse_cli(args):
    """Parse command line arguments """
    parser = argparse.ArgumentParser(prog='physicalflows',
                description='Create and apply IPs')
    parser.add_argument('-n', '--node',
                        help='Node variable (e.g. node-1)')
    parser.add_argument('-f', '--flowfile',
                        help='Json file with all flows')
    parser.add_argument('-i', '--ifaces',
                        help='Provides a list of node interfaces')
    parser.add_argument('-c', '--containerd', action='store_true',
                        help='Flag to indicate that the node is a containerd node (running Docker, Kata, etc.)')
    return parser.parse_args(args)

def get_ip(subnet, node, iface, dst=False):
    if int(iface) > 250:
       sys.exit(1)
    subnet_nr = subnet.split("-")[1]
    node_nr = ""
    if not dst:
        node_nr = node.split("-")[1].split(":")[0]
        # print("not destination", node_nr, type(node_nr))
        # if node_nr is "":
        #     print("node number is empty")
        #     node_nr = node.split("-")[1].split(":")[0]
        print(subnet_nr, node_nr, iface, dst)
        final_ip = "10.{}.{}.{}/16".format(subnet_nr, node_nr, iface)
    else:
        print(node)
        node_nr = node
        final_ip = "10.{}.{}.{}/16".format(subnet_nr, node_nr, iface)
    print(subnet_nr, node_nr, iface)
    print(final_ip)
    return final_ip
    
def assign_ip(ip, iface):
    if is_containerd:
        print("IP", ip, "IFACE", iface, "MAPPED_TO", CONTAINERD_IFACE_ID)
        iface = CONTAINERD_IFACE_ID
    else:
        print("IP", ip, "IFACE", iface)

    iface_hw = node_ifaces[iface]['name']
    # add ip address
    cmd = "ip addr add %s dev %s" % (ip, iface_hw)
    subprocess.run(cmd.split(" "), stdout=subprocess.PIPE)
    # bring interface up
    cmd = "ip link set %s up" % (iface_hw)
    subprocess.run(cmd.split(" "), stdout=subprocess.PIPE, check=True)

def create_physical(iface_in, iface_out, flow, subnet, ip_dst):
    """ Create a receiving virtual interface for the endpoints of a flow
    Several methods possible:
    1. Single virtual interface with one IP per host, attach VLAN id assigned by port
    2. Virtual interfaces for every flow one interface (need for many different ips based on flow id and node)
    3. Virtual interfaces for every physical interface (defined ips can be used) assign vlan ids by port
    -> Implemented 2
    """
    # Here a name is assigned
    iface = "flow%s" % flow
    # Unify formats with ovs_flows
    # In means dst
    print("iface in", iface_in, "iface out", iface_out, "node", node, "flow", flow, "subnet", subnet, "dst ip", ip_dst)
    if iface_in:
        print("iface in")
        ip = get_ip(subnet, node, iface_in)
        assign_ip(ip, iface_in)
        print(ip, ip_dst)
        flow_ifaces.append({"name": iface, "hw": iface_in, "role": "sink", "ip_src": ip.split("/")[0], "ip_dst": ip_dst.split("/")[0], "flow": flow})
    if iface_out:
        print("iface out")
        ip = get_ip(subnet, node, iface_out)
        assign_ip(ip, iface_out)
        print(ip, ip_dst)
        flow_ifaces.append({"name": iface, "hw": iface_out, "role": "source", "ip_src": ip.split("/")[0], "ip_dst": ip_dst.split("/")[0], "flow": flow})
        # flow_ifaces.append({"name": iface, "hw": iface_out, "role": "source", "ip_src": ipsrc, "ip_dst": ipdst, "flow": flow})
# ---------------- START MAIN ---------------------

parser_args = parse_cli(sys.argv[1:])
name = parser_args.node
flowfile = parser_args.flowfile
nodeifacesfile = parser_args.ifaces
is_containerd = parser_args.containerd

with open(flowfile, 'r') as stream:
    flows = json.load(stream)

with open(nodeifacesfile, 'r') as stream:
    node_ifaces = json.load(stream)

flow_ifaces = []
use_ifaces = set()

for flow in list(flows.keys()) :

    # Sanity Check
    if int(flow) >= 254:
        print("ERROR: python script currently not adapted for more than 100 flows")
        # Limitation in IP address (~256)
        sys.exit(1)

    # Flow Format: { 1: ':<node1>:<iface-out>-<iface-in>:<node2>:', 2: '..' }
    subnet = flows[flow].split(";")[0]
    nodes = flows[flow].split(";")[1].split(",")
    print(subnet)
    print(nodes)
    i = 0
    for node in nodes:
        iface_in, node_name, iface_out = node.split(":")
        if name == node_name:
            print(node_name)
            # Extract node and iface name
            # If 0 means that this is the "source"
            if i < 1:
                dst_node = nodes[1].split(":")
                dst_node_name = dst_node[1].split("-")[1]
                dst_node_iface = dst_node[0]
                iface_dst = False
            # If 1 means that this is the "sink"
            else:
                dst_node = nodes[0].split(":")
                dst_node_name = dst_node[1].split("-")[1]
                dst_node_iface = dst_node[2]
                iface_dst = True
            
            print("Dst name", dst_node_name, "dst iface", dst_node_iface, "Is destination", iface_dst)
            ip_dst = get_ip(subnet, dst_node_name, dst_node_iface, True)
            print("destination IP", ip_dst)
            # 1. Case - Start Flow
            if not iface_in and iface_out:
                print("Start flow")
                create_physical(iface_in, iface_out, flow, subnet, ip_dst)
                use_ifaces.add(iface_out)
                print(iface_in, iface_out)
                continue
            # 2. Case - End Flow
            elif not iface_out and iface_in:
                print("End flow")
                create_physical(iface_in, iface_out, flow, subnet, ip_dst)
                print(iface_in, iface_out)
                use_ifaces.add(iface_in)
                continue
            else:
                print("Invalid interface ports [in: %s, out: %s]" % (
                    iface_in, iface_out))
                sys.exit(1)
        i = i + 1
# return flow interfaces
print(list(use_ifaces))
print(flow_ifaces)
