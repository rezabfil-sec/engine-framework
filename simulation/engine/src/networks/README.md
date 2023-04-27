This folder contains network module definitions that realize the testbed. The definition of a network that can be used for simulations is split into a inheritance hierarchy of three modules. 
The folder [base](base) contains a network module that sets the base modules and parameters values for simulation, independent of the actual nodes and topology. The network modules in folder [node](node) extend this base network by defining submodules and parameters for the actual testbed nodes and their individual properties. The network module in folder [topology](topology) extend the networks defining nodes with connections to realize the actual wiring.

# Configuration

To use a network in a simulation, a network in folder [topology](topology) has to be included via the network parameter in the .ini file. The individual submodules can then be accessed via the network's name.

# Defining new networks

The three level hierarchy mimics the structure of engine, and facilitates simpler maintinability as well as auto generation of configuration files. Since the connections depend on the actual wiring, which might be subject to frequent change, a separate network file allows to easily adapt the network connections to a different topology. Since hardware nodes and their basic configuration might also be added, removed, modified, a separate network file allows to adapt for a different setup. Purpose of the single network in [base](base) is to make general definitions that are relevant for the simulation in general for which a single network file should suffice.
