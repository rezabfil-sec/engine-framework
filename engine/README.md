## EnGINE Framework Brief Overview

The experiment campaigns are managed in four steps:

[ install ] --> [ setup ] --> [ scenario ] --> [ process ]

*  install: install nodes with a image and prepare them to be available for experiments
*  setup: do some generic setup tasks (install non included packages, etc.) so that nodes have all dependencies required for experiments
*  scenario: run an experiment campaign -> multiple experiments around one topic
*  process: do post-processing for a single experiment or over multiple experiments

For every step there is a playbook to execute it.
All playbooks require one extra parameter that needs to be specified when executing the playbook: "pgroup" is the host group  here all the commands should be applied to. The pgroup name points to a group inside the hosts file.

### Playbook Execution
#### Original
Playbooks are executed from the command line in the top-level inside the repository folder. The folder needs to be on a testbed management node in order to execute the "install" step / playbook.

* Run install:  `ansible-playbook plays/install.yml -e pgroup=nodes`
* Run setup:    `ansible-playbook plays/setup.yml -e pgroup=nodes`
* Run scenario: `ansible-playbook plays/scenario.yml -e scene=<scenario-name>`
* Run post-processing: `ansible-playbook plays/process.yml -e scene=<scenario-name> -e scene_folder=<absolute-path-to-folder-with-scenario-results>`
* Run all steps:`ansible-playbook plays/all.yml -e scene=<scenario-name>`

#### Extended by OMNeT++ Simulator

You can try the custom OMNeT++ [project](../simulation/engine) standalone. See [README](../simulation/README) for the required OMNeT++ and INET framework versions.

The translation scripts and templates that generate an INI-file based on an EnGINE scenario definition via YAML files can be found in the Ansible role [generate_ini](roles/generate_ini). In subfolder [files](roles/generate_ini/files), run `./generate_ini.py -o <scenario-name>.ini -m mac <scenario-name>`.

The playbook for running the simulation requires that appropriate versions of OMNeT++ and the INET framework, as well as the custom simulation project are installed at certain locations (see [README](../simulation/README)). We use a [playbook](plays/sim_setup.yml) that does this installation (plus installation of any dependencies) from scratch at a selectable testbed node. See the playbook for details.
* Run setup:    `ansible-playbook plays/sim_setup.yml -e simulation_node=<node-name>`

Once everything is setup, the actual simulation can be run by passing the respective scenario.
* Run scenario: `ansible-playbook plays/sim_scenario.yml -e simulation_node=<node-name> -e scene=<scenario-name>`

Processing of the (simulation) result files can be done manually via the script [process.py](roles/process/files/process.py)
* Run result processing script: `./process.py -d ../../plays -f <folder-with-scenario-results> <scenario-name> -c -p -s`
  * The `-s` flag is required for the results produced by the simulation playbooks. Without this flag the scripts can also be used to process results produced by the original engine playbooks.
