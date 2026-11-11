#!/usr/bin/env python3

import argparse
import configparser
import json
import os, sys
from typing import List

def create_config(num_nodes: int, singlethread: bool, hostnamesP2P: List[str], hostnamesSrv: List[str], ports_p2p: List[int], ports_interface: List[int]):
    """ creates the INI files 
    num_nodes: number of nodes n
    hostnamesP2P: list for all nodes containing their hostname/IP for the P2P part
    hostnamesSrv: list for all nodes containing their hostname/IP to run their client interface on
    ports_p2p: the ports of the nodes for P2P communication
    ports_interface: the client interface ports for all the nodes
    """
    # config files for all peers
    ids = range(1, num_nodes+1)

    for peer_id in range(1, num_nodes+1):
        config = configparser.ConfigParser(allow_no_value=True)
        for (i, hostP2P, hostSrv, port, port_interface) in zip(ids, hostnamesP2P, hostnamesSrv, ports_p2p, ports_interface):
            if peer_id == i:
                config["default"] = {
                    "id": i,
                    "addr": f"{hostP2P}:{port}",
                    "# A key will be automatically generated if these files are not present": None,
                    "# Paths are relative to this config file": None,
                    "pubkey": f"/root/peer{i}.pubkey",
                    "seckey": f"/root/peer{i}.seckey",
                    "# The interface where a client can send signing request to": None,
                    "interface": f"{hostSrv}:{port_interface}",
                    "# A peer can run multi-threaded or single-threaded. Defaults to false (multi-threaded).": None,
                    "singlethread": f"{singlethread}",
                    }
            else:
                config[str(i)] = {
                    "addr": f"{hostP2P}:{port}",
                    "pubkey": f"/root/peer{i}.pubkey",
                    }
        fpath = os.path.join(os.path.dirname(sys.argv[0]), f"peer{peer_id}.cfg")
        with open(fpath, "w") as cfgfile:
            config.write(cfgfile)

    # write config file for the client
    config = configparser.ConfigParser(allow_no_value=True)
    config["default"] = {"# ip:port where to connect to the signing interface": None,
                         "interface": f"{hostnamesSrv[0]}:{ports_interface[0]}",
                         "# Path to load and store the public threshold signature verification key": None,
                         "group_key": "/root/thresholdsig.pubkey",
                         }
    for (i, hostSrv, port_interface) in zip(ids, hostnamesSrv, ports_interface):
        config[str(i)] = {
            "interface": f"{hostSrv}:{port_interface}",
            }
    fpath = os.path.join(os.path.dirname(sys.argv[0]), f"client.cfg")
    with open(fpath, "w") as cfgfile:
        config.write(cfgfile)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Creates the config files for all the nodes in TRES.")
    parser.add_argument("--num", "-n", type=int, required=True, help="Total number of nodes in the system. \
                        (The threshold t is configured at runtime)")
    parser.add_argument("--hostp2p", "-ip", type=str, default="localhost", help="IP of the nodes for the P2P network\
                        (Run the whole network on one physical host)")
    parser.add_argument("--hostinter", "-ii", type=str, default="localhost", help="The IP of the client interfaces")
    parser.add_argument("--port_start", "-p", type=int, default=20000, help="Begin of port range to use. 2xxx0 will be \
                        the P2P port and 2xxx1 the client interface.")
    parser.add_argument("--single-thread", "-S", action='store_true', help="Run each peer with only one thread")

    args = parser.parse_args()

    port_range_p2p = [(2000 + i)*10 for i in range(1, args.num+1)]
    port_range_interface = [(2000 + i)*10 + 1 for i in range(1, args.num+1)]

    # multiple 
    hostp2p = args.hostp2p
    f = open(hostp2p, 'r')
    ips_peers = json.loads(f.read())
    f.close()

    # running on a single node
    if len(ips_peers) == 1:
        ips_peers = [ips_peers[0]] * args.num
        client_ips = [ips_peers[0]] * args.num
    else:
        client_ips = ips_peers

    create_config(args.num, args.single_thread, ips_peers, client_ips, port_range_p2p, port_range_interface)
