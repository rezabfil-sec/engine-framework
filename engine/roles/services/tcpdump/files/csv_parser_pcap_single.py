#!/usr/bin/env python3

# Parse pcap files to csv files

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
    # printing the percentage to log file is commented out as it clutters the log file a lot
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
    fileName = processing_descriptor.find_file_name('tcpdump_' + dumpName + '_' + processing_descriptor.iface + '.pcap')
    pcap = ppcap.Reader(filename=fileName) # Loads pcap with pypacker
    return pcap, fileName

def init_general(processing_descriptor):
    ''' Initialize general analysis '''
    fl = processing_descriptor.log_file() # log file
    preOutPath = processing_descriptor.node_path() # post-processing result directory
    # Create the results directory for experiment and node if non existent
    if not os.path.exists(preOutPath):
        os.makedirs(preOutPath, exist_ok=True)
    return fl, preOutPath

def init_single(fl, processing_descriptor, dumpName, limPktNum=-1):
    ''' Initialize analysis of a single pcap file '''
    with open(fl, "a") as myFile:
        print('Parsing PCAP for', processing_descriptor.experiment, processing_descriptor.node, 'interface', processing_descriptor.iface, 'dump', dumpName, end='...\n', file=myFile)
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

def to_dict(pkt, packetLengthCorrection, dst_port, pd, p, ts, buf):
    ''' Store packet contents in a dict '''

    # this part is to get the packet size, I couldn't find a way to do this in pypacker easily
    p._fh.seek(-1 * len(buf) - 16, 1)
    buf2 = p._fh.read(16)
    p._fh.seek(len(buf), 1)
    dx = p._callback_unpack_meta(buf2)

    d = {}
    d['timestamp_ns'] = ts
    d['packet_size_bytes'] = dx[3] - packetLengthCorrection
    # collect the service specific fields and add it to the dictionary variable
    if pd.service_name(dst_port) == 'iperf':
        process_iperf.to_dict(d, pkt)
    if pd.service_name(dst_port) == 'send_udp':
        process_send_udp.to_dict(d, pkt)
    return d

def parse_single_pcap(processing_descriptor, limPktNum=-1):
    ''' helper function to call parse_single_pcap(processing_descriptor, dst_port, fl, preOutPath, limPktNum=-1) '''
    fl, preOutPath = init_general(processing_descriptor)
    if len(processing_descriptor.dst_ports) == 1:
        dst_port = processing_descriptor.dst_ports[0]
    else:
        print("Please call parseFlowPcapIperfFlowsNodeIFace with a PD having exactly one port.")
    parse_single_pcap(processing_descriptor, dst_port, fl, preOutPath, limPktNum)

def parse_single_pcap(processing_descriptor, dst_port, fl, preOutPath, limPktNum=-1):
    ''' parses a single pcap using pypacker '''
    csvPath = preOutPath + 'csv-' + processing_descriptor.service_name(dst_port) + '-single_' + str(dst_port) + '_' + processing_descriptor.iface + '.csv'
    if os.path.isfile(csvPath):
        return

    # load the pcap file
    progressProc, startTime, p, modOp = init_single(fl, processing_descriptor, str(dst_port), limPktNum)

    rows = []

    # Iterate over all packets that are of interest to us
    for index, (ts, buf) in enumerate(p):
        pkt = ethernet.Ethernet(buf)
        rows.append(to_dict(pkt, 4 if processing_descriptor.sim else 0, dst_port, processing_descriptor, p, ts, buf)) # We put the dict to our results list
        # progressProc = progress(index, fl, progressProc, modOp)

    printProgress(fl, 100)
    # don't create csv if the packet number in the pcap is too low to prevent crashes later when plotting
    if len(rows) < 2:
        with open(fl, "a") as myFile:
            print(csvPath, ' only has less than 2 packets, ignoring', file=myFile)
        return
    # Based on our results list we create a dataframe and export to csv
    # the csv name is: csv-<service name>-single_<port name>_<iface name>.csv
    df = pandas.DataFrame(rows)
    df.to_csv(csvPath)
    printComplete('Single Flow PCAP Analysis complete!', startTime, fl)

def parse_separate_pcaps(processing_descriptor, limPktNum=-1):
    """
    Parses pcap(s) to csv(s)
    Assumes a separate pcap file per stream, i.e. given server port, containing UDP packets for given destination port only. Assumes "p<dst_port>"" to be used for tcpdump service file name. Writes one csv file per pcap.
    """
    fl, preOutPath = init_general(processing_descriptor)
    startTimeGlob = time.time()
    with open(fl, "a") as myFile:
        print('Parsing PCAPs for', processing_descriptor.experiment, processing_descriptor.node, 'interface', processing_descriptor.iface, end='...\n', file=myFile)

    # for each port in dst_ports, find the corresponding pcap and process it
    # the name of the corresponding pcap should be: tcpdump_<port name>_<iface name>.pcap
    for dst_port in processing_descriptor.dst_ports:
        dumpName = str(dst_port)
        fileName = processing_descriptor.find_file_name('tcpdump_' + dumpName + '_' + processing_descriptor.iface + '.pcap')
        if fileName == '':
            with open(fl, "a") as myFile:
                print('tcpdump_' + dumpName + '_' + processing_descriptor.iface + '.pcap does not exist', end='...\n', file=myFile)
            continue    
        parse_single_pcap(processing_descriptor, dst_port, fl, preOutPath, limPktNum)

    printComplete('Analysis of all ' + str(len(processing_descriptor.dst_ports)) + ' PCAPs complete!', startTimeGlob, fl)

def main():
    pd = processing_descriptor.create_processing_descriptor_cli('csv_parser_pcap_single', 'Parse pcap to csv')
    pd.print_info(True)

    # Call the parsing function
    parse_separate_pcaps(pd)
    # parsePcapIperfFlowsNodeIFace(pd)

if __name__ == "__main__":
    main()
