#!/usr/bin/python3

# Post-process every single experiment

import argparse
import sys
import time
import os
import sqlite3
import glob
from sqlite3 import Error
import pandas as pd

import processing_descriptor
import plot_csv_combined as ppc
import plot_csv_single as pps
import db_queries as dq

sys.path.append("../../../scripts")
import process_variables as pv

sys.path.append("../../services/tcpdump/files")
import csv_parser_pcap_single as cpps
# import ndn_pcap_parser as npp --> in the main of engine repo
import csv_parser_pcap_combined as cppc

sys.path.append("../../services/queue_monitor/files")
import csv_parser_qm as cpqm
import plot_qm as pqm
from copy import deepcopy

from multiprocessing import Process, Semaphore

sys.path.append("../../generate_config/files")
import access_variables as av


sys.path.append("../../services/send_udp/files")
sys.path.append("../../../services/send_udp/files")
import process_send_udp
sys.path.append("../../services/iperf/files")
sys.path.append("../../../services/iperf/files")
import process_iperf
sys.path.append("../../services/algorand/files")
sys.path.append("../../../services/algorand/files")
import process_algorand

# the script will create csvs and plots if the corresponding variable is set to true
csv = False
plot = False
sim = False
# if process_on_node is true, the data of individidual nodes will be processed on that node itself
process_on_node = False
node_name = ''
# concurrent limit is the maximum number of concurrent processes that can be run
concurrent_limit = 4
experiment_name = ''
num_isolated_cores = 0
ndn = False
service_used = ''


def get_paths(processing_descriptor):
    ''' Initialize general analysis '''
    fl = processing_descriptor.log_file() # log file
    preOutPath = processing_descriptor.pre_path() # export directory
    return fl, preOutPath

def process_queues(pd):
    '''plots queue levels of qdiscs, not supported right now'''
    if csv:
        cpqm.save_qm_to_csv(pd)
    if plot:
        pqm.plotQueueLevelPacketsOrBytesOptWithLog("Packets", pd)
        pqm.plotQueueLevelPacketsOrBytesOptWithLog("Bytes", pd)


def process_endpoint_csv(pd, sema):
    '''parses pcaps into csv's, only for single endpoint of a stream (no jitter/delay)'''
    if process_on_node and node_name != pd.node:
        sema.release()
        return
    if csv and not pd.ndn:
        print('Calling parse single pcaps')
        cpps.parse_separate_pcaps(pd)
    # if csv and pd.ndn:
    #     npp.parse(pd)
    sema.release()


def process_stream_csv(pd_end, pd_start, sema):
    '''parses csv's created from process_endpoint_csv to create new csv's for jitter/delay'''
    if process_on_node:
        # cannot correlate packets if we only have data of one node currently
        sema.release()
        return
    if csv:
        cppc.save_delay_and_jitter_to_csv(pd_end, pd_start, service_used)
    sema.release()


def process_endpoint_plot(pd, sema):
    '''plots results from csv's parsed from process_endpoint_csv'''
    if process_on_node and node_name != pd.node:
        sema.release()
        return
    if plot:
        pps.plot_all(pd)
    sema.release()


def process_stream_plot(pd, sema):
    '''plots results from database's parsed from process_stream_db'''
    if process_on_node:

        # cannot correlate packets if we only have data of one node currently
        sema.release()
        return
    if plot:
        # Must be here for the algorand stuff --> pd_start
        ppc.plot_all(pd)

    sema.release()
# Not used as of now - change flow from iface based on group/file name phase
# def iface_with_name(node_to_flow_to_interfaces_mapping, nodes, node, flow, network_config="ovs"):
#     '''returns name of the iface of flow endpoints (so only start and end node) from flow id'''
#     ifaces = node_to_flow_to_interfaces_mapping[node][flow]
#     print("network_config",network_config)
#     host = nodes['node_mapping'][node]
#     containers_host_mapping = nodes['node_mapping']
#     containers = nodes['containers']
#     host_nodes = nodes['nodes']
#     print(host, host_nodes, containers_host_mapping)
#     # check if containers used at all
#     if len(containers) > 0:
#         print("Using containers in this scenario")
#         containers_used = True
#         for host_node in containers_host_mapping:
#             if containers_host_mapping[host_node] in host_nodes:
#                 print("Combination of containers and physical nodes")
#             else:
#                 print("only using containers nodes")
#     if host not in host_nodes:
#         print("host is container")
#         network_config = nodes["network_config"].lower()
#     else:
#         print("host is not a container", host)
#         network_config == "physical"
#     # print(host, node, nodes, containers, containers_host_mapping, host_nodes)
#     if network_config == "ovs" or network_config == "physical":
#         print("working with ovs or physical ifaces")
#         iface = int(ifaces[0]) # end point only has single interface on flow
#         iface_name = av.get_host_vars([host])['host_vars'][host]['node_ifaces'][iface]['name']
#     else:
#         if containers_used:
#             print("working with sr-iov and containers")
#             iface = int(ifaces[0].split('.')[0]) # end point only has single interface on flow
#             print(iface, ifaces)
#             # Corresponds to the fixed name in roles/setup/create_lxc_container.yml L:28
#             iface_name = "eno" + str(iface)
#         else:
#             # in sr-iov & sr-iov and LXC container
#             iface = int(ifaces[0].split('.')[0]) # end point only has single interface on flow
#             iface_name = av.get_host_vars([host])['host_vars'][host]['node_ifaces'][iface]['name']
#             iface_name = str(iface_name) + "v" + str(int(ifaces[0].split('.')[1]) - 1) # virtual iface start from 0, flow definition from 1
#     return iface, iface_name


