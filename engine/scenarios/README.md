# Overview of scenarios
Most of the work shall be done in this directory.
You can define your own directory which contains the required files - 00-nodes.yml, 01-network.yml, 02-stacks.yml, 03-actions.yml, 04-experiment.yml.

Depending on what experiments you want to do, we created several families of scenarios.

In case some parts are missing, reach out to your advisors and discuss the next steps.

# Creating a Scenario

In order to create a scenario, 5 files have to be specified:

- **00-nodes.yml**: Node specific configuration. E.g. which nodes to use, mapping of containers to nodes and other node specific configuration parameters
- **01-network.yml**: Network configuration. E.g. flows between nodes and qdisc configuration. Allows for several network setups.
- **02-stacks.yml**: Which services to run on which nodes. Services have individual configuration parameters. Allows for several stacks.
- **03-actions.yml**: Which actions should be performed during the experiment. E.g. injecting faults. Allows for several sets of actions.
- **04-experiments.yml**: Specifies the actual experiment runs. Ties together network, stacks and actions.

A minimal scenario has to specify which nodes to use, one network topology and one stack. Actions are optional
and can be regarded as a more advanced feature used to simulate specific events.
The following subsections contain a more detailed description of the configuration options in the different files.

## 00-nodes.yml

The nodes files specifies the nodes of the experiment. Nodes can either be physical testbed nodes, or LXC
containers being hosted by a physical nodes. This section discussed the different parts of the file

### Physical Nodes

The core of the file is the specification of the testbed nodes to use in the experiment. The first step is to 
specify the list of nodes to be used. This can be done using the **nodes** parameter:

    nodes:
    - idex
    - zone
    - yieldly

In this example, the testbed nodes idex, zone and yieldly will be used. EnGINE will automatically create
calendar events in the coinbase calendar, allocate the nodes, set the images and start them.
The next mandatory step is to define a node mapping using **node_mapping**. The idea of the node mapping is to 
introduce pseudonyms for the experiment nodes. Those node names can then be used in the other configuration
files (e.g. when defining flows between nodes in 01-network.yml). That way, the actual physical nodes (or
containers) can be changed without having to change all the other files. An example node mapping may look like
this:

    node_mapping:
      node-1: idex
      node-2: zone
      node-3: yieldly

Note that you can use any names on the left side of the mapping, so more meaningful names can be used. In the
remaining scenario files, the nodes can be referred to as *node-1*, *node-2* and *node-3*.

### Containers

Besides physical nodes, the experiment setup can also contain nodes that are LXC containers. LXC containers are
hosted by a physical node. They behave like light-weight virtual machines and logically behave in the same
way as physical nodes. Hence, it should be possible to replace physical nodes by containers an vice versa.
It is even possible to use the physical container host as one of the experiment nodes. Note that this is
probably not what you want, since containers and the physical host share resources. Containers can be specified
using the **containers** parameter:

    containers:
      idex:
      - { name: container1, ifaces: [6.0, 5], ssh_port: 10022, lxc_config: ["lxc.cgroup2.cpuset.cpus = 1-2"] }
      - { name: container2, ifaces: [6.1], ssh_port:10023 }
      yieldly:
      - name: container3
        ifaces: [6.2]
        ssh_port: 10022
        lxc_config: ["lxc.cgroup2.cpuset.cpus = 1-16"]

In the example, three containers (*container1*, *container2*, *container3*) will be created on the physical
hosts idex (*container1* and *container2*) and yieldly (*container3*). The example shows both yaml syntax
options that can used (`{ name: ... }` vs `name: ...`). The containers specification requires the following 
configuration parameters:

- `name`: Name of the container. Can be used in the same way as tesbed node names (e.g. yieldly).
- `ifaces`: Interfaces that should be **moved** from the physical host to the container. Note that the
interface will not be visible anymore on the physical host. E.g. using the interface 5 on idex in
01-network.yml will result in an error. Interfaces with a dot (e.g. `6.1`) are **SR-IOV** interfaces (actually
called SR-IOV virtual function (VF)). SR-IOV interfaces are preferred for containers, since they allow multiple
containers to efficiently share physical host interface (e.g. the one connected to the test switch).  
- `ssh_port`: More of a technicality. Specifies the port on the physical host that will be forwarded to the
containers ssh port. This is required for Ansible to executed commands in the container. Make sure to assingn
unique (on physical host level) ports. Other than that you don't have to think about this parameter.
- `lxc_config:` Allows to pass any lxc config parameters to the container. This can e.g. be used to assign 
CPU cores to the container, or limit its RAM. More information on the available options
[here](#lxc-configuraton).

After defining the container mapping, containers have to be added to the **node mapping** just as physical
nodes. E.g.:

    node_mapping:
      node-1: zone
      node-2: container1
      node-3: container2
      node-4: container3

Note that we have mixed physical nodes (zone) and containers. This a perfectly valid approach.

### Interface Numbers

The interface numbers for physical hosts are static and can be found in the host variable file corresponding to the node in
`engine/host_vars/<Node Name>.yml`. E.g. the interfaces of node idex can be found in
`engine/host_vars/idex.yml`. The files contain a mapping from interface numbers to the actual interface names and
additional interface properties.

For containers, the numbering follows the order of the interfaces in the list passed to  `ifaces`. E.g.

    - { name: some_container, ifaces: [1.1, 3, 2.1] }, .... }

