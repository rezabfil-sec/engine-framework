# Methodology and Infrastructure for TSN-based Reproducible Network Experiments
This repository containes the EnGINE framework and scenarios used within publication titled: Methodology and Infrastructure for TSN-based Reproducible Network Experiments.

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

### Limitations of This Repository
**TODO**
* Say that it needs a hardware deployment
* Say that initial node orchestration is not available
* Are we listing all required dependencies of the framework?


<!-- During development some tasks can be skipped in order to test only some parts:
* List parts that can be skipped: `ansible-playbook plays/scenario.yml --list-tags`
* Skip clock and network setup:`ansible-playbook plays/scenario.yml -e pgroup=nodes -e scene=<scenario-name> --skip-tags "ptp,network"` -->


 <!-- **Procedure**

 1. Synchronize Time between hosts (linuxptp)
 2. Set the correct Linux Network Traffic Control - qdisc (Queuing Discipline)
	 - etf + taprio - time-aware scheduler in conjunction with time-based transmission (802.1Qbv)
	 - cbs - credit based shaper (802.1Qav) -->


<!-- ## PTP - Time Synchronization

Linux PTP Stack - [linuxptp](http://linuxptp.sourceforge.net/)
 - **ptp4l** -> set network adapter as grandmaster clock or client
 - **phc2sys** -> synchronize network card clock with system clock -->

<!-- ## Linux TSN Scheduling

### ETF qdisc
Not really TSN feature/requirement! Earliest TxTime First (ETF), enables LaunchTime feature supported by the NIC. Send packets at a specific time. Socket-Option must be set SO_TXTIME. Current timestamp goes to CMSG-section and the time the packet should be sent to the SCM-TXTIME field.

### CBS (802.1Qav)

### TAPRIO (802.1Qbv)

# Links / Documentation

 - [Scheduled Tx Tool (taprio + etf)](https://gist.github.com/jeez/bd3afeff081ba64a695008dd8215866f)
 - [Extensive documentation how to use TSN with Linux (VLAN, Qdiscs, gPTP)](https://tsn.readthedocs.io/index.html) -->


## Experiments
In the following, the experiments used in publication "Methodology and Infrastructure for TSN-based Reproducible Network Experiments" are listed. Of note, this repository only contains the used configurations contained in the [scenarios](scenarios) folder. The actual results are available here: **[TODO]()**

While this repository contains most of the code of EnGINE framework, without a suitable hardware deployment and adequate configuration of the nodes, it can only be used to evaluate the results of the experiments. This can be achieved using the [process.yml](plays/process.yml) playbook. **As an example for post-processing of scenario Figure-9:** `ansible-playbook plays/process.yml -vvv -e scene=Figure-9 -e scene_folder=/results/Figure-9`

The plots used within the aforementioned publication can be plotted using the [Journal Plotting](scripts/plotting/plot_journal.py) script. **Importantly, you need to specify the [path to your folder](scripts/plotting/plot_journal.py#L665) containing all result artefacts!!!** After doing that, the plotting script can be run by switching to the [plotting](scripts/plotting) folder and running `python3 plot_journal.py`. Note that you need to have all dependecies installed. 

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


<!-- ## Figure 10
ansible-playbook plays/process.yml -vv -e scene=Figure-10 -e scene_folder=/srv/testbed/vehiclenet/ieee-access-results/Figure-10

## Figure 17
ansible-playbook plays/process.yml -vv -e scene=Figure-17_ETF_Params -e scene_folder=/srv/testbed/vehiclenet/experiments/2022-07-17D_ETF_parameterStudyDeltaValues
## Figure 18
ansible-playbook plays/process.yml -vv -e scene=Figure-25ab_EX_TS-T,EX_TS-W -e scene_folder=/srv/testbed/vehiclenet/ieee-access-results/Figure-18_TAPRIO_Params 

## Figure 25
ansible-playbook plays/process.yml -vv -e scene=Figure-25ab_EX_TS-T,EX_TS-W -e scene_folder=/srv/testbed/vehiclenet/experiments/2022-07-19D_journal 

## Table-11
ansible-playbook plays/process.yml -vv -e scene=Table-11_EX_TS -e scene_folder=/srv/testbed/vehiclenet/experiments/2022-07-17D_singleFlowClassABTxTimeOffload            
## Table-12
ansible-playbook plays/process.yml -vv -e scene=Table-12_EX_TM -e scene_folder=/srv/testbed/vehiclenet/experiments/2022-07-17D_multiFlowClassABBE_180TxTime_175delta_Offload_shift 
## Table 13
ansible-playbook plays/process.yml -vv -e scene=Table-13_EX_UCT,EX_UCT-F -e scene_folder=/srv/testbed/vehiclenet/experiments/2022-07-17D_multiandSingleFlowTAPRIOUseCase_withandwithoutCross    -->