def get_free_core(processes):
    '''finds a free core from the isolated cores to run the new process on'''
    if num_isolated_cores <= 1:
        return -1
    cores = [False for i in range(0, num_isolated_cores)]
    for p, core in processes:
        if p.is_alive():
            cores[core] = True
    for i in range(1, num_isolated_cores):
        if not cores[i]:
            return i
    # if there is no free core, return -1, this will run the core on non isolated cores
    return -1


def start_process(target, args, processes):
 
    '''helper function for starting a new process'''
    args[-1].acquire()
    # get a isolated core to run the process on (returns -1 if none available)
    core = get_free_core(processes)
    p = Process(target=target, args=args)
    processes.append((p, core))
    p.start()
    if core > 0 and p.pid != None:
        os.sched_setaffinity(p.pid, {core})


#Function taken from the csv_parser_pcap_combined
def importCsvExtDnames(path_to_file):
    ''' reads csv, renames columns for delay/jitter calculation '''
    # If we get here, we know our files exist
    path_to_file = glob.glob(path_to_file)
    df = pd.read_csv(path_to_file[0], index_col=0) # Loads the CSV
    return df

def unify_format(df, node_num, data_source, profile, role):
    # MASTER FORMAT
    # [sequence_number], [timestamp_ns], [node], [role], [misc] 
    if data_source == 'tcpdump':
        if profile == 'algorand':
            # Algorand format
            # ,timestamp_ns,packet_size_bytes,algorand_payload, msg_type
            # Missing source
            df = df.rename(columns={'msg_type' : 'misc', 'algorand_payload': 'sequence_number'})
            # Add missing source
            df['node'] = node_num
            df['role'] = role
            # Dropping payload size
            df = df.drop(columns=['packet_size_bytes'], axis=1)
            print(df)
        if profile == 'ethereum':
            # Ethereum format
            # , tx, timestamp_ns
            df = df.rename(columns={ 'ethereum_tx': 'sequence_number'})
            df['node'] = node_num
            df['role'] = role
            df['misc'] = 'misc'
    


        # iperf3 format
        # ,timestamp_ns,packet_size_bytes,iperf_ts_seconds,iperf_ts_microseconds,iperf_sequences
        # Relevant 
        if profile == 'iperf3':
            # Combines three columns to one
            df['combined'] = df.apply(lambda x:'%s%s%s' % (x['iperf_ts_seconds'],x['iperf_ts_microseconds'],x['iperf_sequence']),axis=1)
            df = df.rename(columns={'packet_size_bytes' : 'misc', 'combined': 'sequence_number'})
            # drop not relevant information
            df = df.drop(['iperf_ts_seconds', 'iperf_ts_microseconds', 'iperf_sequence'], axis=1)
            # Add missing source
            df['node'] = node_num
            df['role'] = role
    elif data_source == "algorand-client":
            # Algorand-client format
            # ,timestamp_ns, nonce
            df = df.rename({'nonce': 'sequence_number', 'txid': 'misc'}, axis="columns")
            # REMOVE BEFORE COMMIT --> update on the source
            # df = df_column_switch(df, "timestamp_ns", "sequence_number")
            # Add missing source
            df['node'] = node_num
            df['role'] = role
            # df['misc'] = data_source
    elif data_source == "algorand-mempool-monitor":
            # Algorand-mempool format
            # ,sequence_nr,timestamp_in,timestamp_out,source
            df = df.rename({'sequence_nr': 'sequence_number', 'source': 'misc'}, axis="columns")
            # REMOVE BEFORE COMMIT --> update on the source
            df['node'] = node_num
            df['role'] = role
            # drop not relevant information
            df = df.drop(['timestamp_out'], axis=1)
    return df

