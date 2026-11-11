# BLS
Distributed signature value computation system that offers services (DKG, signing)
built on underlying TCP stack and Noise protocol.

The used signature scheme is a threshold signature scheme BLS (paper, implementation.)

## Content
- tasks/ and defaults/ are standard as in other services
- files/bls-codebase - library of the modified BLS library
- files/multi-party-bls - library implementing threshold BLS developed by ZenGo-X
- files/genhostfile.py - setup script that creates host ip list of peers participating in threshold scheme
- files/get_agg_node.py - returns name of aggregator node
- files/get_client_node.py - returns name of client node
- files/get_participants_node.py - returns list of names of participant nodes
- files/yml_gen_util.py - script to create network.yml, stacks.yml and experiments.yml for large BLS and Schnorr experiments

## Usage
The service is used in the following scenarios
- bls-demo
- bls-sign-lxc32-baseline - runs BLS sign on up to 32 LXC containers
- bls-sign-lxc21-baseline - runs BLS sign on up to 21 LXC containers 
- bls-sign-lxc21-tsn - runs BLS sign with TSN on up to 21 LXC containers

Check the 02-stacks.yml and 04-experiments.yml in the scenario for more information on how to configure and use the service.