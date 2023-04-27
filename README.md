# EnGINE Framework
**En**vironment for **G**eneric **I**n-vehicular **N**etworking **E**xperiments (EnGINE) is highly manageable orchestration tool built in Ansible.
EnGINE a configurable, scalable, flexible, and reproducible setup that operates autonomously (once well configured). It can incorporate various real data sources and recorded footage. Besides, multiple probes can be set up to collect data during the experiment run, such as .pcaps or logs. Such data can be interpreted to provide insights into experiment outcomes. The design allows the reuse of various applications and configurations from different scenarios minimizing the overhead on maintenance. 
The latest extension includes the translation functionality of the scenario configuration to the OMNeT++ configuration, individual playbooks for running the simulation flow, and results post-processing.
Reasoning why EnGINE and OMNeT++ have been selected for a hybrid experimentation platform can be found in the submitted paper that appears at [IFIP 2023](https://networking.ifip.org/2023/).


The repository is structured as follows:
* [engine](engine) - contains the modified codebase of the EnGINE framework, which includes provisions for the simulation capability
* [results](results) - contains the simulation results used for results in the publication
* [simulation](simulation) - contains the installation scripts for OMNeT++ and provisions for given simulations

This repository contains the EnGINE framework and scenarios used within publication titled: Methodology and Infrastructure for TSN-based Reproducible Network Experiments.

This is a supplementary repository of the following list of publications:
* Marcin Bosk, Filip Rezabek, Johannes Abel, Max Helm, Kilian Holzinger, Georg Carle, Jörg Ott: Simulation and Practice: A Hybrid Experimentation Platform for TSN. To appear at the [IFIP 2023](https://networking.ifip.org/2023/)
* Marcin Bosk, Filip Rezabek, Kilian Holzinger, Angela Gonzalez Mariño, Abdoul Aziz Kane, Francesc Fons, Jörg Ott, Georg Carle: Methodology and Infrastructure for TSN-Based Reproducible Network Experiments. IEEE Access 10: 109203-109239 (2022), [PDF: Methodology and Infrastructure - IEEE Access 2022](https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=9910175)
* Filip Rezabek, Marcin Bosk, Thomas Paul, Kilian Holzinger, Sebastian Gallenmüller, Angela Gonzalez Mariño, Abdoul Kane, Francesc Fons, Haigang Zhang, Georg Carle, Jörg Ott: EnGINE: Flexible Research Infrastructure for Reliable and Scalable Time Sensitive Networks. J. Netw. Syst. Manag. 30(4): 74 (2022), [PDF: EnGINE - JNSM 2022](https://link.springer.com/content/pdf/10.1007/s10922-022-09686-0.pdf)
* Filip Rezabek, Marcin Bosk, Thomas Paul, Kilian Holzinger, Sebastian Gallenmüller, Angela Gonzalez Mariño, Abdoul Kane, Francesc Fons, Haigang Zhang, Georg Carle, Jörg Ott: EnGINE: Developing a Flexible Research Infrastructure for Reliable and Scalable Intra-Vehicular TSN Networks. CNSM 2021: 530-536, [PDF: EnGINE - CNSM/HipNET 2021](http://www.net.in.tum.de/fileadmin/bibtex/publications/papers/rezabek_hipnet2021.pdf)
* Marcin Bosk, Filip Rezabek, Kilian Holzinger, Angela Gonzalez Mariño, Abdoul Kane, Francesc Fons, Haigang Zhang, Georg Carle, Jörg Ott: Demo: Environment for Generic In-vehicular Network Experiments - EnGINE. VNC 2021: 117-118, [PDF: Demo - VNC 2021](http://www.net.in.tum.de/fileadmin/bibtex/publications/papers/bosk_vnc2021.pdf)

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

Playbooks are executed from the command line in the top-level inside the repository folder. The folder needs to be on a testbed management node in order to execute the "install" step / playbook.

* Run install:  `ansible-playbook plays/install.yml -e pgroup=nodes`
* Run setup:    `ansible-playbook plays/setup.yml -e pgroup=nodes`
* Run scenario: `ansible-playbook plays/scenario.yml -e scene=<scenario-name>`
* Run post-processing: `ansible-playbook plays/process.yml -e scene=<scenario-name> -e scene_folder=<absolute-path-to-folder-with-scenario-results>`
* Run all steps:`ansible-playbook plays/all.yml -e scene=<scenario-name>`

**Example for post-processing of scenarios:** `ansible-playbook plays/process.yml -vvv -e scene=Figure-9 -e scene_folder=/results/Figure-9`

You can try the custom OMNeT++ [project](../simulation/engine) standalone. See [README](../simulation/README) for the required OMNeT++ and INET framework versions.

The translation scripts and templates that generate an INI-file based on an EnGINE scenario definition via YAML files can be found in the Ansible role [generate_ini](roles/generate_ini). In subfolder [files](roles/generate_ini/files), run `./generate_ini.py -o <scenario-name>.ini -m mac <scenario-name>`.

The playbook for running the simulation requires that appropriate versions of OMNeT++ and the INET framework, as well as the custom simulation project are installed at certain locations (see [README](../simulation/README)). We use a [playbook](plays/sim_setup.yml) that does this installation (plus installation of any dependencies) from scratch at a selectable testbed node. See the playbook for details.
* Run setup:    `ansible-playbook plays/sim_setup.yml -e simulation_node=<node-name>`

Once everything is setup, the actual simulation can be run by passing the respective scenario.
* Run scenario: `ansible-playbook plays/sim_scenario.yml -e simulation_node=<node-name> -e scene=<scenario-name>`

Processing of the (simulation) result files can be done manually via the script [process.py](roles/process/files/process.py)
* Run result processing script: `./process.py -d ../../plays -f <folder-with-scenario-results> <scenario-name> -c -p -s`
  * The `-s` flag is required for the results produced by the simulation playbooks. Without this flag the scripts can also be used to process results produced by the original engine playbooks.

### Limitations of This Repository
To deploy EnGINE in your infrastructure, you need own hardware that is managed from a central management host that has SSH access to the individual nodes. 
If you have such deployments on hand, you can update the `host_vars` directory with your corresponding nodes. 

For our deployments we are using pos [1]. To find out about the architecture navigate to these publications:
* [1] Pos
* [2] EnGINE JNSM 

## Experiments
In the following, the experiments used in publication "Methodology and Infrastructure for TSN-based Reproducible Network Experiments" are listed. Of note, this repository only contains the used configurations contained in the [scenarios](scenarios) folder. The actual results are available here: **[Link to data](https://nextcloud.in.tum.de/index.php/s/sWxadG8JeJss2Sy)**

While this repository contains most of the code of EnGINE framework, without a suitable hardware deployment and adequate configuration of the nodes, it can only be used to evaluate the results of the experiments. This can be achieved using the [process.yml](plays/process.yml) playbook. **As an example for post-processing of scenario Figure-9:** `ansible-playbook plays/process.yml -vvv -e scene=Figure-9 -e scene_folder=/results/Figure-9`

The plots used within the aforementioned publication can be plotted using the [Journal Plotting](scripts/plotting/plot_journal.py) script. **Importantly, you need to specify the [path to your folder](scripts/plotting/plot_journal.py#L665) containing all result artefacts!!!** After doing that, the plotting script can be run by switching to the [plotting](scripts/plotting) folder and running `python3 plot_journal.py`. Note that you need to have all dependecies installed. 

### Plotting Script
To obtain the plots for Figures 4 and 5 of IFIP Publication, you need to first unzip the `results/simulationResults.zip` file and then specify adequate paths in the [plot_paper.py](engine/scripts/plotting/plot_paper.py) script. Please note that you also need to download the results provided with the original EnGINE repository.

We build on top of the EnGINE framework, which cannot be used without a suitable hardware deployment and adequate configuration of the nodes. Nevertheless, it can still be used to evaluate the results of the experiments. This can be achieved using the [process.yml](plays/process.yml) playbook following the similar instructions like for the simulation. To note, you need to download the data provided in the EnGINE repository.

### Available Experiment Campaigns/Scenarios List

| Experiment Identifier | Journal Figure/Table | Brief Experiment Description | Associated Folder | Subexperiment Names |
|---|---|---|---|---|
| EX_SP1 | Figure 12 | 20 minute Iperf3 test showing spikes every 60s | Figure-12_EX_SP1 | 4-queue_2-cbs_2-be_1-streams_2-hop_with-hop-cbs-iperf-line-limit100-20min |
| EX_SP3 | Figure 14 | 2 minute Iperf3 test verifying fixed spikes | Figure-14_EX_SP3 | 4-queue_2-cbs_2-be_1-streams_2-hop_with-hop-cbs-iperf-line-limit100-2min | 
| N/A | Figure 9 | Iperf3 Accuracy - IFS | Figure-9 | 4-queue_2-cbs_2-be_4-streams_1-no-hop-cbs100-iperf100 | 
| N/A | Figure 10 | SendUDP Accuracy - IFS | Figure-10 | 1_hop-etf_100_strict_nooffload_d300_zgw | 
| EX_SP2 | Figure 13 | Spikes ping test | Figure-13_EX_SP2 | pingTest | 
| EX_SO1 | Figure 15a-16a | AO & SMT & powersave | Figure-15a-16a_EX_SO1 | 4-queue_2-cbs_2-be_1-streams_2-hop_with-hop-cbs-iperf-line-limit100-2min-nocpuperf | 
| EX_SO2 | Figure 15b-16b | noAO & noSMT & performance | Figure-15b-16b_EX_SO2 | 4-queue_2-cbs_2-be_1-streams_2-hop_with-hop-cbs-iperf-line-limit100-2min-noturbo-noht-cpuperf | 
| EX_SO3 | Figure 15c-16c | AO & noSMT & performance | Figure-15c-16c_EX_SO3 | 4-queue_2-cbs_2-be_1-streams_2-hop_with-hop-cbs-iperf-line-limit100-2min-cpuperf-noht | 
| EX_SO4 | Figure 15d-16d | AO & SMT & performance | Figure-15d-16d_EX_SO4 | 4-queue_2-cbs_2-be_1-streams_2-hop_with-hop-cbs-iperf-line-limit100-2min-cpuperf | 
| N/A | Figure 17 a,b,c | ETF delta values plots | Figure-17_ETF_Params | 1_hop-etf_25_strict_nooffload_zgw,<br>1_hop-etf_25_strict_offload_zgw,<br>1_hop-etf_50_strict_nooffload_zgw,<br>1_hop-etf_50_strict_offload_zgw,<br>1_hop-etf_75_strict_nooffload_zgw,<br>1_hop-etf_75_strict_offload_zgw,<br>1_hop-etf_100_strict_nooffload_zgw,<br>1_hop-etf_100_strict_offload_zgw,<br>1_hop-etf_125_strict_nooffload_zgw,<br>1_hop-etf_125_strict_offload_zgw,<br>1_hop-etf_150_strict_nooffload_zgw,<br>1_hop-etf_150_strict_offload_zgw,<br>1_hop-etf_175_strict_nooffload_zgw,<br>1_hop-etf_175_strict_offload_zgw,<br>1_hop-etf_200_strict_nooffload_zgw,<br>1_hop-etf_200_strict_offload_zgw,<br>1_hop-etf_225_strict_nooffload_zgw,<br>1_hop-etf_225_strict_offload_zgw,<br>1_hop-etf_250_strict_nooffload_zgw,<br>1_hop-etf_250_strict_offload_zgw,<br>1_hop-etf_275_strict_nooffload_zgw,<br>1_hop-etf_275_strict_offload_zgw,<br>1_hop-etf_300_strict_nooffload_zgw,<br>1_hop-etf_300_strict_offload_zgw |  
| N/A | Figure 18 a,b,c | TAPRIO txtime and ETF delta | Figure-18_TAPRIO_Params | 1to7_hops-taprio_nooffload_180txtime_175delta,<br>1to7_hops-taprio_nooffload_200txtime_175delta,<br>1to7_hops-taprio_nooffload_225txtime_175delta,<br>1to7_hops-taprio_nooffload_250txtime_175delta,<br>1to7_hops-taprio_nooffload_275txtime_175delta,<br>1to7_hops-taprio_nooffload_300txtime_175delta,<br>1to7_hops-taprio_nooffload_300txtime_275delta,<br>1to7_hops-taprio_nooffload_350txtime_175delta,<br>1to7_hops-taprio_nooffload_350txtime_275delta,<br>1to7_hops-taprio_nooffload_400txtime_175delta,<br>1to7_hops-taprio_nooffload_400txtime_275delta,<br>1to7_hops-taprio_nooffload_450txtime_175delta,<br>1to7_hops-taprio_nooffload_450txtime_275delta,<br>1to7_hops-taprio_nooffload_500txtime_175delta,<br>1to7_hops-taprio_nooffload_500txtime_275delta,<br>1to7_hops-taprio_nooffload_550txtime_175delta,<br>1to7_hops-taprio_nooffload_550txtime_275delta,<br>1to7_hops-taprio_offload_180txtime_175delta,<br>1to7_hops-taprio_offload_200txtime_175delta,<br>1to7_hops-taprio_offload_225txtime_175delta,<br>1to7_hops-taprio_offload_250txtime_175delta,<br>1to7_hops-taprio_offload_275txtime_175delta,<br>1to7_hops-taprio_offload_300txtime_175delta,<br>1to7_hops-taprio_offload_300txtime_275delta,<br>1to7_hops-taprio_offload_350txtime_175delta,<br>1to7_hops-taprio_offload_350txtime_275delta,<br>1to7_hops-taprio_offload_400txtime_175delta,<br>1to7_hops-taprio_offload_400txtime_275delta,<br>1to7_hops-taprio_offload_450txtime_175delta,<br>1to7_hops-taprio_offload_450txtime_275delta,<br>1to7_hops-taprio_offload_500txtime_175delta,<br>1to7_hops-taprio_offload_500txtime_275delta,<br>1to7_hops-taprio_offload_550txtime_175delta,<br>1to7_hops-taprio_offload_550txtime_275delta | 
| EX_MQ1 | Table 9 | Mqprio with all 4 flows limited | Table-9_EX_MQ1 | 4-queue_4-be_4-streams_1-hop_all-mqprio-iperf100-90s,<br>4-queue_4-be_4-streams_2-hop_all-mqprio-iperf100-90s,<br>4-queue_4-be_4-streams_3-hop_all-mqprio-iperf100-90s,<br>4-queue_4-be_4-streams_4-hop_all-mqprio-iperf100-90s,<br>4-queue_4-be_4-streams_5-hop_all-mqprio-iperf100-90s,<br>4-queue_4-be_4-streams_6-hop_all-mqprio-iperf100-90s,<br>4-queue_4-be_4-streams_7-hop_all-mqprio-iperf100-90s | 
| EX_MQ2 | Table 10 | Mqprio with 2 limited and two unlimited flows | Table-10_EX_MQ2 | 4-queue_4-be_4-streams_1-hop_all-mqprio-nolimitiperf-45s,<br>4-queue_4-be_4-streams_2-hop_all-mqprio-nolimitiperf-45s,<br>4-queue_4-be_4-streams_3-hop_all-mqprio-nolimitiperf-45s,<br>4-queue_4-be_4-streams_4-hop_all-mqprio-nolimitiperf-45s,<br>4-queue_4-be_4-streams_5-hop_all-mqprio-nolimitiperf-45s,<br>4-queue_4-be_4-streams_6-hop_all-mqprio-nolimitiperf-45s,<br>4-queue_4-be_4-streams_7-hop_all-mqprio-nolimitiperf-45s | 
| EX_CS1 | Figure 22 | Single flow CBS source only | Figure-22_EX_CS1 | 4-queue_2-cbs_2-be_1-streams_1-hop_no-hop-cbs-iperf-line-limit100-2min,<br>4-queue_2-cbs_2-be_1-streams_2-hop_no-hop-cbs-iperf-line-limit100-2min,<br>4-queue_2-cbs_2-be_1-streams_3-hop_no-hop-cbs-iperf-line-limit100-2min,<br>4-queue_2-cbs_2-be_1-streams_4-hop_no-hop-cbs-iperf-line-limit100-2min,<br>4-queue_2-cbs_2-be_1-streams_5-hop_no-hop-cbs-iperf-line-limit100-2min,<br>4-queue_2-cbs_2-be_1-streams_6-hop_no-hop-cbs-iperf-line-limit100-2min,<br>4-queue_2-cbs_2-be_1-streams_7-hop_no-hop-cbs-iperf-line-limit100-2min | 
| EX_CS2 | Figure 22 | Single flow CBS everywhere | Figure-22_EX_CS2 | 4-queue_2-cbs_2-be_1-streams_1-hop_with-hop-cbs-iperf-line-limit100-2min,<br>4-queue_2-cbs_2-be_1-streams_2-hop_with-hop-cbs-iperf-line-limit100-2min,<br>4-queue_2-cbs_2-be_1-streams_3-hop_with-hop-cbs-iperf-line-limit100-2min,<br>4-queue_2-cbs_2-be_1-streams_4-hop_with-hop-cbs-iperf-line-limit100-2min,<br>4-queue_2-cbs_2-be_1-streams_5-hop_with-hop-cbs-iperf-line-limit100-2min,<br>4-queue_2-cbs_2-be_1-streams_6-hop_with-hop-cbs-iperf-line-limit100-2min,<br>4-queue_2-cbs_2-be_1-streams_7-hop_with-hop-cbs-iperf-line-limit100-2min | 
| EX_CM1 | Figure 23-24 | Multi flow CBS source only | Figure-23-24_EX_CM1 | 4-queue_2-cbs_2-be_4-streams_1-hop_no-hop-cbs-iperf-line-limit100-45s,<br>4-queue_2-cbs_2-be_4-streams_2-hop_no-hop-cbs-iperf-line-limit100-45s,<br>4-queue_2-cbs_2-be_4-streams_3-hop_no-hop-cbs-iperf-line-limit100-45s,<br>4-queue_2-cbs_2-be_4-streams_4-hop_no-hop-cbs-iperf-line-limit100-45s,<br>4-queue_2-cbs_2-be_4-streams_5-hop_no-hop-cbs-iperf-line-limit100-45s,<br>4-queue_2-cbs_2-be_4-streams_6-hop_no-hop-cbs-iperf-line-limit100-45s,<br>4-queue_2-cbs_2-be_4-streams_7-hop_no-hop-cbs-iperf-line-limit100-45s | 
| EX_CM2 | Figure 23-24 | Multi flow CBS everywhere | Figure-23-24_EX_CM2 | 4-queue_2-cbs_2-be_4-streams_1-hop_no-hop-cbs-iperf-line-limit100-90s,<br>4-queue_2-cbs_2-be_4-streams_2-hop_with-hop-cbs-iperf-line-limit100-90s,<br>4-queue_2-cbs_2-be_4-streams_3-hop_with-hop-cbs-iperf-line-limit100-90s,<br>4-queue_2-cbs_2-be_4-streams_4-hop_with-hop-cbs-iperf-line-limit100-90s,<br>4-queue_2-cbs_2-be_4-streams_5-hop_with-hop-cbs-iperf-line-limit100-90s,<br>4-queue_2-cbs_2-be_4-streams_6-hop_with-hop-cbs-iperf-line-limit100-90s,<br>4-queue_2-cbs_2-be_4-streams_7-hop_with-hop-cbs-iperf-line-limit100-90s | 
| EX_TS-T,EX_TS-W | Figure 25 a,b | Single flow TAPRIO relation of window cycle and traffic patter with and without offload | Figure-25ab_EX_TS-T,EX_TS-W | 1to7_hops-taprio_nooffload_180txtime_175delta_prio3_singlestrict_shift_20perhop_40windows,<br>1to7_hops-taprio_nooffload_180txtime_175delta_prio3_singlestrict_shift_200perhop_400windows,<br>1to7_hops-taprio_offload_180txtime_175delta_prio3_singlestrict_shift_20perhop_40windows,<br>1to7_hops-taprio_offload_180txtime_175delta_prio3_singlestrict_shift_200perhop_400windows | 
| EX_TS | Table 11 | Single flow TAPRIO, classes A and B, different txtime-delay values, offload | Table-11_EX_TS | 1to7_hops-taprio_offload_200txtime_175delta_singledeadline_prio2,<br>1to7_hops-taprio_offload_200txtime_175delta_singledeadline_prio3,<br>1to7_hops-taprio_offload_200txtime_175delta_singlestrict_prio2,<br>1to7_hops-taprio_offload_200txtime_175delta_singlestrict_prio3,<br>1to7_hops-taprio_offload_450txtime_175delta_prio2_singledeadline,<br>1to7_hops-taprio_offload_450txtime_175delta_prio2_singlestrict,<br>1to7_hops-taprio_offload_450txtime_175delta_prio3_singledeadline,<br>1to7_hops-taprio_offload_450txtime_175delta_prio3_singlestrict | 
| EX_TM | Table 12 | Multi flow TAPRIO with fixed txtime-delay and delta with and without offload | Table-12_EX_TM | 1_hops-taprio_offload_180txtime_175delta_threeflows_shift_200perhop_400windows,<br>2_hops-taprio_offload_180txtime_175delta_threeflows_shift_200perhop_400windows,<br>3_hops-taprio_offload_180txtime_175delta_threeflows_shift_200perhop_400windows,<br>4_hops-taprio_offload_180txtime_175delta_threeflows_shift_200perhop_400windows,<br>5_hops-taprio_offload_180txtime_175delta_threeflows_shift_200perhop_400windows,<br>6_hops-taprio_offload_180txtime_175delta_threeflows_shift_200perhop_400windows,<br>7_hops-taprio_offload_180txtime_175delta_threeflows_shift_200perhop_400windows,<br>1_hops-taprio_nooffload_180txtime_175delta_threeflows_shift_200perhop_400windows,<br>2_hops-taprio_nooffload_180txtime_175delta_threeflows_shift_200perhop_400windows,<br>3_hops-taprio_nooffload_180txtime_175delta_threeflows_shift_200perhop_400windows,<br>4_hops-taprio_nooffload_180txtime_175delta_threeflows_shift_200perhop_400windows,<br>5_hops-taprio_nooffload_180txtime_175delta_threeflows_shift_200perhop_400windows,<br>6_hops-taprio_nooffload_180txtime_175delta_threeflows_shift_200perhop_400windows,<br>7_hops-taprio_nooffload_180txtime_175delta_threeflows_shift_200perhop_400windows | 
EX_UCC | Figure 27a-28a | Use case CBS all file flows used | Figure-27a-28a_EX_UCC | journal-use-case-version1_30s | 
EX_UCC-F | Figure 27b-28b | Use case CBS with individual three flows | Figure-27b-28b_EX_UCC-F | journal-use-case-version1_justFlow1SRA_30s,<br>journal-use-case-version1_justFlow2SRA_30s,<br>journal-use-case-version1_justFlow3SRB_30s | 
EX_UCT,EX_UCT-F | Table 13 | Use case TAPRIO with individual flow with and without cross-traffic | Table-13_EX_UCT,EX_UCT-F | journal-use-case-version2_taprio_deadlinedeadline_30s,<br>journal-use-case-version2_taprio_deadlinedeadline_justFlow1SRA_30s,<br>journal-use-case-version2_taprio_deadlinedeadline_justFlow2SRA_30s,<br>journal-use-case-version2_taprio_deadlinedeadline_justFlow3SRB_30s,<br>journal-use-case-version2_taprio_deadlinestrict_30s,<br>journal-use-case-version2_taprio_deadlinestrict_justFlow1SRA_30s,<br>journal-use-case-version2_taprio_deadlinestrict_justFlow2SRA_30s,<br>journal-use-case-version2_taprio_deadlinestrict_justFlow3SRB_30s,<br>journal-use-case-version2_taprio_strictdeadline_30s,<br>journal-use-case-version2_taprio_strictdeadline_justFlow1SRA_30s,<br>journal-use-case-version2_taprio_strictdeadline_justFlow2SRA_30s,<br>journal-use-case-version2_taprio_strictdeadline_justFlow3SRB_30s,<br>journal-use-case-version2_taprio_strictstrict_30s,<br>journal-use-case-version2_taprio_strictstrict_justFlow1SRA_30s,<br>journal-use-case-version2_taprio_strictstrict_justFlow2SRA_30s,<br>journal-use-case-version2_taprio_strictstrict_justFlow3SRB_30s |


### Examples of post-processing

## Figure 10
```
ansible-playbook plays/process.yml -vv -e scene=Figure-10 -e scene_folder=<local_path>/IEEE-Access-Raw/Figure-10
```
## Figure 17
```
ansible-playbook plays/process.yml -vv -e scene=Figure-17_ETF_Params -e scene_folder=<local_path>/IEEE-Access-Raw/Figure-17_ETF_Params
```
## Figure 18
```
ansible-playbook plays/process.yml -vv -e scene=Figure-25ab_EX_TS-T,EX_TS-W -e scene_folder=<local_path>/IEEE-Access-Raw/Figure-18_TAPRIO_Params 
```
## Figure 25
```
ansible-playbook plays/process.yml -vv -e scene=Figure-25ab_EX_TS-T,EX_TS-W -e scene_folder=<local_path>/IEEE-Access-Raw/Figure-25ab_EX_TS-T,EX_TS-W
```
## Table-11
```
ansible-playbook plays/process.yml -vv -e scene=Table-11_EX_TS -e scene_folder=<local_path>/IEEE-Access-Raw/Table-11_EX_TS        
```
## Table-12
```
ansible-playbook plays/process.yml -vv -e scene=Table-12_EX_TM -e scene_folder=<local_path>/IEEE-Access-Raw/Table-11_EX_TM
```
## Table 13
```
ansible-playbook plays/process.yml -vv -e scene=Table-13_EX_UCT,EX_UCT-F -e scene_folder=<local_path>/IEEE-Access-Raw/Table-13_EX_UCT,EX_UCT-F
```


## Citations
If you want to cite the **Methodology and Infrastructure for TSN-Based Reproducible Network Experiments** publication, use this BibTeX format:
```
@article{Bosk2022MethodologyInfrastructureIEEEAccess,
  author = {Bosk*, Marcin and Rezabek*, Filip and Holzinger, Kilian and Marino, Angela G. and Fons, Francesc and Kane, Abdoul A. and Ott, J{\"o}rg and Carle, Georg},
  title = {Methodology and Infrastructure for TSN-based Reproducible Network Experiments},
  journal = {IEEE Access},
  year = {2022},
  month = sep,
  issn = {2169-3536},
  doi = {10.1109/ACCESS.2022.3211969},
  url = {https://doi.org/10.1109/ACCESS.2022.3211969},
  pdf = {https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=9910175},
  month_numeric = {9}
}
```
If you want to cite the **EnGINE: Flexible Research Infrastructure for Reliable and Scalable Time Sensitive Networks** publication, use this BibTeX format:

```
@article{Rezabek2022EngineJNSM,
  author = {Rezabek*, Filip and Bosk*, Marcin and Paul, Thomas and Holzinger, Kilian and Gallenm{\"u}ller, Sebastian and Gonzalez, Angela and Kane, Abdoul and Fons, Francesc and Haigang, Zhang and Carle, Georg and Ott, J{\"o}rg},
  title = {EnGINE: Flexible Research Infrastructure for Reliable and Scalable Time Sensitive Networks},
  journal = {Journal of Network and Systems Management},
  year = {2022},
  month = sep,
  day = {08},
  volume = {30},
  number = {4},
  pages = {74},
  issn = {1573-7705},
  doi = {10.1007/s10922-022-09686-0},
  url = {https://doi.org/10.1007/s10922-022-09686-0},
  pdf = {https://link.springer.com/content/pdf/10.1007/s10922-022-09686-0.pdf},
  month_numeric = {9}
}
```

If you want to cite the **EnGINE: Developing a Flexible Research Infrastructure for Reliable and Scalable Intra-Vehicular TSN Networks** publication, use this BibTeX format:
```
@inproceedings{RezBosk21,
  title = {{EnGINE: Developing a Flexible Research Infrastructure for Reliable and Scalable Intra-Vehicular TSN Networks}},
  author = {Rezabek, Filip and Bosk, Marcin and Paul, Thomas and Holzinger, Kilian and Gallenm\"uller, Sebastian and Gonzalez, Angela and Kane, Abdoul and Fons, Francesc and Haigang, Zhang and Carle, Georg and Ott, J\"org},
  booktitle = {3rd International Workshop on High-Precision, Predictable, and Low-Latency Networking (HiPNet 2021)},
  year = {2021},
  address = {Izmir, Turkey},
  month = oct,
  pdf = {http://www.net.in.tum.de/fileadmin/bibtex/publications/papers/rezabek_hipnet2021.pdf},
  month_numeric = {10}
}
```
If you want to cite the **Demo: Environment for Generic In-vehicular Network Experiments - EnGINE** publication, use this BibTeX format:
```
@inproceedings{BoskRez21,
  title = {{Demo: Environment for Generic In-vehicular Network Experiments - EnGINE}},
  author = {Bosk, Marcin and Rezabek, Filip and Holzinger, Kilian and Gonzalez, Angela and Kane, Abdoul and Fons, Francesc and Haigang, Zhang and Carle, Georg and Ott, J\"org},
  booktitle = {13th IEEE Vehicular Networking Confernce (VNC 2021)},
  year = {2021},
  address = {Ulm, Germany},
  month = nov,
  pdf = {http://www.net.in.tum.de/fileadmin/bibtex/publications/papers/bosk_vnc2021.pdf},
  month_numeric = {11}
}
```
## Licensing
The source code of EnGINE is published under the MIT license. Its main contributors are (alphabetically):
* Marcin Bosk
* Thomas Paul
* Filip Rezabek

In case other license applies, it is mentioned in the header of the given file e.g.,`send_udp_tai.c`.
Similarly, in case other license applies, it is mentioned in the header of the given file e.g., `Iperf3LikePacketSource.ned`. 
Externally libraries that are used as a part of the experiment execution have their corresponding licensing e.g., [linuxptp](http://linuxptp.sourceforge.net/), [iperf3](https://github.com/esnet/iperf).
OMNeT++ is distributed under the Academic Public License. For commercial purposes navigate to the [https://omnest.com/](https://omnest.com/).
