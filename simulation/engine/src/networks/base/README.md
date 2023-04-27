This folder contains networks that define basic parameters and modules, independent of the actual testbed nodes and topology.
EngineNetworkBase extends the network TsnNetworkBase contained in the INET framework. TsnNetworkBase extends WiredNetworkBase with optional submodules, which are currently not enabled. WiredNetworkBase extends NetworkBase with an optional submodule macAddressTableConfigurator of type MacAddressTableConfigurator, which is deactivated by setting its typename to the empty string to allow manual configuration for flow specific forwaring. NetworkBase defines a PcapRecorder, a visualization submodule, and a configurator module of default type Ipv4NetworkConfigurator, whose parameter addStaticRoutes is set to false, to avoid interference with the flow specific routes.

# Configuration

While all other submodules defined herein are unused, the NetworkBase's submodule configurator of type Ipv4NetworkConfigurator can be used to set up the flow specific IP addresses for the node interfaces.