def df_column_switch(df, column1, column2):
    i = list(df.columns)
    a, b = i.index(column1), i.index(column2)
    i[b], i[a] = i[a], i[b]
    df = df[i]
    return df

def check_files_exist(paths_to_files, fl):
    for file in paths_to_files:
        query_path = ""
        # for .csv reading directly, this has to be checked
        glob_outcome = glob.glob(file)
        print("glob outcome", glob_outcome, file)
        # Happens when we are waiting for .csv
        if len(glob_outcome) == 0 and file != "":
            query_path = file
        # case when csv is there already
        elif len(glob_outcome) != 0:
            query_path = glob_outcome[0]
        while not os.path.exists(query_path):
            with open(fl, "a") as myLog:
                print('Waiting for ', query_path, ' .csv to be processed', end='...\n', file=myLog)
            time.sleep(5)
    print("All files checked")

def check_table_exist(table_names, fl, db_path):
    if process_on_node:
        return
    for experiment in table_names.keys():
        for table in table_names[experiment]["delay"]:
            # Add maybe in the future additional structure
            while not dq.check_table_is_present(db_path, table):
                with open(fl, "a") as myLog:
                    print('Waiting for ', table, ' table to be processed', end='...\n', file=myLog)
                time.sleep(10)
        print("All tables checked")

