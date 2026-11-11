# Util script file to help create network.yml, stack.yml and experiments.yml for high number of nodes
# Currently useful for BLS and Schnorr as it assumes specific details
import argparse

TAB = "  "

def print_bls_network(n, t, netid, client, subnet, tsn):
    net_name = "{t}net-{}:\n".format(str(netid),t=TAB)

    if tsn:
        qdisc = "{t}{t}qdisc:\n".format(t=TAB)
        qdisc += "{t}{t}{t}qdisc-1: [ \"node-{}:1\" ]\n".format(client, t=TAB)
        qdisc += "{t}{t}{t}qdisc-2: [ \"node-{}:1\" ]\n".format(n, t=TAB)
        peers = ["\"node-{}:1\"".format(i) for i in range(1,n)]
        qdisc += "{t}{t}{t}qdisc-3: [ {} ]\n".format(", ".join(peers), t=TAB)
    else:
        qdisc = "{t}{t}qdisc: {{}}\n".format(t=TAB)

    prefix = qdisc + "{t}{t}iconfig: {{}}\n{t}{t}ifaceconfigs: {{}}\n{t}{t}flows:\n".format(t=TAB)

    flow_count = 1
    flows = []
    while flow_count <= n:
        # flow = str(flow_count) + ": '" + subnet + ";:" + client_node + ":1,1:" + peer_node +":'"
        flow = "{}: 'subnet-{};:node-{}:1,1:node-{}:'".format(flow_count, subnet, client, flow_count)
        flows.append(flow)
        flow_count += 1
    if tsn:
        flow = "{}: 'subnet-{};:node-{}:2,2:node-{}:'".format(flow_count, subnet+1, client+1, client+2)
        flows.append(flow)
    suffix = "{t}{t}check: true\n{t}{t}num_net_cores: 0\n{t}{t}nic_irq_rt: false\n\n".format(t=TAB)

    network_str = net_name + prefix

    for flow in flows:
        network_str += "{t}{t}{t}{}\n".format(flow, t=TAB)

    network_str += suffix
    return network_str


def print_bls_stack(n, t, stackid, client, tsn):
    stack_name = "{t}stack-{}:\n".format(str(stackid), t=TAB)
    prefix = "{t}{t}name: 'sign_stack_{}_{}'\n{t}{t}services:\n".format(n,t, t=TAB)

    node_stacks = []
    for node in range(1, n+1):
        node_stacks.append("node-{}:".format(node))
        if node == 1:
            app_setup = "{t}- {{ name: bls, role: setup, level: 0, sync_start: no, service_port: 42000  }}".format(t=TAB)
            node_stacks.append(app_setup)
        if node == n:
            app_part = "{t}- {{ name: bls, role: participant, level: 1, threshold: {}, sync_start: yes, aggregator: yes, agg_port: 41999, phonebook_path: phonebook.txt }}".format(t, t=TAB)
            tsn_part1 = "{t}- {{ name: nftables, level: 0, ports: [ 42000 ], signal: no, priority: 1 }}".format(t=TAB)
            tsn_part2 = "{t}- {{ name: nftables, level: 0, sports: [ 42000, 41999 ], signal: no, priority: 1 }}".format(t=TAB)
        else:
            app_part = "{t}- {{ name: bls, role: participant, level: 1, threshold: {}, sync_start: yes }}".format(t, t=TAB)
            tsn_part1 = "{t}- {{ name: nftables, level: 0, ports: [ 42000 ], signal: no, priority: 1 }}".format(t=TAB)
            tsn_part2 = "{t}- {{ name: nftables, level: 0, sports: [ 42000 ], signal: no, priority: 1 }}".format(t=TAB)
        node_stacks.append(app_part)
        if tsn:
            node_stacks.append(tsn_part1)
            node_stacks.append(tsn_part2)

    node_stacks.append("node-{}:".format(client))
    operation = "tsn" if tsn else "sign"
    node_stacks.append("{t}- {{ name: bls, role: signclient, level: 2, agg_port: 41999, iterations: 500, msg_len: 32, file: n{}_t{}_client_{}_l256, phonebook_path: phonebook.txt, signal: yes }}".format(n,t,operation, t=TAB))
    if tsn:
        node_stacks.append("{t}- {{ name: nftables, level: 0, ports: [ 41999, 42000 ], signal: no, priority: 1 }}".format(t=TAB))
        node_stacks.append("{t}- {{ name: nftables, level: 0, sports: [ 41999 ], signal: no, priority: 1 }}".format(t=TAB))

    suffix = "{t}{t}protocols: {{ }}\n\n".format(t=TAB)

    stack_str = stack_name + prefix

    for s in node_stacks:
        stack_str += "{t}{t}{t}{}\n".format(s,t=TAB)

    stack_str += suffix
    return stack_str

def print_bls_exp(max_n, tsn):
    net = stack = 1
    n = 3

    exps = []
    operation = "sign_tsn" if tsn else "sign"
    while n<=max_n:
        t = n-1
        exp = "- {{ network: 'net-{}', stack: 'stack-{}', action: 'action-1'," \
            " signal: true, timeout: 10000, name: '{}_multinode_n_{}_t_{}' }}".format(net, stack, operation, n, t)
        n += 1
        net += 1
        stack += 1
        exps.append(exp)

    exp_str = ""

    for e in exps:
        exp_str += "{t}{}\n".format(e, t=TAB)

    return exp_str

