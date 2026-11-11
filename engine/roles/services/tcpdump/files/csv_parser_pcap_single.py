#!/usr/bin/env python3

# Parse pcap files to csv files

import enum
from fileinput import filename
import os
import pandas
import sys
import time
from pypacker import ppcap
from pypacker.layer12 import ethernet
import csv

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


def printLog(fl, message):
    ''' helper function for loggin '''
    with open(fl, "a") as myFile:
        print(message, end='\r', file=myFile)

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
    # return progString

def progress(index, fl, progressProc, modOp):
    ''' Log progress string and increment for every modOpth packet '''
    if modOp != 0 and ((index + 1) % modOp == 0):
        progressProc += 1
        printProgress(fl, progressProc)
    return progressProc

def printComplete(string, sTime, fl):
    ''' Logs elapsed time to process a pcap'''
    with open(fl, "a") as myFile:
        print(string + ' It took', time.time() - sTime, 's\n', file=myFile)

def loadPcap(processing_descriptor, dumpName, limPktNum=-1):
    ''' This function loads the PCAP file for the corresponding node and interface '''
    fileName = processing_descriptor.find_file_name('tcpdump_' + dumpName + '_*' + '.pcap')
    pcap = ppcap.Reader(filename=fileName) # Loads pcap
    return pcap, fileName

def init_general(processing_descriptor):
    ''' Initialize general analysis '''
    fl = processing_descriptor.log_file() # log file
    preOutPath = processing_descriptor.node_path() # export directory
    # Create the exports directory for experiment and node if non existent
    if not os.path.exists(preOutPath):
        os.makedirs(preOutPath, exist_ok=True)
    return fl, preOutPath

def init_single(fl, processing_descriptor, dumpName, limPktNum=-1):
    ''' Initialize analysis of a single pcap file '''
    with open(fl, "a") as myFile:
        print('Parsing PCAP for', processing_descriptor.experiment, processing_descriptor.node, 'dump', dumpName, end='...\n', file=myFile)
        print('Loading PCAP...', file=myFile)
    progressProc = 0
    startTime = time.time()
    p, fN = loadPcap(processing_descriptor, dumpName, limPktNum) # Load corresponding pcap

    # Get information for progress control
    pcapLenCheck = os.popen('capinfos ' + fN + ' | grep \"Number of packets = \"')
    pcapLen = int(pcapLenCheck.read().split(' = ')[-1])
    # with open(fl, "a") as myFile:
        # print('Pcap last =', p[-1], file=myFile)
        # print('Pcap len =', pcapLen, file=myFile)
    modOp = int(pcapLen/100)
    if modOp == 0:
        modOp = 1

    with open(fl, "a") as myFile:
        print('Starting analysis...', file=myFile)
    printProgress(fl, progressProc)

    return progressProc, startTime, p, modOp

def to_dict(pkt, packetLengthCorrection, dst_port, pd, p, ts, buf, fl):
    ''' Store packet contents in a dict '''

    # this part is to get the packet size, I couldn't find a way to do this in pypacker easily
    p._fh.seek(-1 * len(buf) - 16, 1)
    buf2 = p._fh.read(16)
    p._fh.seek(len(buf), 1)
    dx = p._callback_unpack_meta(buf2)

    d = {}
    tsmp = str(ts)
    # d['timestamp_seconds'] = int(tsmp[:-9])
    # d['timestamp_nanoseconds'] = int(tsmp[-9:])
    d['timestamp_ns'] = int(tsmp[:-9]) * 10 ** 9 + int(tsmp[-9:])
    d['packet_size_bytes'] = dx[3] - packetLengthCorrection
    if pd.profile == 'iperf3':
        process_iperf.to_dict(d, pkt)
    if pd.profile == 'send_udp':
        process_send_udp.to_dict(d, pkt)
    if pd.profile == 'algorand':
        # Important to used masked in the name of the tcpdump
        with open(fl, "a") as myFile:
            print('In algo msg', pd.dst_ports[0],  file=myFile)
        # FIXME for other msg types
        format = pd.format
        # extend here by additional msg types
        for msg_type in pd.msg_types:
            # This will correlate AV messages only! For other messages, implement new 'to_dict_*' methods.
            process_algorand.to_dict_AV(d, pkt, format, msg_type)
            # This will output a dictionary with entries containing the timestamps of each end of the round. It can be later used to plot the delay between consecutive rounds. We create this data based on the sender packets.
            if pd.role == "source" and msg_type == "av":
                process_algorand.to_dict_AV_rounds(d, pkt, format)
            if d['algorand_payload'] == 0:
                # return empty {} so later on does not get added to a DB
                return {}
                # return d
    if pd.profile == 'ethereum':
        format = pd.format

        with open(fl, "a") as myFile:
            print('In ethreuem msg', pd.dst_ports[0],  file=myFile)
            process_ethereum.to_dict_transactions_timestamps(d, pkt, format)

    return d

