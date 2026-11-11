#!/usr/bin/python3

import json
import sys

compute_instance_dict = json.loads(sys.argv[1])

modified_network_interfaces = []

for entry in compute_instance_dict['networkInterfaces']:
    modified_network_interfaces.append({
        'accessConfigs': [{
            'name': "External NAT",
            'networkTier': "PREMIUM",
            'type': "ONE_TO_ONE_NAT",
        }],
        'network': entry['network']['selfLink'],
        'subnetwork': entry['subnetwork']['selfLink'],
    })
    
compute_instance_dict['networkInterfaces'] = modified_network_interfaces

print(json.dumps(compute_instance_dict))