def process_exp(folder_scene, nodes, net, stack, exp, db_path, process_variables):
    '''parses experiments, finds flow endpoints with a service running and plots the results'''
    exp_name = exp['name']
    global concurrent_limit
    global service_used
    sema = Semaphore(concurrent_limit)
  
    # first step: identify streams, scan the stacks.yml file to store what service is on what port/node
    # flow_to_node_to_port_to_services_mapping structure:
    # flow_to_node_to_port_to_services_mapping[flow id][node id][port of service] = [services bound to the given flow, node ids and port]
    # below loop extracts only relevant services for post processing
    # !! only store in the array the endpoint which generates the packets (for iperf this is the client, for example)
    # iperf and send_udp the below code only extracts client or source services as the other end of the flow has the corresponding sink service
    group_to_node_to_stacks_mapping = {} # identify stacks that generate output for further post-processing
    # If no file is provided, stack is ignored
    # For tools that can be used for multiple applications e.g., tcpdump, use profile option to specify what profile is relevant

    # grouping relevant variables
    groups_to_add = process_variables['groups_to_add']
    groups_to_add_cross = process_variables['groups_to_add_cross']
    # visualization related variables
    limit = process_variables['limit']
    offset = process_variables['offset']
    delay_format = process_variables['delay_format']
    label_format = process_variables['label_format']

    # Creation of the group_to_node_to_stack mappings
    for node, services in stack['services'].items():
        print("node name", node, type(node))
        for service in services:
            print(service)
            # Possible not all services are using it
            # Here extract if additional information needed to identify the data
            # Name must be found
            service_name = service['name']
            # Default service group is [0]
            # 0 as single data source can belong to multiple groups
            # FIXME: Assume group is a list
            service_groups = [ 0 ]
            service_groups_len = 1
            service_flow = []
            service_port = 0
            service_file = ""
            service_profile = ""
            service_role = ""
            service_format = ""
            # FIXME: Assume msg type is a list
            service_msg_types = ""
            try:
                # Flow is needed in service to be able to check the network iface
                service_flow = service['flow']
            except KeyError:
                print('Flow not found for service', service_name)
            else:
                service_flow = service['flow']
        
            try:
                # Port might provide additional info, might not be present for all services
                service_port = service['port']
            except KeyError:
                print('Port not found for service', service_name)
            else:
                service_port = service['port']

            try:
                # File will provide file name as a path
                service_file = service['file']
                # name of the service
            except KeyError:
                print('File not found for service', service_name)
            else:
                service_file = service['file']

            try:
                # Profile provides info on how to process the given data
                # e.g., tcpdump algorand profile
                service_profile = service['profile']
                # name of the service
            except KeyError:
                print('Profile not found for service', service_name)
            else:
                service_profile = service['profile']
           
            try:
                # File will provide file name as a path
                service_groups = service['group_id']
                # name of the service
            except KeyError:
                print('Group ID not found for service', service_name)
            else:
                service_groups = service['group_id']
                service_groups_len = len(service_groups)
        
            try:
                # File will provide file name as a path
                service_role = service['role']
                # name of the service
            except KeyError:
                print('role is not defined for service', service_role)
            else:
                service_role = service['role']
            
            try:
                # Msg types will provide a list of file types we are interested in
                service_msg_types = service['msg_types']
                # msg type of the service
            except KeyError:
                print('msg_type is not defined for service', service_role)
            else:
                service_msg_types = service['msg_types']

            try:
                # service format relevant to the type of traffic
                service_format = service['format']
                # format of the service
            except KeyError:
                print('format is not defined for service', service_format)
            else:
                service_format = service['format']
            
            print('before ifs', node, service_groups, service_name, service_file, service_profile,service_port, service_flow, service_msg_types)
            # Organize as - group, node, name, file, (profile, flow, port)
            for service_group in service_groups:
                if service_group not in group_to_node_to_stacks_mapping.keys():
                    print("group number",service_group, type(service_group))
                    group_to_node_to_stacks_mapping[service_group] = {}
                if node not in group_to_node_to_stacks_mapping[service_group].keys():
                    print("node name", node, type(node))
                    group_to_node_to_stacks_mapping[service_group][node] = {}
                if service_name not in group_to_node_to_stacks_mapping[service_group][node].keys():
                    print("service name", service_name, type(service_name))
                    group_to_node_to_stacks_mapping[service_group][node][service_name] = {}
                if service_file not in group_to_node_to_stacks_mapping[service_group][node][service_name].keys():
                    print("service file", service_file, type(service_file))
                    group_to_node_to_stacks_mapping[service_group][node][service_name][service_file] = []
                misc_information_dict = {'profile': service_profile, 'msg_types': service_msg_types, 'port': service_port, 'flow': service_flow, 'role': service_role, 'group_id_len': service_groups_len, 'format': service_format }
                group_to_node_to_stacks_mapping[service_group][node][service_name][service_file].append(misc_information_dict)

    # print(group_to_node_to_stacks_mapping[1]['node-1'])
    processes = []
    group_to_node_file_mapping = {}
    # group
    for group in group_to_node_to_stacks_mapping.keys():
        paths_to_csvs = []
        if group in groups_to_add_cross:
            group_to_node_file_mapping[group] = {}
        # name of service
        # Limit here how many groups should be post-processed
        # Dont want to add to the DB the data from the group 4 as they are duplicates and does not help anything
        if group in groups_to_add:
            print("Adding group to database")
            conn = sqlite3.connect(db_path, timeout=50)
            dq.create_group_table(conn, group, exp_name)
        # node
        for node in group_to_node_to_stacks_mapping[group].keys():
            if group in groups_to_add_cross:
                group_to_node_file_mapping[group][node] = []
            info_group = {}
            file_list = []
            # service
            for name in group_to_node_to_stacks_mapping[group][node].keys():
                # file
                msg_types = ""
                for file in group_to_node_to_stacks_mapping[group][node][name].keys():
                    if group in groups_to_add_cross:
                        group_to_node_file_mapping[group][node].append(file)
                    # Do hear all the magic needed to identify the files on the nodes
                    if file != '':
                        print(file, name)
                        # if no parsing is needed, this flag should apply
                        process_to_csv = True
                        data_to_add = True
                        plot_single = True
                        # Relevant for the cross-group evaluations
                        file_list.append(file)
                        info_group[file] = {'name': name }
                        group_id_len = group_to_node_to_stacks_mapping[group][node][name][file][0]['group_id_len']

                        if name == "tcpdump":
                            # Comment: Update needed - adding profile and unique file to tcpdumps
                            profile = group_to_node_to_stacks_mapping[group][node][name][file][0]['profile']
                            # might be empty for some bits
                            msg_types = group_to_node_to_stacks_mapping[group][node][name][file][0]['msg_types']
                            role = group_to_node_to_stacks_mapping[group][node][name][file][0]['role']
                            format = group_to_node_to_stacks_mapping[group][node][name][file][0]['format']
                            # This is telling in how many other groups is the given stack
                            # in case in more than one, most likely it means that we want to cross-visualize it with other stacks
                            # Nevertheless, in case it is not used, just results in an overhead and double print
                            info = {file: {'name': name }}
                            print(profile, role)
                            if profile == "algorand":
                                # list
                                msg_types = group_to_node_to_stacks_mapping[group][node][name][file][0]['msg_types']
                                # format
                                default_csv_name = 'csv-' + name + '-single_' + file + '.csv'
                                print("In algorand")
                            elif profile == "iperf3":
                                print("Iperf 3")
                                default_csv_name = 'csv-' + name + '-single_' + file + '.csv'
                            elif profile == "send_udp":
                                print("send UDP")
                            elif profile == "ethereum":

                                msg_types = group_to_node_to_stacks_mapping[group][node][name][file][0]['msg_types']


                                format = group_to_node_to_stacks_mapping[group][node][name][file][0]['format']

                                default_csv_name = 'csv-' + name + '-transactions-times_' + file + '.csv'
                                print("ethereum in the house")
                            # EXTEND HERE
                            # Update with your own profiles for tcpdump

                            pd_file = processing_descriptor.ProcessingDescriptor(folder_scene, node, sim, experiment=exp_name, ndn=ndn, dst_ports=[file], info=info, profile=profile, msg_types=msg_types, limit=limit, offset=offset, format=format, role=role)
                            # fl is a PythonLog.txt info
                            fl, preOutPath = cpps.init_general(pd_file)
                            path_to_csv = preOutPath + default_csv_name
                            paths_to_csvs.append(path_to_csv)
                        elif name == "algorand-client":
                            print("Working on algorand client")
                            process_to_csv = False
                            data_to_add = True
                            # Stick to csv- format!!!
                            if file == "":
                                default_csv_name = "client-algorand"
                            else:
                                default_csv_name = file
                            # visualize locally
                            # Relevant for the cross-group evaluations
                            file_list.append(file)
                            info_group[file] = {'name': name }
                            info = {file: {'name': name }}
                            profile = name
                            role = group_to_node_to_stacks_mapping[group][node][name][file][0]['role']

                            pd_file = processing_descriptor.ProcessingDescriptor(folder_scene, node, sim, experiment=exp_name, ndn=ndn, dst_ports=[file], info=info, limit=limit, offset=offset, role=role, process_to_csv=process_to_csv)

                            fl, preOutPath = get_paths(pd_file)
                            path_to_csv = preOutPath + default_csv_name
                            paths_to_csvs.append(path_to_csv)
                        elif name == "algorand-mempool-monitor":
                            print("Working on algorand mempool")
                            process_to_csv = False
                            data_to_add = True
                            # Stick to csv- format!!!
                            default_csv_name = file + '.csv'
                            # visualize locally
                            # Relevant for the cross-group evaluations
                            file_list.append(file)
                            info_group[file] = {'name': name }
                            info = {file: {'name': name }}
                            profile = name
                            role = group_to_node_to_stacks_mapping[group][node][name][file][0]['role']

                            pd_file = processing_descriptor.ProcessingDescriptor(folder_scene, node, sim, experiment=exp_name, ndn=ndn, dst_ports=[file], info=info, limit=limit, offset=offset, role=role, process_to_csv=process_to_csv)

                            fl, preOutPath = get_paths(pd_file)
                            path_to_csv = preOutPath + default_csv_name
                            paths_to_csvs.append(path_to_csv)
                        else:
                            print("no file define look for other identifiers")
                        # FIXME
                        # Extend by iperf3 and tcpdump in case not defined
                        
                        # Flag so not always this step happens
                        if csv and process_to_csv:
                            start_process(process_endpoint_csv, (pd_file, sema), processes)
                        # Plot single node stuff per node
                        # This is something to specify e.g., algorand round trip
                        if plot and group_id_len == 1 and plot_single:
                            print("plotting for single group")
                            check_files_exist(paths_to_csvs, fl)
                            start_process(process_endpoint_plot, (pd_file, sema), processes)
                        # Currently want to run add only once, otherwise DB is getting larger
                        # Possibly remove DB on each start
                        # NOTE for debug run without -a flag, otherwise DB is growing and the same data are appended multiple times!!
                        # Possible change to rewrite option
                        if add and data_to_add:
                            print("Looking for paths")
                            check_files_exist(paths_to_csvs, fl)
                            # currently reading, since those steps can be separated
                            # Possibly, can be fixed and df can be retrieved
                            df = importCsvExtDnames(path_to_csv)
                            df = unify_format(df, node, name, profile, role)
                            # Insert data
                            name_db = "group_id_" + str(group) + "_" + str(exp_name)
                            inserted = dq.store_in_database(db_path, df, name_db)

                # Plots also base file names on a single node
                if plot and len(groups_to_add) == len(file_list):
                    print("For first plot", file_list, info_group)
                    pd_combined = processing_descriptor.ProcessingDescriptor(folder_scene, node, sim, experiment=exp_name, ndn=ndn, dst_ports=file_list, info=info_group, limit=limit, offset=offset, process_to_csv=process_to_csv)
                    start_process(process_endpoint_plot, (pd_combined, sema), processes)
    
    # # Plot on combined level per group e.g., delay, jitter, ...
    if plot:
        # group
        for group in group_to_node_to_stacks_mapping.keys():
        # Limit here how many groups should be post-processed
            # node
            for node in group_to_node_to_stacks_mapping[group].keys():
                info_group = {}
                file_list = []
                # service
                for name in group_to_node_to_stacks_mapping[group][node].keys():
                    # file
                    for file in group_to_node_to_stacks_mapping[group][node][name].keys():
                        # as a part of the context must provide:
                        # Consider scenario with 1-1 or 1-M
                        # natively decide that if same stack, but different groups, combine together, too
                        file_list.append(file)
                        info_group[file] = {'name': name }
                        group_id_len = group_to_node_to_stacks_mapping[group][node][name][file][0]['group_id_len']
                        if group_id_len == 1 and group in groups_to_add:
                            pd_file = processing_descriptor.ProcessingDescriptor(folder_scene, node, sim,experiment=exp_name, ndn=ndn, dst_ports=[file], info=info, group_nr=group, db_path=db_path, groups_to_add=[group], experiments=[exp_name], limit=limit, offset=offset, delay_format=delay_format, label_format=label_format)
                            start_process(process_stream_plot, (pd_file, sema), processes)
                    if group_id_len > 1 and len(groups_to_add) == len(file_list):
                        # sys.exit(0)
                        pd_combined = processing_descriptor.ProcessingDescriptor(folder_scene, node, sim, experiment=exp_name, ndn=ndn, dst_ports=file_list, info=info_group, group_nr=group, db_path=db_path, groups_to_add=groups_to_add, experiments=[exp_name], limit=limit, offset=offset, delay_format=delay_format, label_format=label_format)
                        print("Plotting combined views")
                        start_process(process_stream_plot, (pd_combined, sema), processes)
                        # Break for the sake of running the loop only for a single node, not all of them
                        break
                else:
                    continue
                break
            else:
                continue
            break
    return group_to_node_to_stacks_mapping, group_to_node_file_mapping, fl

