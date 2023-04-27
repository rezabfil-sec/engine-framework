#!/usr/bin/python3

import yaml

# Provides access to variable files.
# Opens and loads contents of yaml files, hiding directory structures and actual filenames.
# Provides one function per file.

group_vars_dir = "group_vars"
group_vars_all = "all.yml"
host_vars_dir = "host_vars"
scenarios_dir = "scenarios"
topologies_dir = "topologies"
nodes_file = "00-nodes.yml"
network_file = "01-network.yml"
stacks_file = "02-stacks.yml"
actions_file = "03-actions.yml"
experiments_file = "04-experiments.yml"
experiment_defaults = "roles/experiment/defaults/main.yml"
network_defaults = "roles/network/defaults/main.yml"
services_dir = "roles/services"
service_defaults = "defaults/main.yml"
simulation_defaults = "roles/generate_config/defaults/main.yml"
path_to_engine = "../../.."

def set_path_to_engine(path):
	path_to_engine = path

def open_and_load_yml(file):
	with open(path_to_engine + "/" + file) as f:
		loadedFile = yaml.load(f, Loader=yaml.FullLoader)
	return loadedFile

def load_group_vars_all():
	return open_and_load_yml(group_vars_dir + "/" + group_vars_all)

def load_host_vars(host):
	return open_and_load_yml(host_vars_dir + "/" + host + ".yml")

def load_topology(topology):
	return open_and_load_yml(scenarios_dir + "/" + topologies_dir + "/" + topology + ".yml")

def load_nodes(scene):
	return open_and_load_yml(scenarios_dir + "/" + scene + "/" + nodes_file)

def load_network(scene):
	return open_and_load_yml(scenarios_dir + "/" + scene + "/" + network_file)

def load_stacks(scene):
	return open_and_load_yml(scenarios_dir + "/" + scene + "/" + stacks_file)

def load_actions(scene):
	return open_and_load_yml(scenarios_dir + "/" + scene + "/" + actions_file)

def load_experiments(scene):
	return open_and_load_yml(scenarios_dir + "/" + scene + "/" + experiments_file)

def load_experiment_defaults():
	return open_and_load_yml(experiment_defaults)

def load_network_defaults():
	return open_and_load_yml(network_defaults)

def load_service_defaults(service):
	return open_and_load_yml(services_dir + "/" + service + "/" + service_defaults)

def load_simulation_defaults():
	return open_and_load_yml(simulation_defaults)