def parse_single_pcap(processing_descriptor, limPktNum=-1):
    ''' helper function to call parse_single_pcap(processing_descriptor, dst_port, fl, preOutPath, limPktNum=-1) '''
    fl, preOutPath = init_general(processing_descriptor)
    if len(processing_descriptor.dst_ports) == 1:
        dst_port = processing_descriptor.dst_ports[0]
    else:
        print("Please call parseFlowPcapIperfFlowsNodeIFace with a PD having exactly one port.")
    parse_single_pcap(processing_descriptor, dst_port, fl, preOutPath, limPktNum)


def parse_single_ethereum_pcap(processing_descriptor, preOutPath, dst_port, fl, p):
    csvTransactionsPath = preOutPath + 'csv-' + processing_descriptor.service_name(dst_port) + '-transactions-times_' + str(dst_port) +  '.csv'
    if os.path.isfile(csvTransactionsPath) :
        return
    process_ethereum.d_sent_eth_transactions = {}
    process_ethereum.d_pended_eth_transactions = {}
    rows = iterate_over_all_packets(p, dst_port, processing_descriptor, fl)

    if process_ethereum.d_sent_eth_transactions or process_ethereum.d_pended_eth_transactions:
        df_txs = pandas.DataFrame.from_dict(process_ethereum.get_dist_transactions_pandas())
        df_txs.to_csv(csvTransactionsPath)

    return rows
    

def parse_single_algorand_pcap(processing_descriptor,preOutPath, dst_port, fl, p ):

        # such paths could be defined in process.py or the process of a corresponding service directly
    csvRoundsPath = preOutPath + 'csv-' + processing_descriptor.service_name(dst_port) + '-algo-rounds_' + str(dst_port) + '.csv'

    if os.path.isfile(csvRoundsPath):
        return
    process_algorand.d_AV_rounds = {}
   
    with open(fl, "a") as myFile:
        print('before algo process before',  file=myFile)
    rows = iterate_over_all_packets(p, dst_port, processing_descriptor, fl)

    if process_algorand.d_AV_rounds:
        with open(fl, "a") as myFile:
            print('In algo process after',  file=myFile)
        df_rounds = pandas.DataFrame.from_dict(process_algorand.get_dist_AV_rounds_pandas())
        print(df_rounds)
        df_rounds.to_csv(csvRoundsPath)

    return rows


def iterate_over_all_packets(p, dst_port, processing_descriptor, fl):
    rows = []

    for index, (ts, buf) in enumerate(p):
        pkt = ethernet.Ethernet(buf)
        row = to_dict(pkt, 4 if processing_descriptor.sim else 0, dst_port, processing_descriptor, p, ts, buf, fl)
        if bool(row):
            # not empty sequence number
            # relevant for e.g., large blockchain data
            # possible change to keep noise for some data calculation
            rows.append(row) # We put the dict to our results list
    return rows


