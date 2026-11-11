#!/usr/bin/python3

# Reusably processes variables by calculating additional parameters based on
# existing parameters from scenario variable files.

def map_node_to_flow_to_interfaces(flows):
    network_config = "ovs"
    node_to_flow_to_interface_mapping = {}
    for flows_key, flows_value in flows.items():
        print(flows_value)
        if "subnet-" in flows_value:
            if "." in flows_value:
                network_config = "sriov"
                # Format of the sriov: subnet-1;:node-1:1.1,1.1:node-3:
                flows_value = flows_value.split(';')[1]
                #Outcome - :node-1:1.1,1.1:node-3:
                flow_nodes = flows_value.split(',')
                print(flow_nodes)
                print("SR-IOV network config")
            else:
                # Format of the physical: subnet-1;:node-1:1,1:node-3:
                network_config = "physical"
                flows_value = flows_value.split(';')[1]
                #Outcome - :node-1:1,1:node-3:
                flow_nodes = flows_value.split(',')
                #Outcome - [":node-1:1", "1:node-3:"]
                print(flow_nodes)
                print("Physical network config")
        else:
            # Format of the ovs: :node-1:1,1:node-3:
            network_config = "ovs"
            flow_nodes = flows_value.split(',')

        for flow_node in flow_nodes:
            print(flow_node)
            iface_in, node_name, iface_out = flow_node.split(':')
            if not node_name in node_to_flow_to_interface_mapping.keys():
                node_to_flow_to_interface_mapping[node_name] = {}
            node_to_flow_to_interface_mapping[node_name][flows_key] = []
            if iface_in:
                node_to_flow_to_interface_mapping[node_name][flows_key].append(iface_in)
            if iface_out:
                node_to_flow_to_interface_mapping[node_name][flows_key].append(iface_out) 
    return node_to_flow_to_interface_mapping, network_config

def map_node_to_interface_to_qdisc(qdisc):
    node_to_interface_to_qdics_mapping = {}
    for qdisc_key, qdisc_value in qdisc.items():
        for node_interfaces_string in qdisc_value:
            if ':' in node_interfaces_string:
                node, interfaces_string = node_interfaces_string.split(':')
                if not node in node_to_interface_to_qdics_mapping.keys():
                    node_to_interface_to_qdics_mapping[node] = {}
                interfaces = interfaces_string.split(',')
                for interface in interfaces:
                    node_to_interface_to_qdics_mapping[node][interface] = qdisc_key
            else:
                node = node_interfaces_string
                if not node in node_to_interface_to_qdics_mapping.keys():
                    node_to_interface_to_qdics_mapping[node] = {}
                node_to_interface_to_qdics_mapping[node][0] = qdisc_key
    return node_to_interface_to_qdics_mapping
