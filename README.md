# EnGINE Framework
**En**vironment for **G**eneric **I**n-vehicular **N**etworking **E**xperiments (EnGINE) is a highly manageable orchestration tool built in Ansible.
EnGINE a configurable, scalable, flexible, and reproducible setup that operates autonomously (once well configured). It can incorporate various real data sources and recorded footage. Besides, multiple probes can be set up to collect data during the experiment run, such as .pcaps or logs. Such data can be interpreted to provide insights into experiment outcomes. The design allows the reuse of various applications and configurations from different scenarios, minimizing the maintenance overhead. 
The latest extension includes the translation functionality of the scenario configuration to the OMNeT++ configuration, individual playbooks for running the simulation flow, and results post-processing.
The reasons why EnGINE and OMNeT++ have been selected for a hybrid experimentation platform can be found in the submitted paper that appears at [IFIP 2023](https://networking.ifip.org/2023/).


The repository is structured as follows:
* [engine](engine) - contains the modified codebase of the EnGINE framework, which includes provisions for the simulation capability
* [results](results) - contains the simulation results used for results in the publication
* [simulation](simulation) - contains the installation scripts for OMNeT++ and provisions for given simulations

This repository contains the EnGINE framework and scenarios used in the publication: Methodology and Infrastructure for TSN-based Reproducible Network Experiments.

This is a supplementary repository of the following list of publications:
* Marcin Bosk*, Filip Rezabek*, Johannes Abel, Max Helm, Kilian Holzinger, Georg Carle, Jörg Ott: Simulation and Practice: A Hybrid Experimentation Platform for TSN. To appear at the [IFIP 2023](https://networking.ifip.org/2023/)
* Marcin Bosk*, Filip Rezabek*, Kilian Holzinger, Angela Gonzalez Mariño, Abdoul Aziz Kane, Francesc Fons, Jörg Ott, Georg Carle: Methodology and Infrastructure for TSN-Based Reproducible Network Experiments. IEEE Access 10: 109203-109239 (2022), [PDF: Methodology and Infrastructure - IEEE Access 2022](https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=9910175)
* Filip Rezabek*, Marcin Bosk*, Thomas Paul, Kilian Holzinger, Sebastian Gallenmüller, Angela Gonzalez Mariño, Abdoul Kane, Francesc Fons, Haigang Zhang, Georg Carle, Jörg Ott: EnGINE: Flexible Research Infrastructure for Reliable and Scalable Time Sensitive Networks. J. Netw. Syst. Manag. 30(4): 74 (2022), [PDF: EnGINE - JNSM 2022](https://link.springer.com/content/pdf/10.1007/s10922-022-09686-0.pdf)
* Filip Rezabek, Marcin Bosk, Thomas Paul, Kilian Holzinger, Sebastian Gallenmüller, Angela Gonzalez Mariño, Abdoul Kane, Francesc Fons, Haigang Zhang, Georg Carle, Jörg Ott: EnGINE: Developing a Flexible Research Infrastructure for Reliable and Scalable Intra-Vehicular TSN Networks. CNSM 2021: 530-536, [PDF: EnGINE - CNSM/HipNET 2021](http://www.net.in.tum.de/fileadmin/bibtex/publications/papers/rezabek_hipnet2021.pdf)
* Marcin Bosk, Filip Rezabek, Kilian Holzinger, Angela Gonzalez Mariño, Abdoul Kane, Francesc Fons, Haigang Zhang, Georg Carle, Jörg Ott: Demo: Environment for Generic In-vehicular Network Experiments - EnGINE. VNC 2021: 117-118, [PDF: Demo - VNC 2021](http://www.net.in.tum.de/fileadmin/bibtex/publications/papers/bosk_vnc2021.pdf)

```*``` Authors with * contributed to the publications equally
## EnGINE Framework Brief Overview

The experiment campaigns are managed in four steps:

[ install ] --> [ setup ] --> [ scenario ] --> [ process ]

*  install: install nodes with an image and prepare them to be available for experiments
*  setup: do some generic setup tasks (install non-included packages, etc.) so that nodes have all dependencies required for experiments
*  scenario: run an experiment campaign -> multiple experiments around one topic
*  process: do post-processing for a single experiment or over multiple experiments

Every step has a playbook to execute it.
All playbooks require one extra parameter that needs to be specified when executing the playbook: "pgroup" is the host group  here all the commands should be applied to. The pgroup name points to a group inside the hosts file.

### Playbook Execution

Playbooks are executed from the command line in the top-level inside the repository folder. The folder needs to be on a testbed management node to execute the "install" step/playbook.

* Run install:  `ansible-playbook plays/install.yml -e pgroup=nodes`
* Run setup:    `ansible-playbook plays/setup.yml -e pgroup=nodes`
* Run scenario: `ansible-playbook plays/scenario.yml -e scene=<scenario-name>`
* Run post-processing: `ansible-playbook plays/process.yml -e scene=<scenario-name> -e scene_folder=<absolute-path-to-folder-with-scenario-results>`
* Run all steps:`ansible-playbook plays/all.yml -e scene=<scenario-name>`

**Example for post-processing of scenarios:** `ansible-playbook plays/process.yml -vvv -e scene=Figure-9 -e scene_folder=/results/Figure-9`

You can try the custom OMNeT++ [project](../simulation/engine) standalone. See [README](../simulation/README) for the required OMNeT++ and INET framework versions.

The translation scripts and templates that generate an INI file based on an EnGINE scenario definition via YAML files can be found in the Ansible role [generate_ini](roles/generate_ini). In subfolder [files](roles/generate_ini/files), run `./generate_ini.py -o <scenario-name>.ini -m mac <scenario-name>`.

The playbook for running the simulation requires that appropriate versions of OMNeT++ and the INET framework, as well as the custom simulation project, are installed at certain locations (see [README](../simulation/README)). We use a [playbook](plays/sim_setup.yml) that does this installation (plus installation of any dependencies) from scratch at a selectable testbed node. See the playbook for details.
* Run setup:    `ansible-playbook plays/sim_setup.yml -e simulation_node=<node-name>`

Once everything is setup, the actual simulation can be run by passing the respective scenario.
* Run scenario: `ansible-playbook plays/sim_scenario.yml -e simulation_node=<node-name> -e scene=<scenario-name>`

Processing of the (simulation) result files can be done manually via the script [process.py](roles/process/files/process.py)
* Run result processing script: `./process.py -d ../../plays -f <folder-with-scenario-results> <scenario-name> -c -p -s`
  * The `-s` flag is required for the results produced by the simulation playbooks. Without this flag, the scripts can also be used to process results produced by the original engine playbooks.

### Limitations of This Repository
To deploy EnGINE in your infrastructure, you need hardware managed from a central management host with SSH access to the individual nodes. 
If you have such deployments on hand, you can update the `host_vars` directory with your corresponding nodes. 

For our deployments we are using pos [1]. To find out about the architecture, navigate to these publications:
* [1] Pos
* [2] EnGINE JNSM 

## Relevant publications using & Extending EnGINE
Extension of EnGINE is present in **Multilayer Environment and Toolchain for Holistic NetwOrk Design and Analysis**:
```
@misc{rezabek2023multilayer,
      title={Multilayer Environment and Toolchain for Holistic NetwOrk Design and Analysis}, 
      author={Filip Rezabek and Kilian Glas and Richard von Seck and Achraf Aroua and Tizian Leonhardt and Georg Carle},
      year={2023},
      eprint={2310.16190},
      archivePrefix={arXiv},
      primaryClass={cs.DC}
}
```

**EnGINE** was used in **Playing the MEV Game on a First-Come-First-Served Blockchain**:
```
@misc{öz2024playing,
      title={Playing the MEV Game on a First-Come-First-Served Blockchain}, 
      author={Burak Öz and Jonas Gebele and Parshant Singh and Filip Rezabek and Florian Matthes},
      year={2024},
      eprint={2401.07992},
      archivePrefix={arXiv},
      primaryClass={cs.CR}
}
```

**EnGINE** was used in **TSN Experiments Using COTS Hardware and Open-Source Solutions: Lessons Learned**:
```
@INPROCEEDINGS{10150312,
  author={Rezabek, Filip and Bosk, Marcin and Carle, Georg and Ott, Jörg},
  booktitle={2023 IEEE International Conference on Pervasive Computing and Communications Workshops and other Affiliated Events (PerCom Workshops)}, 
  title={TSN Experiments Using COTS Hardware and Open-Source Solutions: Lessons Learned}, 
  year={2023},
  volume={},
  number={},
  pages={466-471},
  keywords={Pervasive computing;Performance evaluation;Protocols;Conferences;Hardware;Behavioral sciences;Network interfaces;TSN;COTS;Open-Source;PTP;Experiments},
  doi={10.1109/PerComWorkshops56833.2023.10150312}}

```



If you want to cite the **Simulation and Practice: A Hybrid Experimentation Platform for TSN** publication, use this BibTeX format:
```
@inproceedings{BoskRez23IFIP,
  title = {{Simulation and Practice: A Hybrid Experimentation Platform for TSN}},
  author = {Bosk*, Marcin and Rezabek*, Filip and Abel, Johannes and Holzinger, Kilian and Helm, Max and Carle, Georg and Ott, J\"org},
  booktitle = {22nd International Federation for Information Processing (IFIP) Networking Conference},
  year = {2023},
  address = {Barcelona, Spain},
  month = jun,
  month_numeric = {6}
}
```

**EnGINE** was used in **PTP Security Measures and their Impact on Synchronization Accuracy**:
```
@INPROCEEDINGS{9964658,
  author={Rezabek, Filip and Helm, Max and Leonhardt, Tizian and Carle, Georg},
  booktitle={2022 18th International Conference on Network and Service Management (CNSM)}, 
  title={PTP Security Measures and their Impact on Synchronization Accuracy}, 
  year={2022},
  volume={},
  number={},
  pages={109-117},
  keywords={Protocols;Power system protection;Peer-to-peer computing;Topology;Security;Synchronization;Power system faults;PTP;security;clocks;synchronicity;TSN},
  doi={10.23919/CNSM55787.2022.9964658}}
```

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
  booktitle = {13th IEEE Vehicular Networking Conference (VNC 2021)},
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

In case another license applies, it is mentioned in the header of the given file, e.g.,`send_udp_tai.c`.
Similarly, in case another license applies, it is mentioned in the header of the given file, e.g., `Iperf3LikePacketSource.ned`. 
Externally libraries that are used as a part of the experiment execution have their corresponding licensing, e.g., [linuxptp](http://linuxptp.sourceforge.net/), [iperf3](https://github.com/esnet/iperf).
OMNeT++ is distributed under the Academic Public License. For commercial purposes, navigate to the [https://omnest.com/](https://omnest.com/).