def print_schnorr_network(n, t, netid, client, subnet, tsn):
    net_name = "{t}net-{}:\n".format(str(netid),t=TAB)

    if tsn:
        qdisc = "{t}{t}qdisc:\n".format(t=TAB)
        qdisc += "{t}{t}{t}qdisc-1: [ \"node-{}:1\" ]\n".format(client, t=TAB)
        qdisc += "{t}{t}{t}qdisc-2: [ \"node-{}:1\" ]\n".format(1, t=TAB)
        peers = ["\"node-{}:1\"".format(i) for i in range(2,n+1)]
        qdisc += "{t}{t}{t}qdisc-3: [ {} ]\n".format(", ".join(peers), t=TAB)
    else:
        qdisc = "{t}{t}qdisc: {{}}\n".format(t=TAB)

    prefix = qdisc + "{t}{t}iconfig: {{}}\n{t}{t}ifaceconfigs: {{}}\n{t}{t}flows:\n".format(t=TAB)

    flow_count = 1
    flows = []
    for flow_count in range(1,n):
        # flow = str(flow_count) + ": '" + subnet + ";:" + client_node + ":1,1:" + peer_node +":'"
        flow = "{}: 'subnet-{};:node-{}:1,1:node-{}:'".format(flow_count, subnet, 1, flow_count+1)
        flows.append(flow)
    flow = "{}: 'subnet-{};:node-{}:1,1:node-{}:'".format(flow_count+1, subnet, 1, client)
    flows.append(flow)
    if tsn:
        flow = "{}: 'subnet-{};:node-{}:2,2:node-{}:'".format(flow_count+2, subnet+1, client+1, client+2)
        flows.append(flow)
    suffix = "{t}{t}check: true\n{t}{t}num_net_cores: 0\n{t}{t}nic_irq_rt: false\n\n".format(t=TAB)

    network_str = net_name + prefix

    for flow in flows:
        network_str += "{t}{t}{t}{}\n".format(flow, t=TAB)

    network_str += suffix
    return network_str

def print_schnorr_stack(n, t, stackid, client, tsn):
    stack_name = "{t}stack-{}:\n".format(str(stackid), t=TAB)
    prefix = "{t}{t}name: 'sign_stack_{}_{}'\n{t}{t}services:\n".format(n,t, t=TAB)

    node_stacks = []
    for node in range(1, n+1):
        node_stacks.append("node-{}:".format(node))
        if node == 1:
            flows = [str(f) for f in range(1, n)]
            app_setup = "{t}- {{ name: schnorr-threshold, role: setup, number_nodes: {}, single_thread: yes, source_node: [1], flows: [{}], level: 0, sync_start: no  }}".format(n, ", ".join(flows),t=TAB)
            node_stacks.append(app_setup)

        app_part = "{t}- {{ name: schnorr-threshold, role: participant, id: {}, number_nodes: {}, level: 1, sync_start: yes, use_core: {} }}".format(node, n, node+1, t=TAB)
        tsn_part1 = "{t}- {{ name: nftables, level: 3, ip_range_from: part{}, ip_range_to: client, signal: no, priority: 1 }}".format(1, t=TAB)
        node_stacks.append(app_part)
        if tsn:
            node_stacks.append(tsn_part1)

    node_stacks.append("node-{}:".format(client))
    operation = "tsn" if tsn else "sign"
    node_stacks.append("{t}- {{ name: schnorr-threshold, role: client, number_nodes: {}, iterations: 500, threshold: {}, test_mode: sign, msg_len: 32, level: 4, file: n{}_t{}_client_{}_l32, group: [1], signal: yes }}".format(n, n-1, n, n-1, operation, t=TAB))
    if tsn:
        node_stacks.append("{t}- {{ name: nftables, level: 3, ip_range_from: part{}, ip_range_to: client, signal: no, priority: 1 }}".format(1, t=TAB))

    suffix = "{t}{t}protocols: {{ }}\n\n".format(t=TAB)

    stack_str = stack_name + prefix

    for s in node_stacks:
        stack_str += "{t}{t}{t}{}\n".format(s,t=TAB)

    stack_str += suffix
    return stack_str

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot results of benchmarks")
    parser.add_argument('-f', '--file', dest='file_type', help='output file type.', required=True)
    parser.add_argument('-t', '--tss', dest='tss', help='threshold scheme', required=True)
    parser.add_argument("-n", "--nodes", dest='nodes', help='total nodes.', required=False)
    parser.add_argument("-c", "--client", dest='client', help='client node.', required=False)
    parser.add_argument("-s", "--subnet", dest='subnet', help='subnet', required=False)
    parser.add_argument("-tsn", "--tsn", dest='tsn', help='tsn sonfigured', required=False, action="store_true")

    args = parser.parse_args()
    ftype = args.file_type
    tss = args.tss
    total_n = int(args.nodes)
    client = int(args.client)
    subnet = int(args.subnet)
    tsn = args.tsn

    if ftype == "network" or ftype == "exp":
        net_file = open("network.yml", "w")
        net_file.write("---\nnetwork:\n")

        net_id = 1
        for n in range(3,total_n+1):
            t = n-1
            if tss == "bls":
                network_str = print_bls_network(n, t, net_id, client, subnet, tsn)
            elif tss == "schnorr":
                network_str = print_schnorr_network(n, t, net_id, client, subnet, tsn)
            net_file.write(network_str)
            net_id += 1

        # Add qdiscconfig manually if tsn required

    if ftype == "stack" or ftype == "exp":
        st_file = open("stacks.yml", "w")
        st_file.write("---\nstacks:\n")

        st_id = 1
        for n in range(3,total_n+1):
            t = n-1
            if tss == "bls":
                stack_str = print_bls_stack(n, t, st_id, client, tsn)
            if tss == "schnorr":
                stack_str = print_schnorr_stack(n, t, st_id, client, tsn)
            st_file.write(stack_str)
            st_id += 1

    if ftype == "exp":
        exp_file = open("experiments.yml", "w")
        exp_file.write("---\nexperiments:\n")

        exp_str = print_bls_exp(total_n, tsn)
        exp_file.write(exp_str)

