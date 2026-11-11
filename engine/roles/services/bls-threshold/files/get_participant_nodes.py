#!/usr/bin/env python3
import json
import sys


def get_part_nodes(stack_services, node_mapping):
    """
    Get a list of nodes participating in a threshold scheme
    :param stack_services: application services configured using stacks.yml
    :param node_mapping: mapping of pseudonym to physical node name
    :return: list of participating nodes
    """
    part_nodes = []
    for node in stack_services.keys():
        services = stack_services[node]
        for service in services:
            if 'role' in service.keys() and service['role'] == 'participant':
                part_nodes.append(node_mapping[node])
    return part_nodes


if __name__ == '__main__':
    stack_services = json.loads(sys.argv[1])

    node_mapping = json.loads(sys.argv[2])

    print(json.dumps(get_part_nodes(stack_services, node_mapping)))