def parse_single_pcap(processing_descriptor, dst_port, fl, preOutPath, limPktNum=-1):
    ''' parses a single pcap using pypacker '''
    print(processing_descriptor.service_name(dst_port)+'1')
    print(str(dst_port))
    csvPath = preOutPath + 'csv-' + processing_descriptor.service_name(dst_port) + '-single_' + str(dst_port) + '.csv'
    
    if os.path.isfile(csvPath):
        return
    if str(dst_port).isdigit():
        name = 'p' + str(dst_port)
    else:
        name = str(dst_port)
    progressProc, startTime, p, modOp = init_single(fl, processing_descriptor, name, limPktNum)
    if processing_descriptor.profile == 'algorand':
      rows= parse_single_algorand_pcap(processing_descriptor, preOutPath, dst_port, fl, p)
    elif processing_descriptor.profile == 'ethereum':
        rows = parse_single_ethereum_pcap(processing_descriptor, preOutPath, dst_port, fl, p)
    else :
        rows = iterate_over_all_packets(p, dst_port, processing_descriptor, fl)
    printProgress(fl, 100)
    if len(rows) < 2:
        with open(fl, "a") as myFile:
            print(csvPath, ' only has less than 2 packets, ignoring', file=myFile)
        return
    # Based on our results list we create a dataframe and export to csv
    # with open(csvPath, 'w', newline='') as csvfile:
    #     writer = csv.DictWriter(csvfile, fieldnames=rows[0].keys(), dialect='excel')
    #     writer.writeheader()
    #     writer.writerows(rows)
    df = pandas.DataFrame(rows)
    df.to_csv(csvPath) #processing_descriptor.iface+'PcapFlowIperf'+str(dst_port)+'.csv') 
    printComplete('Single Flow PCAP Analysis complete!', startTime, fl)

def parse_separate_pcaps(processing_descriptor, limPktNum=-1):
    """
    Parses pcap(s) to csv(s)
    Assumes a separate pcap file per stream, i.e. given server port, containing UDP packets for given destination port only. Assumes "p<dst_port>"" to be used for tcpdump service file name. Writes one csv file per pcap.
    """
    fl, preOutPath = init_general(processing_descriptor)
    startTimeGlob = time.time()
    with open(fl, "a") as myFile:
        print('Parsing PCAPs for', processing_descriptor.experiment, processing_descriptor.node, processing_descriptor.dst_ports, processing_descriptor.msg_types, processing_descriptor.profile, end='...\n', file=myFile)

    for dst_port in processing_descriptor.dst_ports:
        # Update here for tcpdump if not defined
        if str(dst_port).isdigit():
            dumpName = 'p' + str(dst_port)
        else:
            dumpName = str(dst_port)
        # Update here - no need for the iface name, but look for .pcap
        fileName = processing_descriptor.find_file_name('tcpdump_' + dumpName + '_*' + '.pcap')
        if fileName == '':
            with open(fl, "a") as myFile:
                print('tcpdump_' + dumpName + '_' + '.pcap does not exist', end='...\n', file=myFile)
            continue
        parse_single_pcap(processing_descriptor, dst_port, fl, preOutPath, limPktNum)
    printComplete('Analysis of all ' + str(len(processing_descriptor.dst_ports)) + ' PCAPs complete!', startTimeGlob, fl)

# def parsePcapIperfFlowsNodeIFace(processing_descriptor, limPktNum=-1):
#    '''
#        Parses pcap to csvs
#        
#        Assumes single pcap containing packets of all processing_descriptor. Uses given ports to filter packets and write separate csv for each stream.
#    '''
#    fl, preOutPath = init_general(processing_descriptor)
#    progressProc, startTime, p, modOp = init_single(fl, processing_descriptor, 'probe', limPktNum)
#
#    # Prepare result collection
#    rows = {}
#    for dst_port in processing_descriptor.dst_ports:
#        rows[dst_port] = []
#
#    # Iterate over all packets that are of interest to us - the iperf ones.
#    for index, pkt in enumerate(p):
#        if UDP in pkt:
#            if str(pkt[UDP].dport) in processing_descriptor.dst_ports:
#                rows[str(pkt[UDP].dport)].append(to_dict(pkt, 4 if processing_descriptor.sim else 0)) # We put the dict to our results list
#                progressProc = progress(index, fl, progressProc, modOp)
#    
#    printProgress(fl, 100)
#    # Based on our results list we create a dataframe and export to csv
#    for row in rows:
#        df = pandas.DataFrame(rows[row]) 
#        df.to_csv(preOutPath + 'csv-' + pd.service_name(dst_port) + '-single_' + str(dst_port) + '_' + processing_descriptor.iface + '.csv') #processing_descriptor.iface+'PcapFlowIperf'+str(row)+'.csv')
#    printComplete('Analysis complete!', startTime, fl)

def main():
    pd = processing_descriptor.create_processing_descriptor_cli('csv_parser_pcap_single', 'Parse pcap to csv')
    pd.print_info(True)

    # Call the parsing function
    parse_separate_pcaps(pd)
    # parsePcapIperfFlowsNodeIFace(pd)

if __name__ == "__main__":
    main()
