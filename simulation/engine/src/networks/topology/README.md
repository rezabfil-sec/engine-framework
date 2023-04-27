These networks extend networks in [nodes](../nodes) with the relevant connections realizing the actual wiring of nodes. For each link, a channel connects the relevant interfaces, using a channel type defined in EngineLink to set the respective bandwitdth. Since the node submodules may be optional, links are conditional based on the existence of both end point submodules.

# Configuration

These networks require no specific configuration.

# Defining new networks

Since the scenario configuration variable files facilitate to select the subset of testbed nodes required for an experiment, node specific submodules in the base networks may be optional. If this is the case, connections should be defined conditional based on the existence of both submodules that are end points of the link. [EngineLink.ned](../../node/EngineLink.ned) defines channels that can be used to realize the different link types for the connections. Available channels currently include EngineLink, which sets a fixed cable length of 1.5m, EngineLink1_0G, and EngineLink10_0G that additionally set the datarate to the respective value. If different prameters are required, new channels may be added to EngineLink.ned, or EthernetLink may be extended directly with implicit channel types in the network files.

## Network auto-generation

These network might be auto generated for a topology defined in [topologies](../../../../../engine/scenarios/topologies) via the script [generate_topo.py](../../../../../engine/roles/generate_config/files/generate_topo.py), using the template [topo.j2](../../../../../engine/roles/generate_config//templates/topo.j2). Additional information for auto generation is taken from the [host_vars](../../../../../engine/engine/host_vars) files.
