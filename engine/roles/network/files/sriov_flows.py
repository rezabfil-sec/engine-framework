#!/usr/bin/python3

import subprocess
import json
import sys
import argparse

def parse_cli(args):
    """Parse command line arguments """
    parser = argparse.ArgumentParser(prog='sriov',
                description='Create and apply IPs')
    parser.add_argument('-n', '--node',
                        help='Node variable (e.g. node-1)')
    parser.add_argument('-f', '--flowfile',
                        help='Json file with all flows')
    parser.add_argument('-i', '--ifaces',
                        help='Provides a list of node interfaces')
    return parser.parse_args(args)

def check_if_virtual(iface):
    print("Checking if virtual or physical", iface)
    if len(iface.split(".")) == 1:
        print("Physical")
        return False
    else:
        print("virtual")
        return True

def get_ip(subnet, node, iface, dst=False, sriov=False):
    subnet_nr = subnet.split("-")[1]
    node_nr = ""
    if not dst:
        node_nr = node.split("-")[1].split(":")[0]
        # print("not destination", node_nr, type(node_nr))
        # if node_nr is "":
        #     print("node number is empty")
        #     node_nr = node.split("-")[1].split(":")[0]
        print(subnet_nr, node_nr, iface, dst)
        if sriov:
            iface_hw = iface.split('.')[0]
            iface_veth = iface.split('.')[1]
            final_ip = "10.{}.{}.{}{}/16".format(subnet_nr, node_nr, iface_hw, iface_veth)
        else:
            final_ip = "10.{}.{}.{}/16".format(subnet_nr, node_nr, iface)
    else:
        print(node)
        node_nr = node
        if sriov:
            iface_hw = iface.split('.')[0]
            iface_veth = iface.split('.')[1]
            final_ip = "10.{}.{}.{}{}/16".format(subnet_nr, node_nr, iface_hw, iface_veth)
        else:
            final_ip = "10.{}.{}.{}/16".format(subnet_nr, node_nr, iface)
    print(subnet_nr, node_nr, iface)
    print(final_ip)
    return final_ip
    
def assign_ip(ip, iface, sriov=False):
    if sriov:
        print("IFACE", iface)
        iface_hw = iface.split('.')[0]
        iface_veth_nr = iface.split('.')[1]
        iface_hw_name = node_ifaces[iface_hw]['name']
        hw_ifaces.append(iface_hw_name)
        iface_name = iface_hw_name+'v'+str(int(iface_veth_nr)-1)
        virtual_ifaces.append(iface_name)
    else:
        hw_ifaces.append(node_ifaces[iface]['name'])
        iface_name = node_ifaces[iface]['name']
    # add ip address
    cmd = "ip addr add %s dev %s" % (ip, iface_name)
    subprocess.run(cmd.split(" "), stdout=subprocess.PIPE)
    # bring interface up
    cmd = "ip link set %s up" % (iface_name)
    subprocess.run(cmd.split(" "), stdout=subprocess.PIPE, check=True)
    return iface_name

def create_physical(iface_in, iface_out, flow, subnet, ip_dst, sriov=False):
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
        ip = get_ip(subnet, node, iface_in, sriov=sriov)
        hw_name = assign_ip(ip, iface_in, sriov=sriov)
        print(ip, ip_dst)
        flow_ifaces.append({"name": iface, "hw": iface_in, "role": "sink", "ip_src": ip.split("/")[0], "ip_dst": ip_dst.split("/")[0], "flow": flow, "iface_name": hw_name })
    if iface_out:
        print("iface out")
        ip = get_ip(subnet, node, iface_out, sriov=sriov)
        hw_name = assign_ip(ip, iface_out, sriov=sriov)
        print(ip, ip_dst)
        flow_ifaces.append({"name": iface, "hw": iface_out, "role": "source", "ip_src": ip.split("/")[0], "ip_dst": ip_dst.split("/")[0], "flow": flow, "iface_name": hw_name })
        # flow_ifaces.append({"name": iface, "hw": iface_out, "role": "source", "ip_src": ipsrc, "ip_dst": ipdst, "flow": flow})
# ---------------- START MAIN ---------------------

parser_args = parse_cli(sys.argv[1:])
name = parser_args.node
flowfile = parser_args.flowfile
nodeifacesfile = parser_args.ifaces

with open(flowfile, 'r') as stream:
    flows = json.load(stream)

with open(nodeifacesfile, 'r') as stream:
    node_ifaces = json.load(stream)

flow_ifaces = []
use_ifaces = set()
hw_ifaces = []
virtual_ifaces = []
sriov = True
for flow in list(flows.keys()):

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
        print(iface_in, node_name, iface_out)
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
            sriov = check_if_virtual(dst_node_iface)
            ip_dst = get_ip(subnet, dst_node_name, dst_node_iface, True, sriov)
            print("destination IP", ip_dst)
            # 1. Case - Start Flow
            if not iface_in and iface_out:
                print("Start flow")
                sriov = check_if_virtual(iface_out)
                create_physical(iface_in, iface_out, flow, subnet, ip_dst, sriov)
                use_ifaces.add(iface_out)
                print(iface_in, iface_out)
                continue
            # 2. Case - End Flow
            elif not iface_out and iface_in:
                print("End flow")
                sriov = check_if_virtual(iface_in)
                create_physical(iface_in, iface_out, flow, subnet, ip_dst, sriov)
                print(iface_in, iface_out)
                use_ifaces.add(iface_in)
                continue
            else:
                print("Invalid interface ports [in: %s, out: %s]" % (
                    iface_in, iface_out))
                sys.exit(1)
        i = i + 1
# return flow interfaces
print(virtual_ifaces)
print(hw_ifaces)
print(list(use_ifaces))
print(flow_ifaces)