def process_exp_cross(folder_scene, db_path, group_experiments, process_variables, group_to_node_to_stacks_mappings, group_to_node_file_mappings, fl):
    print(group_experiments)
    print(group_experiments[0])
    exp_name = group_experiments[0]
    group_to_node_to_stacks_mapping = group_to_node_to_stacks_mappings[exp_name]
    group_to_node_file_mapping = group_to_node_file_mappings[exp_name]
    sema = Semaphore(concurrent_limit)
    # grouping relevant variables
    groups_to_add = process_variables['groups_to_add']
    groups_to_add_cross = process_variables['groups_to_add_cross']
    # visualization related variables
    limit = process_variables['limit']
    offset = process_variables['offset']
    delay_format = process_variables['delay_format']
    label_format = process_variables['label_format']

    processes = []

    # Waiting for all relevant tables to be present before querying them
    # Can be updated by additional check of relevant tables for the given cross experiment information
    list_of_tables = {}
    for experiment in group_experiments:
        list_of_tables[experiment] = {}
        list_of_tables[experiment]["delay"] = []
        for group_in_cross in groups_to_add_cross:
            # Maybe in the future might be more tables
            table_name = "delay_jitter_" + str(group_in_cross) + "_" + experiment
            list_of_tables[experiment]["delay"].append(table_name)
    check_table_exist(list_of_tables, fl, db_path)

    # Might have to here and see if database is ready
    if plot:
        # group
        for group in group_to_node_to_stacks_mapping.keys():
            # Limit here how many groups should be post-processed
            # node
            node_round = 0
            for node in group_to_node_to_stacks_mapping[group].keys():
                info_group = {}
                file_list = []
                # service
                for name in group_to_node_to_stacks_mapping[group][node].keys():
                    # file
                    for file in group_to_node_to_stacks_mapping[group][node][name].keys():
                        # as a part of the context must provide:
                        # Consider scenario with 1-1 or 1-M
                        # natively decide that if same stack, but different groups, combine together, too
                        file_list.append(file)
                        info_group[file] = {'name': name }
                        group_id_len = group_to_node_to_stacks_mapping[group][node][name][file][0]['group_id_len']
                        if group_id_len == 1 and group in groups_to_add and node_round == 0:
                            info = {file: {'name': name }}
                            print("Going with the single", group_experiments)
                            pd_file = processing_descriptor.ProcessingDescriptor(folder_scene, node, sim, ndn=ndn, dst_ports=[file], info=info, group_nr=group, db_path=db_path, groups_to_add=[group], experiment=exp_name, experiments=group_experiments, limit=limit, offset=offset, delay_format=delay_format, label_format=label_format)
                            start_process(process_stream_plot, (pd_file, sema), processes)
                        # Optimization for cross-experiment visualizations based on the group_to_add_cross
                    if group_id_len > 1 and len(groups_to_add_cross) == len(file_list[:len(groups_to_add_cross)]):
                        print("here ready to cross", file_list, len(file_list))
                        # prepares only relevant file names for cross groups
                        file_list = []
                        for groupi in group_to_node_file_mapping.keys():
                            for filei in group_to_node_file_mapping[groupi][node]:
                                file_list.append(filei)
                        pd_combined = processing_descriptor.ProcessingDescriptor(folder_scene, node, sim, ndn=ndn, dst_ports=file_list[:len(groups_to_add_cross)], info=info_group, group_nr=group, db_path=db_path, groups_to_add=groups_to_add_cross, experiments=group_experiments, limit=limit, offset=offset, delay_format=delay_format, label_format=label_format)

                        print("Plotting combined views in here", group_experiments)
                        start_process(process_stream_plot, (pd_combined, sema), processes)
                        # Break for the sake of running the loop only for a single node, not all of them
                        break
                else:
                    # For the same group, we dont need to run the combined experiments on the different nodes
                    node_round = node_round + 1
                    continue
                break
            else:
                continue
            break

    # Extend for post-process of plots local
    # No need to modify anything on that front, just store in the csvs and read from DB for further works
    # Add a flag to either plot or not to plot
    # For minimal diffs, can do it on the csv data not on the DB - in the future can be extended

