# schnorr-frost
Distributed signature value computation system that offers services (DKG, preprocessing, signing)
through an HTTP interface.

The used signature scheme is a threshold signature scheme FROST (paper, implementation.)

## Content
- tasks/ and defaults/ are standard as in other services
- files/frost-borg - library of the modified frost-dalek library
- files/tres - default sources for the benchmark tool (bench) and integration of additional results
- files/create_cfg.py - setup script that create corresponding flow to create the paths for each node

## Usage
The service is used in tss-schnorr scenario and tss-schnorr-lxc.
Check the 02-stacks.yml and 04-experiments.yml in the scenario for more information on how to configure and use the service.