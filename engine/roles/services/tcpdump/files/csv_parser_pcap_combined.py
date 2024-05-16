#!/usr/bin/env python3

# Merge csv files of stream end points with added delay and jitter

import numpy as np
import pandas as pd
import sys
import time
import os
import ndn.encoding as ndn

sys.path.append("../../../process/files")
import processing_descriptor

sys.path.append("../../services/send_udp/files")
sys.path.append("../../../services/send_udp/files")
import process_send_udp
sys.path.append("../../services/iperf/files")
sys.path.append("../../../services/iperf/files")
import process_iperf
sys.path.append("../../services/ndn-traffic/files")
sys.path.append("../../../services/ndn-traffic/files")
import process_ndn_traffic

def check_csvs(pd_end, pd_st):
    '''
    deletes port from dst_ports of processing_descriptorif the corresponding csv does not exist (means tcpdump collection was not 
        enabled for that port or there were no packets in the pcap)
    also deletes port if the port does not have a csv on the other endpoint
    '''
    for pd in [pd_end, pd_st]:
        for dst_port in pd.dst_ports[:]:
            fileName = pd.node_path() + 'csv-' + pd.service_name(dst_port) + '-single_' + pd.get_port(dst_port) + '_' + pd.iface + '.csv'
            if not os.path.isfile(fileName):
                pd.dst_ports.remove(dst_port)
                with open(pd.log_file(), "a") as myFile:
                    print('csv-' + pd.service_name(dst_port) + '-single_' + pd.get_port(dst_port) + '_' + pd.iface + '.csv', ' does not exist.', end='...\n', file=myFile)
    for pd in [pd_end, pd_st]:
        for pd2 in [pd_end, pd_st]:
            if pd != pd2:
                for dst_port in pd.dst_ports[:]:
                    if dst_port not in pd2.dst_ports:
                        pd.dst_ports.remove(dst_port)

def printProgress(fl, progressProc):
    ''' Logs progress string, unused '''
    progString = 'Progress: ['
    for _ in range(progressProc):
        progString += '#'
    for _ in range(100-progressProc):
        progString += ' '
    progString += ']   ' + str(progressProc) + '% Complete'
    # with open(fl, "a") as myFile:
    #     print(progString, end='\r', file=myFile)

def printComplete(string, sTime, fl):
    ''' Logs elapsed time to process a csv'''
    with open(fl, "a") as myFile:
        print(string + ' It took', time.time() - sTime, 's\n', file=myFile)

def importCsvExtDnames(processing_descriptor, dst_port):
    ''' reads csv, renames columns for delay/jitter calculation '''
    fileName = processing_descriptor.find_file_name('csv-' + processing_descriptor.service_name(dst_port) + '-single_' + processing_descriptor.get_port(dst_port) + '_' + processing_descriptor.iface + '.csv') #processing_descriptor.iface + 'PcapFlowIperf' + str(dst_port) + '.csv')
    df = pd.read_csv(fileName, index_col=0) # Loads the CSV
    # rename the columns, add the node number to the column names, so that after merging dataframes of 2 endpoints you can access timestamp on 
    # specific node
    df = df.rename(columns={'timestamp_ns_first': 'timestamp_ns_first_' + processing_descriptor.node_num(), 'timestamp_ns' : 'timestamp_ns_' + processing_descriptor.node_num(), 'timestamp_nanoseconds' : 'timestamp_nanoseconds ' + processing_descriptor.node_num(), 'packet_size_bytes' : 'packet_size_bytes ' + processing_descriptor.node_num()})
    return df

def init(processing_descriptor_end, processing_descriptor_start):
    ''' helper function for logging '''
    startTimeGlob = time.time()
    fl = processing_descriptor_end.log_file()
    with open(fl, "a") as myFile:
        print('Parsing data to get delay, jitter and packets for', processing_descriptor_end.experiment, 'between ' + processing_descriptor_end.node, processing_descriptor_end.iface, 'and '+processing_descriptor_start.node, processing_descriptor_start.iface, end='...\n', file=myFile)
    return startTimeGlob, fl