# processing for NDN only
# FIXME - update to the same pipeline
def process_ndn(folder_scene, nodes, net, stack, exp):
    exp_name = exp['name']
    global concurrent_limit, ndn
    sema = Semaphore(concurrent_limit)
    processes = []
    # first parse probe pcaps for all nodes
    # it parses probe tcpdumps and creates individual csv's for each name
    for node in nodes['node_mapping'].keys():
        pd = processing_descriptor.ProcessingDescriptor(folder_scene, exp_name, node, '', sim, ndn=True)
        start_process(process_endpoint_csv, (pd, sema), processes)

    for p, _ in processes:
        p.join()
    processes = []

    for node, services in stack['services'].items():
        pd = processing_descriptor.ProcessingDescriptor(folder_scene, exp_name, node, '', sim, ndn=True, dst_ports=[])
        for service in services:
            service_name = service['name']
            if service_name in ['ndn-traffic']:
                # we parse directly from tcpdump_probe, unlike normal iperf/send_udp individual tcpdumps for each service
                # so can not determine service name while parsing from tcpdump_probe
                # I don't update info dictionary of pd here, service name of any service of ndn will be assumed 'ndn' (for csv naming purposes)
                # because even if 2 different services use NDN, what matters only is the content name 
                content = service['content']
                role = service['role']
                pd.dst_ports.append(content)
            else:
                continue  # ignore unknown services
        # plot data that does not need correlating
        start_process(process_endpoint_plot, (pd, sema), processes)

    streams = []

    # the loop checks every node pair, to see if they have packets belonging to same name, if so plots/correlates them
    for node, services in stack['services'].items():
        # first loop is for 'source' nodes
        sources = []
        for service in services:
            service_name = service['name']
            if service_name in ['ndn-traffic'] and service['role'] == 'source':
                sources.append(service['content'])
        for node2, services2 in stack['services'].items():
            # second loop is for 'client' nodes
            dst_ports = []
            if node2 == node:
                continue
            for service2 in services2:
                service_name = service2['name']
                # if node2 is the client of a name that the node is source of, to correlate them and create delay csv's
                if service_name in ['ndn-traffic'] and service2['role'] == 'client' and service2['content'] in sources:
                    dst_ports.append(service2['content'])
                    pd1 = processing_descriptor.ProcessingDescriptor(folder_scene, exp_name, node, '', sim, ndn=True,
                                                                     dst_ports=[dst_ports[-1]])
                    pd2 = processing_descriptor.ProcessingDescriptor(folder_scene, exp_name, node2, '', sim, ndn=True,
                                                                     dst_ports=[dst_ports[-1]])
                    start_process(process_stream_csv, (pd1, pd2, sema), processes)
            if dst_ports != []:
                # store pd's with all names in the dst_ports array, to plot them together 
                pdAll1 = processing_descriptor.ProcessingDescriptor(folder_scene, exp_name, node, '', sim, ndn=True,
                                                                    dst_ports=dst_ports)
                pdAll2 = processing_descriptor.ProcessingDescriptor(folder_scene, exp_name, node2, '', sim, ndn=True,
                                                                    dst_ports=dst_ports)
                streams.append((pdAll1, pdAll2))

    for p, _ in processes:
        p.join()
    processes = []

    for pd1, pd2 in streams:
        start_process(process_stream_plot, (pd1, pd2, sema), processes)

    for p, _ in processes:
        p.join()
    processes = []


