#!/usr/bin/python3

import subprocess
import json
import sys
import argparse

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
    parser.add_argument('--arp_entries', action='store_true', help='Set up ARP entries')

    return parser.parse_args(args)

def get_mac(flow, dir_in):
    mac_suffix = "%s%s" % (str(int(int(flow) / 10)), str(int(flow) % 10))
    if dir_in:
        return "82:a3:c2:4a:a8:%s" % mac_suffix
    else:
        return "82:a3:c2:4a:a9:%s" % mac_suffix

def get_ip(flow, dir_in):
    return get_ip_no_cidr(flow, dir_in) + "/24"

def get_ip_no_cidr(flow, dir_in):
    if dir_in:
        return "10.0.%s.1" % flow
    else:
        return "10.0.%s.2" % flow

def create_virtual(iface_in, iface_out, flow, vid):
    """ Create a receiving virtual interface for the endpoints of a flow
    Several methods possible:
    1. Single virtual interface with one IP per host, attach VLAN id assigned by port
    2. Virtual interfaces for every flow one interface (need for many different ips based on flow id and node)
    3. Virtual interfaces for every physical interface (defined ips can be used) assign vlan ids by port
    -> Implemented 2
    """
    # Here a name is assigned
    iface = "flow%s" % flow
    #iface = "flow{}{}{}".format(flow,iface_in,iface_out)

    if iface_in:
        mac = get_mac(flow, False)
        ip = get_ip(flow, False)
        ipsrc = get_ip(flow, False).split("/")[0]
        ipdst = get_ip(flow, True).split("/")[0]
        flow_ifaces.append({"name": iface, "hw": iface_in, "role": "sink", "ip_src": ipsrc, "ip_dst": ipdst, "flow": flow})
    if iface_out:
        mac = get_mac(flow, True)
        ip = get_ip(flow, True)
        ipsrc = get_ip(flow, True).split("/")[0]
        ipdst = get_ip(flow, False).split("/")[0]
        flow_ifaces.append({"name": iface, "hw": iface_out, "role": "source", "ip_src": ipsrc, "ip_dst": ipdst, "flow": flow})

    # add port to ovs bridge
    cmd = "ovs-vsctl --may-exist add-port ovs0 %s tag=%s -- set interface %s ofport_request=%s -- set interface %s type=internal" % (
        iface, vid, iface, str(100+int(flow)), iface)
    subprocess.run(cmd.split(" "), stdout=subprocess.PIPE, check=True)
    # change mac address to a fixed and well known address
    cmd = "ip link set %s address %s" % (iface, mac)
    subprocess.run(cmd.split(" "), stdout=subprocess.PIPE, check=True)
    # add ip address
    cmd = "ip addr add %s dev %s" % (ip, iface)
    subprocess.run(cmd.split(" "), stdout=subprocess.PIPE)
    # bring interface up
    cmd = "ip link set %s up" % (iface)
    subprocess.run(cmd.split(" "), stdout=subprocess.PIPE, check=True)

def forward_flow(in_port, out_port, flow):
    # ARP - both directions
    cmd = "ovs-ofctl add-flow ovs0 in_port=%s,dl_src=%s,arp,priority=1,actions=output:%s" % (
        in_port, get_mac(flow, True), out_port)
    subprocess.run(cmd.split(" "), stdout=subprocess.PIPE, check=True)
    cmd = "ovs-ofctl add-flow ovs0 in_port=%s,dl_src=%s,arp,priority=1,actions=output:%s" % (
        out_port, get_mac(flow, False), in_port)
    subprocess.run(cmd.split(" "), stdout=subprocess.PIPE, check=True)
    # Traffic - both directions
    cmd = "ovs-ofctl add-flow ovs0 in_port=%s,dl_src=%s,dl_dst=%s,priority=1,action=output:%s" % (
        in_port, get_mac(flow, True), get_mac(flow, False), out_port)
    subprocess.run(cmd.split(" "), stdout=subprocess.PIPE, check=True)
    cmd = "ovs-ofctl add-flow ovs0 in_port=%s,dl_src=%s,dl_dst=%s,priority=1,action=output:%s" % (
        out_port, get_mac(flow, False), get_mac(flow, True), in_port)
    subprocess.run(cmd.split(" "), stdout=subprocess.PIPE, check=True)

def arp_entry(flow, dir_in):
    # cmd = "arp -s %s %s" % (get_ip_no_cidr(flow, dir_in), get_mac(flow, dir_in)) # use -i option? # arp command (part of net-tools) not installed for our setup, thus use ip neigh
    cmd = "ip neigh add %s lladdr %s nud permanent dev flow%s" % (get_ip_no_cidr(flow, dir_in), get_mac(flow, dir_in), flow)
    subprocess.run(cmd.split(" "), stdout=subprocess.PIPE, check=True)

# ---------------- START MAIN ---------------------

parser_args = parse_cli(sys.argv[1:])
name = parser_args.node
vid = parser_args.vlanid
flowfile = parser_args.flowfile
arp_entries = parser_args.arp_entries

with open(flowfile, 'r') as stream:
    flows = json.load(stream)

flow_ifaces = []
use_ifaces = set()

# store tuples for iface peers; example: :node-1:2,3:node-2: yields [(2, 3, node-2)]
# read as: from current node on iface 2, we want to receive from node-2 via his iface 3
peer_ifaces = set()

for flow in list(flows.keys()) :

    # Sanity Check
    if int(flow) >= 100:
        print("ERROR: python script currently not adapted for more than 100 flows")
        # Limitation in two places: [1] MAC address (~99) [2] IP address (~256)
        sys.exit(1)

    # Flow Format: { 1: ':<node1>:<iface-out>-<iface-in>:<node2>:', 2: '..' }
    nodes = flows[flow].split(",")
    for (i, node) in enumerate(nodes):
        iface_in, node_name, iface_out = node.split(":")
        if name == node_name:

            # Attach virtual interface - if node is at a flow end (start + end)
            if not iface_in or not iface_out:
                create_virtual(iface_in, iface_out, flow, vid)
            # Forwarding flows
            # 1. Case - Forwarding Flow
            if iface_in and iface_out:
                forward_flow(iface_in, iface_out, flow)
                use_ifaces.add(iface_in)
                use_ifaces.add(iface_out)

                peer_in, peer_name, peer_out = nodes[i-1].split(':')
                peer_ifaces.add((iface_in, peer_out, peer_name))

                peer_in, peer_name, peer_out = nodes[i+1].split(':')
                peer_ifaces.add((iface_out, peer_in, peer_name))
                continue
            # 2. Case - Start Flow
            elif not iface_in and iface_out:
                forward_flow(str(100+int(flow)), iface_out, flow)
                use_ifaces.add(iface_out)

                peer_in, peer_name, peer_out = nodes[i+1].split(':')
                peer_ifaces.add((iface_out, peer_in, peer_name))

                if arp_entries:
                    arp_entry(flow, False)
                continue
            # 3. Case - End Flow
            elif not iface_out and iface_in:
                forward_flow(iface_in, str(100+int(flow)), flow)
                use_ifaces.add(iface_in)

                peer_in, peer_name, peer_out = nodes[i-1].split(':')
                peer_ifaces.add((iface_in, peer_out, peer_name))

                if arp_entries:
                    arp_entry(flow, True)
                continue
            else:
                print("Invalid interface ports [in: %s, out: %s]" % (
                    iface_in, iface_out))
                sys.exit(1)

# return flow interfaces
print(list(use_ifaces))
print(flow_ifaces)
print(list(peer_ifaces))
