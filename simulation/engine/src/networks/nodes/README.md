These networks extend EngineNetworkBase with submodules realizing the individual testbed nodes.
EngineNetworkNodes sets for each node a respective submodule hostname of type EngineNode that specifies the node specific paramters, i.e. the mac addresses and type (which in turn results in the correct number and bandwidth of interfaces being set) of a node, as defined in the respective host_vars files. These submodules are conditional based on a respective paramter hasHostname, which is set to false by default.

# Configuration

To use a testbed node for a simulation, the respective variable hasHostname has to be set to true. Node specific setup can then be applied by referencing the respective submodule via its hostname.

# Definition of new networks

Excluding unused testbed nodes is not strictly necessary for simulations, and its sole purpose is to mimic the selection of relevant testbed node for a scenario in the node variable files. To have submodules with the respective hostnames is however required for the autogeneration based on the scenario configuration files. The type and interface address parameters should be set in accordance to the files in host_vars. If the number and datarates of a node's interfaces differ from the ones currently in use, EngineNode may have to be adapted, e.g. with a different type to implement the correct interfaces.
