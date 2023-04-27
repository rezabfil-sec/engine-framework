#!/usr/bin/env python3

# Parse pcap files to csv files

from scapy.all import *

import os
import pandas
import sys
import time

sys.path.append("../../../process/files")
import processing_descriptor

sys.path.append("../../services/send_udp/files")
sys.path.append("../../../services/send_udp/files")
import process_send_udp
sys.path.append("../../services/iperf/files")
sys.path.append("../../../services/iperf/files")
import process_iperf

def loadPcap(processing_descriptor, dumpName, limPktNum=-1):
    ''' This function loads the PCAP file for the corresponding node and interface '''
    fileName = processing_descriptor.find_file_name('tcpdump_' + dumpName + '_' + processing_descriptor.iface + '.pcap')
    # print(fileName)
    pcap = PcapReader(fileName) # Loads pcap
    return pcap, fileName

def printProgress(fl, progressProc):
    ''' Logs progress string '''
    progString = 'Progress: ['
    for _ in range(progressProc):
        progString += '#'
    for _ in range(100-progressProc):
        progString += ' '
    progString += ']   ' + str(progressProc) + '% Complete'
    with open(fl, "a") as myFile:
        print(progString, end='\r', file=myFile)
    # return progString

def progress(index, fl, progressProc, modOp):
    ''' Log progress string and increment for every modOpth packet '''
    if modOp != 0 and ((index + 1) % modOp == 0): 
        progressProc += 1
        printProgress(fl, progressProc)
    return progressProc

def printComplete(string, sTime, fl):
    with open(fl, "a") as myFile:
        print(string + ' It took', time.time() - sTime, 's\n', file=myFile)

def init_general(processing_descriptor):
    ''' Initialize general analysis '''
    fl = processing_descriptor.log_file() # log file
    preOutPath = processing_descriptor.node_path() # export directory
    # Create the exports directory for experiment and node if non existent
    if not os.path.exists(preOutPath):
        os.makedirs(preOutPath)
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

def to_dict(pkt, packetLengthCorrection, dst_port, pd):
    ''' Store packet contents in a dict '''
    timeStr = str(pkt.time).split('.')
    d = {} # We store stuff in a dict
    # I think the following is self-explanatory :)
    d['timestamp_seconds'] = int(timeStr[0])
    # TODO: instead of nanoseconds, pcaps directly produced by OMNeT++ (and not via additional tcpdump) use microseconds -> adapt, when being relevant
    d['timestamp_nanoseconds'] = int(timeStr[1])
    d['packet_size_bytes'] = pkt.wirelen - packetLengthCorrection
    if pd.service_name(dst_port) == 'iperf':
        process_iperf.to_dict(d, pkt)
    if pd.service_name(dst_port) == 'send_udp':
        process_send_udp.to_dict(d, pkt)
    return d

def parse_single_pcap(processing_descriptor, limPktNum=-1):
    fl, preOutPath = init_general(processing_descriptor)
    if len(processing_descriptor.dst_ports) == 1:
        dst_port = processing_descriptor.dst_ports[0]
    else:
        print("Please call parseFlowPcapIperfFlowsNodeIFace with a PD having exactly one port.")
    parse_single_pcap(processing_descriptor, dst_port, fl, preOutPath, limPktNum)

def parse_single_pcap(processing_descriptor, dst_port, fl, preOutPath, limPktNum=-1):
    progressProc, startTime, p, modOp = init_single(fl, processing_descriptor, 'p'+str(dst_port), limPktNum)

    rows = []

    # Iterate over all packets that are of interest to us - the iperf ones.
    for index, pkt in enumerate(p):
        rows.append(to_dict(pkt, 4 if processing_descriptor.sim else 0, dst_port, processing_descriptor)) # We put the dict to our results list
        progressProc = progress(index, fl, progressProc, modOp)

    printProgress(fl, 100)
    # Based on our results list we create a dataframe and export to csv
    df = pandas.DataFrame(rows)
    df.to_csv(preOutPath + 'csv-' + processing_descriptor.service_name(dst_port) + '-single_' + str(dst_port) + '_' + processing_descriptor.iface + '.csv') #processing_descriptor.iface+'PcapFlowIperf'+str(dst_port)+'.csv') 
    printComplete('Flow PCAP Analysis complete!', startTime, fl)

def parse_separate_pcaps(processing_descriptor, limPktNum=-1):
    """
        Parses pcap(s) to csv(s)

        Assumes a separate pcap file per stream, i.e. given server port, containing UDP packets for given destination port only. Assumes "p<dst_port>"" to be used for tcpdump service file name. Writes one csv file per pcap.
        
        Parameters
        ----------
        experimentName :
            Name of the (folder with result files for the) experiment
        pathToFolder :
            Folder with per experiment result, assuming structure as written by ansible, i.e. one folder per experiment; Folder where the resulting files should be written to
        nodeNum :
            Node alias id
        iFace :
            Name of the interface where the pcap file(s) were recorded
        limPktNum:
            Load only this number of packets from the pcap files
        dst_ports:
            List of ports to differentiate processing_descriptor for which separate csv files should be generated
        packetLengthCorrection:
            (optional) number to be substracted from packetLength (simulation pcap packet lengths have 4 additional bytes; my guess: ethernet FCS)
    """
    fl, preOutPath = init_general(processing_descriptor)
    startTimeGlob = time.time()
    with open(fl, "a") as myFile:
        print('Parsing PCAPs for', processing_descriptor.experiment, processing_descriptor.node, 'interface', processing_descriptor.iface, end='...\n', file=myFile)

    for dst_port in processing_descriptor.dst_ports:
        parse_single_pcap(processing_descriptor, dst_port, fl, preOutPath, limPktNum)

    printComplete('Analysis of all' + str(len(processing_descriptor.dst_ports)) + 'PCAPs complete!', startTimeGlob, fl)

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
