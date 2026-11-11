# New EnGINE Post-Processing

> TY Filip for initial text prep!

The updated post-processing pipeline is in place. Overall, it introduces changes to the way how the data are stored and processed during the execution of the `process.yml` playbook. Relevant demos:

- [demo_testing](../../scenarios/demos-springfield/demo_testing/)

The flow of execution is - collect data on a service level -> create an intermediate representation in .csv format, read .csv and store in database based on `group_id`, read data from database and visualize the relevant data. Possibly, if defined in `04-experiments.yml` visualize results cross different experiments. More info TBD.

A short overview on how to add your service to the process pipeline:

1. Modify your stacks that are generating data and storing data on the management with additional arguments, mainly `group_id`, `file`, and `role`. Others, e.g., format or msg type are not mandatory.
2. Extend the [process.py](./files/process.py) with your stack info - around line 500 and extract relevant information
3. (if needed, e.g., for a new profile of tcpdump when you want to conver data from .pcap to .csv extend [`csv_parser_pcap_single.py`](../services/tcpdump/files/csv_parser_pcap_single.py))
4. If you just have a .csv, extract the correct path and follow the steps to unify the format to add it to the sqlite database 
5. Add the .csv that you are expecting to collect to the `paths_to_csvs` - it is important, as we have to check the files are present before proceeding to the individual steps and serves as a checkpoint that all parallel processes have finished successfully.
6. If all steps went well, your data should be appended correctly to the sqlite database and should proceed well and you should get at the end delay, jitter, and possibly packet loss.

For debug/implementation I recommend to copy the whole scenario directory from the management host to your local machine and keep extending the process.py there. Once you are confident stuff should work, just run a whole `scenario_process.yml` to see if stuff works. Follow steps to execute the pipeline as defined here: 

Few side comments:

- service/experiment can be in multiple groups
- If you dont define a service to belong to multiple groups, only a data from the given group will used for visualizations. For cross-group experiments, add data to so-called meta group to get all results e.g., `group_id: 4`
- Your scenario must have `05-process.yml` if you want to use the processing pipeline - it allows you to specify the relevant groups, limits/offset, and others. Feel free to extend the pipeline by new label descriptors or delay formats.

We hope this will help the flow and unifies the data to a similar format and most importantly, enables data correlation independent of their data collection in the network. For more advanced visualization you can also just copy the database that is created on per scenario basic and interact with it easily without the need to move around .csvs.
More demos are coming soon - expect by the end of the week. In case you have any questions in the meantime or stuff dont work as expected, you know where to reach us :) Also, always happy to hear some feedback, comments, on how to improve the readability or what features would be beneficial to you.

# Old Processing Description Below

## How to use processing

- run scenario with all.yml or scenario_process.yml
- call process.yml directly after running scenario
    - Example: `ansible-playbook plays/process.yml -e scene=demo_post -e scene_folder=/srv/testbed/vehiclenet/experiments/2023-04-19D-13:58:27T_demo_post`
- run locally by directly running process.py
    - `python3 path_to_process.py scenario_name -f path_to_scenario_results -c -p`
    - Example: `python3 engine/roles/process/files/process.py demo-netem -f /path/to/results/2023-03-25D-17:44:18T_demo -c -p -a`

## Relevant Files for Processing

engine/engine/roles/process/files

- process.py - Main file for processing. It parses experiments from YAML files of the scenario and spawns new processes to process the results. concurrent_limit variable (currently 4) is the limit of the number of processes.
- processing_descriptor.py - Helper class for processing. Holds information for an endpoint of a flow.
- plot_plots.py - Holds common functions for plotting.
- plot_csv_single.py - Plots results using csv's created by csv converter scripts.
- plot_csv_combined.py - Plots results using csv's created by csv converter scripts.

engine/engine/roles/services/tcpdump/files

- csv_parser_pcap_single.py - Parses single tcpdumps pcaps into csv's.
- csv_parser_pcap_combined.py - Using csv's parsed by csv_parser_pcap_single, correlates csv's from flow endpoints and creates new csv for delay/jitter calculation.

engine/engine/roles/services/generate_config/files

- access_variables.py - Functions for parsing scenario YAML files.

engine/engine/roles/services/[iperf,send_udp]/files

- process_[iperf,send_udp].py - Application specific parsing

## Simple Flow of Processing

1. process.py iterates through experiments
2. process.py spawns new processes that calls functions from csv_parser_pcap_single.py for every node that is a server/sink of iperf/send_udp service, to parse pcaps into csv's.
3. process.py spawns new processes that calls functions from csv_parser_pcap_combined.py to correlate csv's of every iperf/send_udp service endpoints to compute delay csv's.  
Also concurrently spawns processes to call functions from plot_pcap_single.py to plot results using csv's created by csv_parser_pcap_single.py.
4. Lastly, process.py spawns new processes from plot_pcap_combined.py to plot using information from csv's created by csv_parser_pcap_combined.py.

## Options

These options are used in 00-nodes.yml file of a scenario. An example can be seen in demo_post scenario.