def process(scene, folder_scene):
    '''loop through experiments of a scenario'''
    fl = folder_scene + '/pythonLog.txt'

    global node_name, experiment_name, ndn

    # Create database 
    db_path = folder_scene + "/scenario.sqlite"
    dq.create_connection(db_path)
    print("Database successfully created")
    with open(fl, "a") as myFile:
        print('\n\nStarting Evaluation...\n', file=myFile)
    startTime = time.time()

    nodes = av.get_nodes(scene)

    # extract the name of the current node
    for name_num, inventory_name in nodes['node_mapping'].items():
        if inventory_name == node_name:
            node_name = name_num
            break
    network_processed = av.get_network_processed(scene)
    stacks_with_service_defaults = av.get_stacks_with_service_defaults(scene)
    # actions = av.get_actions(scene)
    experiments = av.get_experiments(scene)

    process_values = av.get_process(scene)
    process_variables = {}
    for process in process_values:
        for key in process:
            print(process, process[key])
            process_variables[key] = process[key]
    # check if experiment is a ndn experiment
    if 'ndn' in nodes.keys() and nodes['ndn'] == True:
        ndn = True

    # Extract the cross experiment information defined in the 04-experiment.yml
    # Group accordingly 
    group_experiments = {}
    for exp in experiments['experiments']:
        exp_groups = 0
        try:
            # Not always present (does not have to be)
            # Exp group is needed to be able to match various results
            exp_groups = exp['exp_group']
        except KeyError:
            print('Exp group not found for experiment', exp_groups)
        else:
            exp_groups = exp['exp_group']
        
        if exp_groups != 0:
            for exp_group in exp_groups:
                if exp_group not in group_experiments.keys():
                    print("Experiment group", exp_group, type(exp_group))
                    group_experiments[exp_group] = []
            exp_names = group_experiments[exp_group]
            exp_names.append(exp['name'])
            group_experiments[exp_group] = exp_names
        else:
            print("No experiment found")
    group_to_node_to_stacks_mappings = {}
    group_to_node_file_mappings = {}
    for exp in experiments['experiments']:
        group_to_node_to_stacks_mappings[exp['name']] = {}
        group_to_node_file_mappings[exp['name']] = {}
        if process_on_node and exp['name'] != experiment_name:
            continue
        net = network_processed['network'][exp['network']]
        stack = stacks_with_service_defaults['stacks'][exp['stack']]
        # action = actions['actions'][exp['action']]
        # if it is an ndn experiment call ndn processing
        if ndn:
            process_ndn(folder_scene, nodes, net, stack, exp)
        group_to_node_to_stacks_mappings[exp['name']], group_to_node_file_mappings[exp['name']], fl = process_exp(folder_scene, nodes, net, stack, exp, db_path, process_variables)

    for group_experiment in group_experiments:
        process_exp_cross(folder_scene, db_path, group_experiments[group_experiment], process_variables, group_to_node_to_stacks_mappings, group_to_node_file_mappings, fl)
    with open(fl, "a") as myFile:
        print('Evaluation took:', time.time() - startTime, file=myFile)


