#!/usr/bin/env python3

# Merge csv files of stream end points with added delay and jitter

import numpy as np
import pandas as pd
import sys
import time
import os
import statistics

sys.path.append("../../../process/files")
import processing_descriptor

sys.path.append("../../services/send_udp/files")
sys.path.append("../../../services/send_udp/files")
import process_send_udp
sys.path.append("../../services/iperf/files")
sys.path.append("../../../services/iperf/files")
import process_iperf
sys.path.append("../../services/algorand/files")
sys.path.append("../../../services/algorand/files")
import process_algorand
sys.path.append("../../services/ethereum/files")
sys.path.append("../../../services/ethereum/files")
import process_ethereum


def check_csvs(pd_end, pd_st):
    '''
    deletes port from dst_ports if the corresponding csv does not exist (means tcpdump collection was not enabled for that port)
    also deletes port if the port does not have a csv on the other endpoint
    '''
    for pd in [pd_end, pd_st]:
        for dst_port in pd.dst_ports[:]:
            fileName = pd.node_path() + 'csv-' + pd.service_name(dst_port) + '-single_' + str(dst_port) + '_' + pd.iface + '.csv'
            if not os.path.isfile(fileName):
                pd.dst_ports.remove(dst_port)
                with open(pd.log_file(), "a") as myFile:
                    print('csv-' + pd.service_name(dst_port) + '-single_' + str(dst_port) + '_' + pd.iface + '.csv', ' does not exist.', end='...\n', file=myFile)
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
    if processing_descriptor.service_name(dst_port) is None:
        return None
    fileName = processing_descriptor.find_file_name('csv-' + processing_descriptor.service_name(dst_port) + '-single_' + str(dst_port) + '_' + processing_descriptor.iface + '.csv') #processing_descriptor.iface + 'PcapFlowIperf' + str(dst_port) + '.csv')
    if fileName == '':
        return None
    df = pd.read_csv(fileName, index_col=0) # Loads the CSV
    df = df.rename(columns={'timestamp_ns' : 'timestamp_ns_' + processing_descriptor.node_num(), 'timestamp_nanoseconds' : 'timestamp_nanoseconds ' + processing_descriptor.node_num(), 'packet_size_bytes' : 'packet_size_bytes ' + processing_descriptor.node_num()})
    return df

def init(processing_descriptor_end, processing_descriptor_start):
    ''' helper function for logging '''
    startTimeGlob = time.time()
    fl = processing_descriptor_end.log_file()
    with open(fl, "a") as myFile:
        print('Parsing data to get delay, jitter and packets for', processing_descriptor_end.experiment, 'between ' + processing_descriptor_end.node, processing_descriptor_end.iface, 'and '+processing_descriptor_start.node, processing_descriptor_start.iface, end='...\n', file=myFile)
    return startTimeGlob, fl

