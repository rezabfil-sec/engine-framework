#!/usr/bin/python3

import json
import sys

containers = json.loads(sys.argv[1])
node_mapping = json.loads(sys.argv[2])

def obtain_containers(containers, node_mapping):
    container_names = {}
    node_mapping = {y: x for x, y in node_mapping.items()}
    for host, conts in containers.items():
        for cont in conts:
            container_names[cont['name']] = node_mapping[cont['name']]

    return container_names

print(obtain_containers(containers, node_mapping))

# def obtain_containers(containers):
#     container_names = []
#     for host, conts in containers.items():
#         for cont in conts:
#             container_names.append(cont['name'])

#     return container_names

# print(obtain_containers(containers))