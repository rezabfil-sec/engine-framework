#!/usr/bin/env python3
import json
import sys


def get_client_node(stack_services, node_mapping):
    """
    Get the client node in a threshold scheme
    :param stack_services: application services configured using stacks.yml
    :param node_mapping: mapping of pseudonym to physical node name
    :return: client node name
    """
    for node in stack_services.keys():
        services = stack_services[node]
        for service in services:
            if 'role' in service.keys() and service['role'] == 'signclient':
                client_node = node_mapping[node]
    return client_node


if __name__ == '__main__':
    stack_services = json.loads(sys.argv[1])

    node_mapping = json.loads(sys.argv[2])

    print(json.dumps(get_client_node(stack_services, node_mapping)))