- processing_node:  
This option is used to delegate some other host than management host to process the results. If the processing_node is localhost or is not defined, results will be processed in management node.  
It achieves this by sending engine folder and experiment artifacts to the selected processing node and simply executes process.py from there.  
Example:
> processing_node: maggie
- parse_pcaps_on_nodes:  
If true, this will parse pcaps on experiment nodes directly and send them to management host.  
It achieves this by sending engine folder to the experiment nodes and execute process.py from there.  
process.py has command line options so that it can understand which node it is on and execute only functions from csv_parser_pcap_single.py, plot_pcap_single.py.  
Nodes then sends these results to management host.  
Example:
> parse_pcaps_on_nodes: true
- auto_tcpdump_collection:  
If true, this option will create tcpdump services automatically for every iperf/send_udp service. It uses measurement.yml in service roles files.   
send_udp flows additionally need a dummy send_udp service for flow endpoint for auto tcpdump collection to work. It needs to have flow and port information.  
You can also turn this off for specific services by adding tcpdump: off to service definition.     
Example: 
> { name: send_udp, role: sink, flow: 1, port: 1001 }  
> { name: iperf, role: client, flow: 1, port: 1004, prio: 4, limit: 1000000000, time: 4, size: 1180, level: 1, sync_start: yes, signal: yes, udp: yes, use_core: 1, **tcpdump: off** }

## How to add a new service (like iperf)?

- Edit code in process.py process_exp function so that the service gets parsed from scenario YAML files.
- Create a process_<new_service>.py file in engine/engine/roles/services/<new_service>/files like in iperf/send_udp.  
This function will parse service specific stuff from pcaps(like iperf_sequence for iperf). timestamp and packet size are parsed by default from all pcaps. 
List named "merge" is used for correlating endpoint csv's for delay calculation. Columns in "merge" list will be matched to match packets from two endpoints.  Import this python file into csv_parser_pcap_[single, combined].
- Create a measurement.yml file like in iperf/send_udp for auto_tcpdump_collection to work.  
- Iperf and send_udp is very similar, only thing different is parsing extra stuff used in packet correlating for delay calculation.  
So if the new service is fundamentally different than iperf/send_udp you might need to add more code for new parsing/plotting.


## How to add a fundamentally different service from iperf (input is not a pcap, different plots etc)?

### processing_descriptor class 
This class is used in plotting and parsing functions. It has info about a service of a machine. Using this class as a function parameter, the functions can know the file location of inputs, the tcpdump pcap or csv name of the input, interface of the service etc.  
dst_ports and iface variables of processing descriptor is used to determine tcpdump pcap file names, and output csv names. dst_ports do not actually have to be ports, they are just used as identifiers, but the corresponding tcpdump service should have the same 'file' variable as this dst_port. info variable has the service dict entry of the corresponding port  
For example with processing_descriptor variables: dst_ports = [1234], iface = ['eth0'], info : { 1234: { 'name': 'iperf', 'iface': 'eth0', 'port': 1234 }}  
> tcpdump name will be:  
tcpdump_1234_eth0.pcap  
output csv name will be:  
csv-iperf-single_1234_eth0.csv   

So it is important that corresponding tcpdump file has the 'file' variable set to whatever is in the dst_ports list of processing_descriptor, otherwise the processing script can not find the correct tcpdump.

### Input parsing

- Input is a pcap:  
    There are two options to collect pcaps
    - Probably easiest: You can add auto tcpdump collection for the new service. Take a look at iperf3/tasks/measurement.yml or send_udp/tasks/measurement.yml to see how it is done. It simply adds a new tcpdump dictionary entry to services dict.
    - Add tcpdump services on stacks.yml manually. 
    You need to have an unique identifier, that binds tcpdump to a service. For example, in case of iperf this is a port. The 'file' variable of the tcpdump service should be equal to this unique identifier. For iperf/send_udp this identifier is simply the port. 
    In process.py, pass this identifier to processing_descriptor dst_ports list, even if the identifier is not a port. This identifier is used to determine tcpdump pcap file names and the created csv file names.  
    For example a new service named newservice:
    > - { 'name': 'newservice', 'id'/'port'/'whatever': 'abcdef' }
    > - {'name': 'tcpdump', 'filter':..., 'file': 'abcdef'}  
      
    So file variable is used to determine to which service  tcpdump belongs to. In process.py, you need to pass this identifier ('id'/'port'/'whatever' above) in the dst_ports list of processing descriptor while adding parsing support for your new service.  
    Afterwards current pcap parsing scripts should work for new service. Take a loot at "How to add a new service (like iperf)?" section for correlating pcap packets between start and end points. 
- Input is not pcap: 
    You need to write your custom parsing script and call it on process_endpoint_csv function. 
    If you want to use current plotting scripts (throughput etc.), you need to have the same csv structure as explained below.  
    If you do not want to use current plotting scripts, you should just ensure that the service is being parsed and right function is being called in process.py, and write your custom parsing/plotting scripts.  

### Csv structure 
Columns: 
> timestamp_ns: timestamp of the csv entry (single packet for pcaps)
> packet_size_bytes: size in bytes of csv entry (does not have to be a single packet) 

The remaining columns are service specific. Look at "How to add a new service (like iperf)?" section for more. 

### Example: Add support for ploting iperf logs, using current plotting scripts 
- You don't need to add additional parsing in process.py, as iperf services are already being parsed. 
- Create an additional processing_descriptor while parsing iperf. It should be almost equal to processing_descriptor for normal iperf, you should edit the service name in info variable of processing_descriptor, so that the resulting parsed csv names do not clash. For example change name to iperflog. After parsing, resulting csv name should be for example:  
csv-iperflog-single_1234_eth0.csv  
The csv structure should be the same as described before so that plotting scripts work.
- Create your custom parsing script to parse log and convert to csv. The name of the csv should be as above. Call your custom script in process_endpoint_csv function in process.py if service name is iperflog.  
- No need to correlate iperf log files in start and endpoints so if service name is iperflog do nothing in process_stream_csv and process_stream_plot. 
- You don't need to change anything for plotting. If created csv name and structure of csv are correct the plotting scripts should all work without additional changes. 