def parse_cli(args):
    """Parse command line arguments """
    parser = argparse.ArgumentParser(prog='process', description='Convert pcaps to csv and create graphs')
    parser.add_argument('scene', help='Scenario')
    parser.add_argument('-f', '--folder_scene', help='Scenario folder with result files to process')
    parser.add_argument('-d', '--directory', default='../../plays', help='EnGINE plays folder')
    parser.add_argument('-c', '--csv', action='store_true', help='Create CSV files')
    parser.add_argument('-a', '--add', action='store_true', help='Add CSVs to database')
    parser.add_argument('-p', '--plot', action='store_true', help='Create plot files')
    parser.add_argument('-s', '--sim', action='store_true', help='Do simulation specific processing')
    parser.add_argument('-pn', '--process_on_node', action='store_true', help='Process on nodes')
    parser.add_argument('-n', '--node_name', help='Name of the node if parsing on nodes')
    parser.add_argument('-e', '--experiment_name', help='Name of the experiment if parsing on nodes')
    parser.add_argument('-i', '--isolated_cores', default='0', help='Number of isolated cores for scenario')
    return parser.parse_args(args)


def main():
    parser_args = parse_cli(sys.argv[1:])
    scene = parser_args.scene
    folder_scene = parser_args.folder_scene
    directory = parser_args.directory

    global csv, plot, add, sim, node_name, process_on_node, experiment_name, num_isolated_cores
    num_isolated_cores = int(parser_args.isolated_cores)
    csv = parser_args.csv
    add = parser_args.add
    plot = parser_args.plot
    sim = parser_args.sim
    process_on_node = parser_args.process_on_node
    node_name = parser_args.node_name
    experiment_name = parser_args.experiment_name

    av.set_path_to_engine(directory)

    process(scene, folder_scene)


if __name__ == "__main__":
    main()
