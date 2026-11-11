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

def define_action(out_port, flow, type):
    actn = "actions="
    # if type == SRC:
    #     add_actn = "mod_vlan_vid:%s,mod_vlan_pcp:%s," % (
    #         str(10+int(flow)), str(get_flow_prio(flow)))
    #     actn += add_actn
    # if type == SINK:
    #     actn += "strip_vlan,"

    if type == SRC:
        add_actn = "output:%s" % (
            str(int(out_port)*1000+int(get_flow_prio(flow))))
    # elif type == SINK:
    #     actn += "strip_vlan,"
    else:
        add_actn = "output:%s" % (
            out_port)
    actn += add_actn
    return actn

def get_flow_prio(flow):
    for prio in prios:
        for fl in prios[prio]:
            if int(flow) == int(fl):
                return prio
    return -1

def define_match(in_port, flow, dir, type):
    if type == ARP:
        mtch = "in_port=%s,dl_src=%s," % (
            in_port, get_mac(flow, dir))
        mtch += "arp,"
    if type == PASS or type == SINK:
        mtch = "in_port=%s,dl_src=%s," % (
            str(int(in_port)*1000+int(get_flow_prio(flow))), get_mac(flow, dir))
        # add_mtch = "dl_dst=%s,dl_vlan=%s,dl_vlan_pcp=%s," % (
        #     get_mac(flow, not dir), str(10+int(flow)), str(get_flow_prio(flow)))
        add_mtch = "dl_dst=%s," % (
            get_mac(flow, not dir))
        mtch += add_mtch
    if type == SRC:
        mtch = "in_port=%s,dl_src=%s," % (
            in_port, get_mac(flow, dir))
        add_mtch = "dl_dst=%s," % (
            get_mac(flow, not dir))
        mtch += add_mtch
    mtch += "priority=1,"
    return mtch

def forward_flow(in_port, out_port, flow, place):
    cmd_pre = "ovs-ofctl add-flow ovs0 "
    # ARP - both directions
    # print(define_match(in_port, out_port, flow, True, ARP))
    # print(define_match(in_port, out_port, flow, True, PASS))
    # cmd = "ovs-ofctl add-flow ovs0 in_port=%s,dl_src=%s,arp,priority=1,actions=output:%s" % (
    #     in_port, get_mac(flow, True), out_port)
    cmd = cmd_pre + define_match(in_port, flow, True, ARP) + define_action(out_port, flow, ARP)
    # print(cmd)
    subprocess.run(cmd.split(" "), stdout=subprocess.PIPE, check=True)
    # cmd = "ovs-ofctl add-flow ovs0 in_port=%s,dl_src=%s,arp,priority=1,actions=output:%s" % (
        # out_port, get_mac(flow, False), in_port)
    cmd = cmd_pre + define_match(out_port, flow, False, ARP) + define_action(in_port, flow, ARP)
    # print(cmd)
    subprocess.run(cmd.split(" "), stdout=subprocess.PIPE, check=True)
    # Traffic - both directions
    # cmd = "ovs-ofctl add-flow ovs0 in_port=%s,dl_src=%s,dl_dst=%s,priority=1,action=output:%s" % (
    #     in_port, get_mac(flow, True), get_mac(flow, False), out_port)
    

    act1 = PASS
    act2 = PASS
    if place == START:
        act1 = SRC
        act2 = SINK
    
    if place == END:
        act1 = SINK
        act2 = SRC

    cmd = cmd_pre + define_match(in_port, flow, True, act1) + define_action(out_port, flow, act1)
    # print(cmd)
    subprocess.run(cmd.split(" "), stdout=subprocess.PIPE, check=True)

    cmd = cmd_pre + define_match(out_port, flow, False, act2) + define_action(in_port, flow, act2)
    # print(cmd)

    
    # cmd = "ovs-ofctl add-flow ovs0 in_port=%s,dl_src=%s,dl_dst=%s,priority=1,action=output:%s" % (
        # out_port, get_mac(flow, False), get_mac(flow, True), in_port)
    subprocess.run(cmd.split(" "), stdout=subprocess.PIPE, check=True)


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
                forward_flow(iface_in, iface_out, flow, PASS)
                use_ifaces.add(iface_in)
                use_ifaces.add(iface_out)

                peer_in, peer_name, peer_out = nodes[i-1].split(':')
                peer_ifaces.add((iface_in, peer_out, peer_name))

                peer_in, peer_name, peer_out = nodes[i+1].split(':')
                peer_ifaces.add((iface_out, peer_in, peer_name))
                continue
            # 2. Case - Start Flow
            elif not iface_in and iface_out:
                forward_flow(str(100+int(flow)), iface_out, flow, START)
                use_ifaces.add(iface_out)

                peer_in, peer_name, peer_out = nodes[i+1].split(':')
                peer_ifaces.add((iface_out, peer_in, peer_name))
                continue
            # 3. Case - End Flow
            elif not iface_out and iface_in:
                forward_flow(iface_in, str(100+int(flow)), flow, END)
                use_ifaces.add(iface_in)

                peer_in, peer_name, peer_out = nodes[i-1].split(':')
                peer_ifaces.add((iface_in, peer_out, peer_name))
                continue
            else:
                print("Invalid interface ports [in: %s, out: %s]" % (
                    iface_in, iface_out))
                sys.exit(1)

# return flow interfaces
print(list(use_ifaces))
print(flow_ifaces)
print(list(peer_ifaces))
