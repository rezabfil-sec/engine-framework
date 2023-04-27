#!/usr/bin/python3

import json
import sys
import argparse

sys.path.append("scripts") # path on simulation node
sys.path.append("../../../scripts") # path on management node
import process_variables as pv

def parse_cli(args):
    """Parse command line arguments """
    parser = argparse.ArgumentParser(prog='pm', description='Process mappings')
    parser.add_argument('-f', '--flows', help='Json file with flows')
    parser.add_argument('-t', '--tsn', help='Json file with tsn')
    return parser.parse_args(args)

def main():
    parser_args = parse_cli(sys.argv[1:])
    flows_file = parser_args.flows
    tsn_file = parser_args.tsn

    with open(flows_file, 'r') as f:
        flows = json.load(f)
    with open(tsn_file, 'r') as f:
        tsn = json.load(f)

    node_to_flow_to_interfaces_mapping = pv.map_node_to_flow_to_interfaces(flows)
    node_to_interface_to_tsn_mapping = pv.map_node_to_interface_to_tsn(tsn)

    print(node_to_interface_to_tsn_mapping)
    print(node_to_flow_to_interfaces_mapping)

if __name__ == "__main__":
    main()
