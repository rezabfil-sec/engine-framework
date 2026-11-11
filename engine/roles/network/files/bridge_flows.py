#!/usr/bin/python3

import subprocess
import json
import sys
import argparse

SUBNET_OFFSET = 77

def parse_cli(args):
    """Parse command line arguments """
    parser = argparse.ArgumentParser(prog='bridgeflows',
                description='Set up bridging for containerd on a physical host')
    parser.add_argument('-n', '--node',
                        help='Node variable (e.g. node-1)')
    parser.add_argument('-f', '--flowfile',
                        help='Json file with all flows')
    parser.add_argument('-i', '--ifaces',
                        help='Provides a list of node interfaces')
    parser.add_argument('-m', '--nodemap',
                        help='Json file with mappings from nodes to hostname')
    parser.add_argument('-c', '--containers',
                        help='Json file with all containers')
    parser.add_argument('-b', '--bridge',
                        help='Name of the bridge to use')
    return parser.parse_args(args)

def get_subnet_hop(subnet):
    """ Get subnet for hop """
    subnet_nr = subnet.split("-")[1]
    return f"subnet-{int(subnet_nr) + SUBNET_OFFSET}"

def get_bridge_ip():
    """ Get IP address of bridge """
    cmd = "ip addr show %s" % bridge
    result = subprocess.run(cmd.split(" "), stdout=subprocess.PIPE, check=True)
    output = result.stdout.decode('utf-8')
    for line in output.split("\n"):
        if "inet" in line:
            return line.strip().split(" ")[1].split("/")[0]

def is_container(node):
    """ Check if node is a container """
    hostname = node_map[node]

    # iterate containers dict
    # structure: {host: [{name: name}], host2: [{name: name2}]}
    for _, container_list in containers.items():
        for container in container_list:
            if container['name'] == hostname:
                return True

    return False

def is_host_of(node):
    """ Check if current node is host of node """
    hostname = node_map[cur_node]
    node_hostname = node_map[node]

    for container in containers[hostname]:
        if container['name'] == node_hostname:
            return True
    
    return False

def get_ip(subnet, node, iface, dst=False):
    if int(iface) > 10:
       sys.exit(1)

    subnet_nr = subnet.split("-")[1]
    node_nr = node.split("-")[1].split(":")[0]
    final_ip = "10.{}.{}.{}/16".format(subnet_nr, node_nr, iface)

    return final_ip

def get_ip_hop(subnet, node, dst=False):
    subnet_nr = subnet.split("-")[1]
    node_nr = node.split("-")[1].split(":")[0]
    final_ip = "10.{}.{}.0/24".format(subnet_nr, node_nr)

    return final_ip
    
def assign_ip(ip, iface):
    iface_hw = node_ifaces[iface]['name']
    # add ip address
    cmd = "ip addr add %s dev %s" % (ip, iface_hw)
    subprocess.run(cmd.split(" "), stdout=subprocess.PIPE)
    # bring interface up
    cmd = "ip link set %s up" % (iface_hw)
    subprocess.run(cmd.split(" "), stdout=subprocess.PIPE, check=True)