def save_delay_and_jitter_to_csv(processing_descriptor_end, processing_descriptor_start):
    """
        Extracts e2e delay and jitter from results and exports it to csv

        For each port in given port list, merges pcap based csv files for given start and end node interfaces.
        Writes new csv file per port.
        Files read: <pathToFolder>/<experimentName>/node-<(start|end)NodeNum/csv-<service>-single_<dst_port>_<iFace>.csv
        File(s) written: <pathToFolder>/<experimentName>/node-<endNodeNum>/csv-<service>-combined_<dst_ports>_<endiFace>.csv
    """
    # use check_csvs to delete unnecessary ports from dst_ports of processing_descriptor's
    check_csvs(processing_descriptor_end, processing_descriptor_start)
    if len(processing_descriptor_end.dst_ports) == 0:
        return
    startTimeGlob, fl = init(processing_descriptor_end, processing_descriptor_start)
    for dst_port in processing_descriptor_end.dst_ports:
        startTime = time.time()
        with open(fl, "a") as myFile:
            print('Analyzing port', dst_port, end='...\n', file=myFile)
        printProgress(fl, 0)
        df = importCsvExtDnames(processing_descriptor_start, dst_port)# Import source csv
        printProgress(fl, 10)
        df2 = importCsvExtDnames(processing_descriptor_end, dst_port) # Import target csv
        printProgress(fl, 20)
        # load the merge variable for the service used for the port
        # the rows on the dataframes of endpoints will be merged together if they have the same column values for 
        # the colums in 'merge' variable
        if processing_descriptor_end.service_name(dst_port) == 'iperf':
            merge = process_iperf.merge
        elif processing_descriptor_end.service_name(dst_port) == 'send_udp':
            merge = process_send_udp.merge
        elif processing_descriptor_end.service_name(dst_port) == 'ndn':
            merge = process_ndn_traffic.merge
        else:
            print('Service', processing_descriptor_end.service_name(dst_port), 'not supported')
            continue
        # merge based on columns in 'merge' variable
        evalDF = pd.merge(df, df2, how='inner', on=merge)
        printProgress(fl, 30)
        retDF = pd.DataFrame()
        retDF['timestamp_ns'] = evalDF['timestamp_ns_' + str(processing_descriptor_start.node_num())]
        printProgress(fl, 40)
        # calculate delay
        if processing_descriptor_start.ndn == False:
            retDF['delay_ns'] = evalDF.apply(lambda row: (row['timestamp_ns_' + str(processing_descriptor_end.node_num())] - row['timestamp_ns_' + str(processing_descriptor_start.node_num())]) , axis=1).dropna() #  - (0 if processing_descriptor_end.sim else (37 * 10 ** 9))
        else:
            # for fragmented NDN packets, the delay is the time the last fragment arrived at the end node - time the first fragment left the start node
            retDF['delay_ns'] = evalDF.apply(lambda row: (row['timestamp_ns_' + str(processing_descriptor_start.node_num())] - row['timestamp_ns_first_' + str(processing_descriptor_end.node_num())] if row['type'] == ndn.LpTypeNumber.LP_PACKET 
                                                                        else abs(row['timestamp_ns_' + str(processing_descriptor_start.node_num())] - row['timestamp_ns_' + str(processing_descriptor_end.node_num())])) , axis=1)
        # add NDN specific columns (currently only type of the ndn packet)
        if processing_descriptor_start.ndn:
            retDF['type'] = evalDF['type']
        printProgress(fl, 60)

        # collect the packets that did not arrive at the end node to tempDF
        tempDF = evalDF[evalDF['timestamp_ns_' + str(processing_descriptor_end.node_num())].isna()]
        printProgress(fl, 70)
        tempDF2 = pd.DataFrame()
        tempDF2['timestamp_loss_ns'] = tempDF['timestamp_ns_' + str(processing_descriptor_start.node_num())]
        # add lost packet data to main dataframe
        retDF = pd.concat([retDF, tempDF2], axis=1)
        
        # Export to CSV
        outPath = processing_descriptor_end.node_path() + 'csv-' + processing_descriptor_end.service_name(dst_port) + '-combined_' + processing_descriptor_end.get_port(dst_port) + '_' + processing_descriptor_end.iface + '.csv' #processing_descriptor_end.iface + 'DelayAndJitterFlowIperf' + str(dst_port) + '.csv'
        retDF.to_csv(outPath)
        printProgress(fl, 100)
        printComplete('Analysis for port' + str(dst_port) + 'complete!', startTime, fl)
    printComplete('Analysis complete!', startTimeGlob, fl)

def main():
    pd_end, pd_start = processing_descriptor.create_processing_descriptors_cli('csv_parser_pcap_combined', 'Parse pcap to csv')
    print('Parsing experiment', pd_end.experiment, 'on', pd_start.node, pd_start.iface, pd_end.node, pd_end.iface, 'for UDP flows with target ports', pd_end.dst_ports)

    # Call the parsing function
    save_delay_and_jitter_to_csv(pd_end, pd_start)

if __name__ == "__main__":
    main()
