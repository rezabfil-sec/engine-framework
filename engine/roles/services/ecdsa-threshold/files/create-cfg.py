#!/usr/bin/env python3

from subprocess import Popen
import os
import yaml
import shutil
import sys
import json

# Possible configs
# # Lower bound of range for n
# min_players: 5
# # Upper bound of range for n
# max_players: 25
# # Experiment schemes, can be both or only one scheme. Accepted values: "GG18", "GG20"
# schemes: ["GG18", "GG20"]
# # Broadcast type. Accepted values: "BestEffort", "Echo", "Optimized"
# bc_type: "Optimized"
# # Base port used for processes. Supervisor listens on base_port, protocol process i on base_port + i
# base_port: 10000
# # Number of runs
# num_dkg_runs: 200
# num_dkr_runs: 200
# num_sig_runs: 200

# def getParams(min, max):
#     out = []
#     for n in range(min, max + 1, 5):
#         # Number of signers
#         numSigs = [math.ceil(n / 2.0), math.ceil(2.0/3.0 * n), n]
#         # actual threshold is num signers - 1
#         out += map(lambda t: (int(t - 1), n), numSigs)
#     return out


# base part is legacy. since it is part of the SocketAddr directly
def getLocalhost():
    return "127.0.0.1"

def getSocketAddr(IP, base_port):
    return f"{IP}:{base_port}"

def getPeersAddr(IPs, base_port, n):
    peers_ip = []
    for i in range(int(n) + 1):
        actual_port = base_port + i
        # more formatting
        peers_ip.append(getSocketAddr(IPs[i], actual_port))
    return peers_ip
# Peers contain all IPs as it was easier that way --> originally the code expected all of them that way so makes the indexing easier
def getConfigs(IPs, base_port, n, t, repetitions, scheme, bc_type):
    conf = {
        "supervisor_ip" : getSocketAddr(IPs[0], base_port),
        "peers" : getPeersAddr(IPs, base_port, n), 
        "num_players": n,
        "threshold": t,
        "num_dkg_runs": repetitions,
        "num_dkr_runs": repetitions,
        "num_sig_runs": 0,
        "base_port": base_port,
        "scheme": scheme,
        "bc_type": bc_type,
    }
    return conf

if __name__ == "__main__":
    if len(sys.argv) != 9:
        print("Usage: python script.py <IPs_file> <base_port> <n> <t> <repetitions> <scheme> <bc_type> <exp_index>")
        sys.exit(1)

    IPs_file = sys.argv[1]
    base_port = int(sys.argv[2])
    n = int(sys.argv[3])
    t = int(sys.argv[4])
    repetitions = int(sys.argv[5])
    scheme = sys.argv[6]
    bc_type = sys.argv[7]
    exp_index = sys.argv[8]

    # Read IPs from file
    with open(IPs_file, "r") as ips_file:
        IPs = json.loads(ips_file.read())  # Using eval to interpret the file content as a Python list

    # No flow or 1 flow define assume localhost
    if len(IPs) <= 1:
        IPs = ["127.0.0.1"]* n
    # if supervisor is on the same node a participation node, the first item 
    if len(IPs) == n:
        IPs = [IPs[0]] + IPs

    config = getConfigs(IPs, base_port, n, t, repetitions, scheme, bc_type)

    with open("config.yaml", "w") as configFile:
        yaml.dump(config, configFile, default_flow_style=False)

    if int(exp_index) == 0:
        shutil.rmtree("/root/keys", ignore_errors=True)

        os.mkdir("/root/keys")
        genKeys = Popen(["/root/rust-impl", "gen-keys"], shell=False)
        genKeys.wait()

    print("Config file & keys generated successfully.")


# supervisor_ip: 172.16.11.1:2000
# peers: 
# - "172.16.11.1:2000"
# - "172.16.11.1:2001"
# - "172.16.12.1:2002"
# - "172.16.13.1:2003"

# with open("config.yaml") as configFile:
#     config= yaml.safe_load(configFile)

#     shutil.rmtree("keys", ignore_errors=True)

#     os.mkdir("keys")
#     genKeys = Popen(["./target/release/rust-impl", "gen-keys"], shell=False)
#     genKeys.wait()

#     numPlayers = int(config["num_players"])