def save_delay_and_jitter_to_csv(processing_descriptor_end, processing_descriptor_start, service_used=''):
    """
        Extracts e2e delay and jitter from results and exports it to csv

        For each port in given port list, merges pcap based csv files for given start and end node interfaces.
        Writes new csv file per port.
        Files read: <pathToFolder>/<experimentName>/node-<(start|end)NodeNum/csv-<service>-single_<dst_port>_<iFace>.csv
        File(s) written: <pathToFolder>/<experimentName>/node-<endNodeNum>/csv-<service>-combined_<dst_ports>_<endiFace>.csv
    """
    if service_used == 'algorand':
        print("Algorand in the house")
    if service_used  == 'ethereum':
        print("Ethereum in the house")
    else:
        check_csvs(processing_descriptor_end, processing_descriptor_start)
    if len(processing_descriptor_end.dst_ports) == 0:
        print("No dst ports")
        return
    startTimeGlob, fl = init(processing_descriptor_end, processing_descriptor_start)
    for dst_port in processing_descriptor_end.dst_ports:
        print("dst_port", dst_port)
        startTime = time.time()
        with open(fl, "a") as myFile:
            print('Analyzing', end='...\n', file=myFile)
        printProgress(fl, 0)
        df = importCsvExtDnames(processing_descriptor_start, processing_descriptor_start.dst_ports[0])# Import source csv
        if df is None:
            return
        printProgress(fl, 10)
        df2 = importCsvExtDnames(processing_descriptor_end, processing_descriptor_end.dst_ports[0]) # Import target csv
        if df2 is None:
            return
        printProgress(fl, 20)
        dst_port = processing_descriptor_end.dst_ports[0]
        print("Service", processing_descriptor_end.service_name(dst_port))
        if processing_descriptor_end.service_name(dst_port) == 'iperf':
            print("working on iperf")
            merge = process_iperf.merge
        elif processing_descriptor_end.service_name(dst_port) == 'send_udp':
            print("working on send_udp")
            merge = process_send_udp.merge
        elif processing_descriptor_end.service_name(dst_port) == 'tcpdump' and \
                "algorand-track-msg" in processing_descriptor_end.node_path():
            merge = process_algorand.merge
        elif processing_descriptor_end.service_name(dst_port) == 'tcpdump' and \
                "ethereum-demo" in processing_descriptor_end.node_path():
            merge = process_ethereum.merge
        elif processing_descriptor_end.service_name(dst_port) == 'tcpdump':
            if "iperf" in processing_descriptor_end.node_path():
                print("tcpdump and iperf")
                continue
            elif "send_udp":
                print("tcpdump and send_udp")
                continue
        else:
            raise NotImplementedError("Service not implemented")

        pd.set_option('display.max_columns', None)
        evalDF = pd.merge(df, df2, how='inner', on=merge)
        printProgress(fl, 30)
        retDF = pd.DataFrame()
        #retDF['Timestamp'] = evalDF.dropna()['timestamp_full ' + str(processing_descriptor_start.node_num())]
        retDF['timestamp_ns'] = evalDF.dropna()['timestamp_ns_' + str(processing_descriptor_start.node_num())]
        printProgress(fl, 40)
        #retDF['Delay'] = evalDF.dropna().apply(lambda row: (row['timestamp_full ' + str(processing_descriptor_end.node_num())] - row['timestamp_full ' + str(processing_descriptor_start.node_num())] - (0 if processing_descriptor_end.sim else 37)) * 1e9, axis=1).dropna()
        # Due to PTP TAI UTC difference, it is important to check the status
        # One Physical interfaces works well, is an issue for no PTP4L ifaces e.g., SR-IOV ifaces
        retDF['delay_ns'] = evalDF.dropna().apply(lambda row: abs(row['timestamp_ns_' + str(processing_descriptor_end.node_num())] - row['timestamp_ns_' + str(processing_descriptor_start.node_num())]), axis=1).dropna()
        avg = statistics.mean(retDF['delay_ns'])
        if avg > (37 * 10 ** 9):
            print("Lower by TAI", avg)
            retDF['delay_ns'] = retDF['delay_ns'] - (37 * 10 ** 9)
            # print(statistics.mean(retDF['delay_ns']))
        else:
            print("TAI not present", avg)
        # retDF['delay_ns'] = evalDF.dropna().apply(lambda row: abs(row['timestamp_ns_' + str(processing_descriptor_end.node_num())] - row['timestamp_ns_' + str(processing_descriptor_start.node_num())] - (0 if processing_descriptor_end.sim or utc_tai else (37 * 10 ** 9))), axis=1).dropna()
        printProgress(fl, 50)
        #retDF['Jitter'] = retDF['Delay'].diff()
        retDF['jitter_ns'] = retDF['delay_ns'].diff()
        #retDF.at[0, 'Jitter'] = 0
        retDF.at[0, 'jitter_ns'] = 0
        printProgress(fl, 60)

        #tempDF = evalDF[evalDF['timestamp_full ' + str(processing_descriptor_end.node_num())].isna()]
        tempDF = evalDF[evalDF['timestamp_ns_' + str(processing_descriptor_end.node_num())].isna()]
        printProgress(fl, 70)
        tempDF2 = pd.DataFrame()
        #tempDF2['Timestamp Loss'] = tempDF['timestamp_full ' + str(processing_descriptor_start.node_num())]
        tempDF2['timestamp_loss_ns'] = tempDF['timestamp_ns_' + str(processing_descriptor_start.node_num())]
        printProgress(fl, 80)
        if processing_descriptor_end.service_name(dst_port) == 'iperf':
            sequence = process_iperf.sequence
        elif processing_descriptor_end.service_name(dst_port) == 'send_udp':
            sequence = process_send_udp.sequence
        elif processing_descriptor_end.service_name(dst_port) == 'tcpdump' and \
                "algorand-track-msg" in processing_descriptor_end.node_path():
            sequence = process_algorand.sequence
        else:
            print("TODO")
        #tempDF2['LostSeq'] = tempDF[sequence]
        tempDF2['lost_seq'] = tempDF[sequence]
        printProgress(fl, 90)
        retDF = pd.concat([retDF, tempDF2], axis=1)
        printProgress(fl, 100)

        # Export to CSV
        outPath = processing_descriptor_end.node_path() + 'csv-' + processing_descriptor_end.service_name(dst_port) + '-combined_' + str(dst_port) + '_' + processing_descriptor_end.iface + '.csv' #processing_descriptor_end.iface + 'DelayAndJitterFlowIperf' + str(dst_port) + '.csv'
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
