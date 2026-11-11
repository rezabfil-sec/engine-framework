# ECDSA Code

Contains implementations of GG18, GG20 and the new DKR protocol. 
The protocols have been implemented using the multi-party-ecdsa library.

## Dependencies 

In order to build the project, the following dependencies are required:
- python 
- pyyaml
- libgmp
- cargo/ rust

For debian based systems, the install.sh script can be used to install all dependencies. Simply run e.g.:

```shell
bash install.sh
```

## Build and Run

Before executing an experiment, build the project using:
``` shell
cargo build --release
```
The experiment can then be started using the run_experiment.py script. E.g. use the following to write stdout and stderr to out and err, respectively, and to run the experiment as a daemon: 
``` shell
python run_experiment.py > out 2> err &
```

## Configuration

Use the exepriment_conf.yaml file to configure an experiment. Note that when running the experiment, the repo
also contains a file called config.yaml. This is the config generated for the specific setup that is used by
the supervisor and protocol processes.
The file contains the following configuration options:
- *min_players*: Smallest value for n, number - *max_players*: Largest value for n (including), number
- *schemes*: List containing the scheme. Possible values: "GG18" or "GG20". Example to run experiment for both schemes: ["GG18", "GG20"]. When both schemes are selected, the experiment is first conducted for the first
scheme (all setups) and then for the second scheme.
- *bc_type*: Either "BestEffort" for best-effort broadcast, "Echo" for standard echo broadcast or "Optimized" for optimized echo broadcast
- *base_port*: Base port used for addresses of the supervisor (uses base port) and protocol processes (pp with id i base address port + i). All processes listen on localhost. 
- *num_dkg_runs*: Number of DKG runs. Has to be at least 1.
- *num_dkr_runs*: Number of DKR runs. Only for GG20, ignored for GG18. Can be 0.
- *num_sig_runs*: Number of singnature runs. Can be 0.

The threshold is always computed from n (n/2, 2n/3, n).

## Experiment Output

The measurement results of an experiment are written to csv files in the res/ directory. Files are prefixed with the sheme (e.g. gg18) and protocol (e.g. dkg). For each
combination of scheme and protocol (note that for gg20, there is on_sig and off_sig), there are three files:
- *total*: Total execution time
- *round_total*: Total round time
- *round_computation*: Round computation time
The columns in the csv files are t, n, protocol process id, run, time in millis.

## Module Structure

The project contains the following top-level modules:
- *supervisor*: Contains the implementation of the supervisor process.
- *protocol_process*: Contains the implementation of the protocol process. 
- *network*: Contains networking modules.
- *protocol*: Contains the protocol implementations for GG18, GG20 and the DKR protocol.
- *util*: Contains helper modules for crypto, config, key pairs for authentication and measurements.