will results in container interfaces 1, 2 and 3, where e.g. container interface 1 is (or was) the host interface 1.1.

### Using Pre-Defined Topology

It is also possible to import node and container specifications from pre-defined topology files. The files
can be found in `./topologies`. Using a topology can be set via the `topology` parameter. E.g.:

    topology: "topo-01"

This use the node specification in `./topologies/topo-01.yml`. If you don't want to use a pre-defined topology
set topology to `""`:

    topology: ""

If topology is set, `nodes`, `containers` and `node_mapping` **will be ignored**.

### Additional Configuration Parameters

The file should also contain the following additional configuration parameters:

- `use_low_latency_kernel`: Either `yes` or `no` (default `yes`). Specifies whether the low latency kernel
should be used.
- `num_isolated_cores`: `0` - `number of CPU cores` (default 0). Specifies which cores should be isolated. If
set to `0`, no core will be isolated. 
- `processing_node`: `name of node` (default `"localhost"`). Which physical testbed node to perform
post-processing of experiment artifacts on. If set to `"localhost"`, the management host will be used.
- `parse_pcap_on_nodes`: `yes` or `no` (default `no`). Specifies if pcaps should be converted to csv on
experiment nodes before being sent to a single host.
- `auto_tcpdump_collection`: `yes` or `no` (default `no`). Creates tcpdump services for iperf server/clients
and send_udp source/sinks. For send_upd, you need to add a extra redundant send_udp service to the node at the 
end of the flow with role, sink, flow and port defined. You can add `tcpdump: off` to a iperf/sendudp service
to disable auto tcpdump collection for that specific service (more details about services
[here](#02-stacks.yml)).
- `probe_tcpdumps`: `yes` or `no` (default `no`). Whether to start probe tcpdumps. 

    > Note: This does not work in LXC container yet`

- `network_config`: `Physical`, `SRIOV` or `OvS`. If set to `SRIOV`, SR-IOV VFs are created on capable interfaces.
If `OvS` is selected then hops in flows in `01-network.yml` are used as virtual switches without IP (only forward traffic).
Those can then be used via `<Interface Number>.<VF Number>`. E.g. VF 0 on interface 5 can be addressed via
`5.0`.
- `ptp_clockmode`: `switch_mode` or `linuxptp` (default `linuxptp`). Selects ptp switch mode.
- `debug_mode`: `yes` or `no`. Introduces debug pauses in `engine/roles/experiment/tasks/run_experiment.yml`. Currently there are three hard-coded points.

### LXC Configuration

A detailed list of lxc configuration options can be found
[here](https://linuxcontainers.org/lxc/manpages/man5/lxc.container.conf.5.html).
The most important ones are assingn CPU cores to the container. E.g. :

    lxc.cgroup2.cpuset.cpus = 1, 3, 10-15

The example assigns the cores 1, 3 and all cores from 10 to 15 (including) to the container. Note that the
cores will not be visible (e.g. via `lscpu`) on the physical host anymore. Therefore, it can be made sure
that the container does not share the cores with other containers or the physical host. 
Another important use-case is to limit the RAM of the container:


## 01-network.yml

This file contains the network setup of the experiment. The core building block of the network configuration are **flows**, 
where each flow represents a connection from a sink to a source node, potentially via multiple hops. In addition to that, 
the file contains several tsn-specific configuration options. The following sections describe the network configuration in more
detail.

### Defining a Network

Networks can be defined under the `network` parameter. There can be multiple network configurations that can later be
used for experiments with e.g. different network topologies or tsn configs. The config structure looks llike this:

    network:
      net-1:
        ... 
      net-2:
        ...
      other-network-name:
        ...

Note that there are no restrictions on the network names. A minimal setup requires one network. 
Every network has to define the following options:

- `qdisc`: Applies the corresponding qdisc on node level or per interface. More details  [here](#qdisc-config)
- `flows`: Flow specifications. More details [here](#flows)
- `check`: `yes` or `no` (default `yes`). Checks node connectivity by pinging for all network configs.
- `nic_irq_rt`: `yes` or `no` (default `no`). Should be `yes` if the NIC IRQs will be set to real-time priority in the linux kernel

  >  Note: This currently does not work on machines with more than 8 vCPUs.

### Flows
Flows represent the network topology. Each flow has an index (starting from 1) and is assigned to a subnet. An example flow
specification could look like this:
    
    network:
      net-1:
        qdisc: {}    
        flows:
          1: 'subnet-1;node-1:1,1:node-2'
          2: 'subnet-1;node-2:2,1:-node3'
          3: 'subnet-2;node-4:3,4:node-5:6,2:node-6'

In the example, there are 3 flows belonging to two subnets. The structure of the flow string is 
$$\text{subnet};:\text{source}:\text{iface},(\text{iface}:\text{hop node}:\text{iface})^*,\text{iface}:\text{sink}:$$

While source and sink are always required, hops are ***only supported** when OvS is activated. Note that OvS will **not work** if the
interfaces are connected via a switch. Subnet names can be freely chosen, the node names have to 
be defined in `node_mapping` in `00-nodes.yml`. Engine will automatically assign IP addresses in the corresponding
subnets to the interfaces. Note while a flow has a source and a sink, you can think about it as a bidirectional communication
channel. Hence, if you need any kind of bidirectional connection between two nodes, it usually suffices to only define one
flow, where it does not matter which node is the source and which one the sink. In general, your flows should represent your
network topology, i.e. if you e.g. have a peer-to-peer network, there should be for each link between peers.

### Qdisc Config

Currently, qdisc config is supported, but for most of our use cases it is not really needed so you can leave `qdisc` under `network` and
`qdisconfigs` empty. I.e.:

    network:
      net-1:
        qdisc: {}
        ...
        
    qdiscconfigs: {}

## 02-stacks.yml

Stacks define which services (i.e. programs) should run during your experiment. Services will be started when the experiment
begins and stopped when they are done or when the experiment finishes. As with the network config, you can define multiple
stacks.

### Services

You can find the available services in `engine/role/services`. There are services e.g. for blockchain protocols or for
utility programs like tcpdump. To create a new stack, you should add it under the `stacks` parameter:

    stacks:
      stack-1:
        ...
      stack-2:
        ...
      some-other-stack-name:
        ...

Each stack has to define the following parameters:

- `name`: More descriptive name of the stack. This will  printed in the experiment execution. Has no logical use other than
that.
- `services`: Contains the actual service specifications. More on this in the remainder of the section.
- `protocols`: Can be ignored. May be implemented in the future.

The `services` parameter contains a mapping from nodes (node names from `node_mapping`) to services that should be
started on this nodes. A stack for a minimal Algorand setup (2 participation nodes, 1 relay), could look like this:

    stacks:
      stack-1:
        name: 'Algorand'
        services:
          node-1:
            - { name: algorand-setup, level: 0, type: participation, algos: 100000 }
            - { name: algorand, level: 1, type: participation, relays: [ 1 ], signal: no  }
          node-2:
            - { name: algorand-setup, level: 0, type: participation, algos: 200000 }
            - { name: algorand, level: 1, type: participation, relays: [ 2 ], signal: no }
          node-3:
            - { name: algorand-setup, level: 0, type: relay }
            - { name: algorand, level: 1, type: relay, signal: no }


You can see that the different nodes have different services, depending on their role (relay, participation node). Services have
service specific configuration parameters (e.g. `type: participation`,  `algos: 100000` or `relays: [1]` ) and meta
configuration parameters, available to any service. Those meta options are:

- `name`: Which service. Service names are can be found in `engine/roles/services` (directory names).
- `level`: Number starting from 0. The service level is useful if some service needs to be started before another one, e.g. if
there are dependencies between services. EnGINE will start services level by level. In the example, the algorand-setup 
service needs to be executed on every node before the algorand service can be started, hence it has service level 0 while
the algorand service has service level 1.
- `signal`: `yes` or `no`. Used for services that are expected to terminate gracefully. Used for **signal mode** in `04-experiments.yml`,
which allows to finish experiment once all services are finished. Have a look [here](#04-experiments).

## 03-actions.yml

Can be used to specify actions. While services represent the actual software stack of the nodes in experiment (e.g.
blockchain nodes), actions are used to implement artificial events (e.g. load spikes, node failures, ...). Hence, they can 
simulate different events over the timespan of the experiment. As with network and stack, you can define multiple sets of 
actions.

## 04-experiments

The experiments file defines the actual experiment runs and ties together network setups, stacks and actions. Experiments
can either be run in **time mode**  or **signal mode**. In time mode, the experiment runs for a certain time (in seconds)
and is then stopped. The signal mode waits for services to be finished (e.g. after sending a pre-defined number of packets). 
Service indicate that they are finished by sending a success signal. In both modes, the experiment is immediately stopped
when receiving an error signal. 

In order to define an experiment, a list of experiment runs has to be defined under the `experiments parameter`, e.g.:

    experimens:
      - { network: 'net-1', stack: 'stack-1', actions: 'actions-1', time: 10, name: 'name_of_experiment_1' }
      - { network: 'net-2', stack: 'stack-2', actions: 'actions-2', time: 200, name: 'name_of_experiment_2' }

The `network`, `stack` and `actions` options specify the network, stack and action, respectively. The `time`  option
is used for time mode and requires the time in seconds. The `name` of the experiment can be freely chosen and should be
descriptive since it will appear in the artifacts produced by the experiment run. 

### Using Signal Mode

Signal mode is not activated by any flag in `04-experiment.yml`, but rather automatically used if any service has set 
`signal: yes`. An example where this is useful is a blockchain experiment where clients generate a fixed amount of transactions




          