def route_via_bridge(ip):
    """ Route traffic to bridge """
    ip = ip.split("/")[0]
    cmd = "ip route add %s dev %s src %s" % (ip, bridge, get_bridge_ip())
    try:
        subprocess.run(cmd.split(" "), stdout=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {cmd}")
        print(f"Error output: {e.output}")

def disable_promiscuous_mode(iface):
    """ Disable promiscuous mode """
    iface_hw = node_ifaces[iface]['name']
    cmd = "ip link set %s promisc off" % (iface_hw)
    subprocess.run(cmd.split(" "), stdout=subprocess.PIPE, check=True)

def plug_iface_to_bridge(iface):
    """ Plug interface into bridge (i.e., make its master the bridge) """
    # disable promiscuous mode first due to a bug with ice
    # we sometimes get "File exists", which is actually the following error:
    # ice [...] $IFACE: failed to initialize vlan filtering on this port
    disable_promiscuous_mode(iface)
    iface_hw = node_ifaces[iface]['name']
    cmd = "ip link set %s master %s" % (iface_hw, bridge)
    try:
        subprocess.run(cmd.split(" "), stdout=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {cmd}")
        print(f"Error output: {e.output}")

def route_via_dev(match, via, iface):
    """ Route traffic via device """
    iface_hw = node_ifaces[iface]['name']
    via = via.split("/")[0]
    cmd = "ip route add %s via %s dev %s" % (match, via, iface_hw)
    try:
        subprocess.run(cmd.split(" "), stdout=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {cmd}")
        print(f"Error output: {e.output}")

# ---------------- START MAIN ---------------------

args = parse_cli(sys.argv[1:])
cur_node = args.node
flow_file = args.flowfile
ifaces_file = args.ifaces
nodemap_file = args.nodemap
containers_file = args.containers
bridge = args.bridge

with open(flow_file, 'r') as stream:
    flows = json.load(stream)

with open(ifaces_file, 'r') as stream:
    node_ifaces = json.load(stream)

with open(nodemap_file, 'r') as stream:
    node_map = json.load(stream)

with open(containers_file, 'r') as stream:
    containers = json.load(stream)

for flow in list(flows.keys()) :

    # Sanity Check
    if int(flow) >= 254:
        print("ERROR: python script currently not adapted for more than 100 flows")
        # Limitation in IP address (~256)
        sys.exit(1)

    # Flow Format: { 1: 'subnet-n;:<node1>:<iface-out>-<iface-in>:<node2>:', 2: '..' }
    subnet = flows[flow].split(";")[0]
    subnet_hop = get_subnet_hop(subnet)
    nodes = flows[flow].split(";")[1].split(",")

    print(subnet)
    print(nodes)

    for i in range(len(nodes)):
        iface_in, node_name, iface_out = nodes[i].split(":")


        # If 0 means that this is the "source"
        if i < 1:
            dst = nodes[1].split(":")
            dst_node = dst[1]
            dst_node_iface = dst[0]
            src_node_iface = iface_out
        # If 1 means that this is the "sink"
        else:
            dst = nodes[0].split(":")
            dst_node = dst[1]
            dst_node_iface = dst[2]
            src_node_iface = iface_in

        if not is_container(node_name) and not is_container(dst_node):
            print("Physical flow from", node_name, "to", dst_node)

        if not is_container(node_name) or not is_host_of(node_name):
            print("Node", node_name, "is not a container or not hosted on", cur_node)
            continue

        print(f"source node: {node_name}, sink node: {dst_node}")
        print(f"source iface: {src_node_iface}, sink iface: {dst_node_iface}")

        ip_src = get_ip(subnet, node_name, src_node_iface)
        ip_dst = get_ip(subnet, dst_node, dst_node_iface, True)

        ip_src_hop = get_ip(subnet_hop, node_name, src_node_iface)
        ip_dst_hop = get_ip(subnet_hop, dst_node, dst_node_iface, True)

        print(f"source IP: {ip_src}, sink IP: {ip_dst}")

        # stop early if the other side is on the same bridge -- the bridge handles routing
        if is_host_of(dst_node):
            print("Node", dst_node, "is hosted on", cur_node)
            continue
    
        route_via_bridge(ip_src)
        plug_iface_to_bridge(src_node_iface)
        assign_ip(ip_src_hop, src_node_iface)

        # stop early if the other side is a physical host -- we know how to reach it
        if not is_container(dst_node):
            print("Node", dst_node, "is not a container or is on the same bridge as", cur_node)
            continue

        print(f"source IP hop: {ip_src_hop}, sink IP hop: {ip_dst_hop}")

        print(f"routing packets for {ip_src} via {bridge}")
        print(f"routing packets for {get_ip_hop(subnet, dst_node)} via iface {src_node_iface}")

        route_via_dev(get_ip_hop(subnet, dst_node), ip_src_hop, src_node_iface)
