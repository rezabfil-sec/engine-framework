#!/usr/bin/env python3

# Merge csv files of stream end points with added delay and jitter

import numpy as np
import pandas as pd
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

def printComplete(string, sTime, fl):
    with open(fl, "a") as myFile:
        print(string + ' It took', time.time() - sTime, 's\n', file=myFile)

def importCsvExtDnames(processing_descriptor, dst_port):
    fileName = processing_descriptor.find_file_name('csv-' + processing_descriptor.service_name(dst_port) + '-single_' + str(dst_port) + '_' + processing_descriptor.iface + '.csv') #processing_descriptor.iface + 'PcapFlowIperf' + str(dst_port) + '.csv')
    df = pd.read_csv(fileName, index_col=0) # Loads the CSV
    #df['timestamp_full ' + processing_descriptor.node_num()] = df.apply(lambda row: row['timestamp_seconds'] + row['timestamp_nanoseconds']/1e9, axis=1) # Adds full fimestamp
    df['timestamp_ns_' + processing_descriptor.node_num()] = df.apply(lambda row: row['timestamp_seconds'] * 1e9 + row['timestamp_nanoseconds'], axis=1).astype(int)
    df = df.rename(columns={'timestamp_seconds' : 'timestamp_seconds ' + processing_descriptor.node_num(), 'timestamp_nanoseconds' : 'timestamp_nanoseconds ' + processing_descriptor.node_num(), 'packet_size_bytes' : 'packet_size_bytes ' + processing_descriptor.node_num()})
    return df

def init(processing_descriptor_end, processing_descriptor_start):
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
        Files read: <pathToFolder>/<experimentName>/node-<(start|end)NodeNum/csv-<service>-combined_<dst_port>_<iFace>.csv
        File(s) written: <pathToFolder>/<experimentName>/node-<endNodeNum>/csv-<service>-combined_<dst_ports>_<endiFace>.csv

        Parameters
        ----------
        experimentName :
            Name of the (folder with result files for the) experiment
        pathToFolder :
            Folder where the resulting files should be written to
        startNodeNum :
            Node alias id of traffic source node
        endNodeNum :
            Node alias id of traffic sink node
        startiFace :
            Name of the start node interface where the pcap file(s) were recorded
        endiFace :
            Name of the end node interface where the pcap file(s) were recorded
        dst_ports:
            List of ports with separate csv files
    """
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
        if processing_descriptor_end.service_name(dst_port) == 'iperf':
            merge = process_iperf.merge
        elif processing_descriptor_end.service_name(dst_port) == 'send_udp':
            merge = process_send_udp.merge
        else:
            print("TODO")
        evalDF = pd.merge(df, df2, how='left', on=merge)
        printProgress(fl, 30)
        retDF = pd.DataFrame()
        #retDF['Timestamp'] = evalDF.dropna()['timestamp_full ' + str(processing_descriptor_start.node_num())]
        retDF['timestamp_ns'] = evalDF.dropna()['timestamp_ns_' + str(processing_descriptor_start.node_num())]
        printProgress(fl, 40)
        #retDF['Delay'] = evalDF.dropna().apply(lambda row: (row['timestamp_full ' + str(processing_descriptor_end.node_num())] - row['timestamp_full ' + str(processing_descriptor_start.node_num())] - (0 if processing_descriptor_end.sim else 37)) * 1e9, axis=1).dropna()
        retDF['delay_ns'] = evalDF.dropna().apply(lambda row: (row['timestamp_ns_' + str(processing_descriptor_end.node_num())] - row['timestamp_ns_' + str(processing_descriptor_start.node_num())] - (0 if processing_descriptor_end.sim else (37 * 1e9))) , axis=1).dropna().astype(int)
        printProgress(fl, 50)
        #retDF['Jitter'] = retDF['Delay'].diff()
        retDF['jitter_ns'] = retDF['delay_ns'].diff()
        #retDF.at[0, 'Jitter'] = 0
        retDF.at[0, 'jitter_ns'] = 0
        retDF['jitter_ns'] = retDF['jitter_ns'].astype(int)
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

# TODO: adapt: use nanosecond timestamps instead of seconds

def importCsvAddFullTS(processing_descriptor, dst_port):
    ''' Imports a csv and adds a combined timestamp to it (based on partial ones) '''
    fileName = processing_descriptor.find_file_name('csv-' + processing_descriptor.service_name(dst_port) + '-single_' + str(dst_port) + '_' + processing_descriptor.iface + '.csv') #processing_descriptor.iface + 'PcapFlowIperf' + str(dst_port) + '.csv')
    df = pd.read_csv(fileName, index_col=0) # Loads the CSV
    df['timestamp_full'] = df.apply(lambda row: row['timestamp_seconds'] + row['timestamp_nanoseconds']/1e9, axis=1) # Adds full fimestamp
    return df

def init_single(fl, dst_port, processing_descriptor_end, processing_descriptor_start):
    startTime = time.time()
    with open(fl, "a") as myFile:
        print('Analyzing port', dst_port, end='...\n', file=myFile)
    df = importCsvAddFullTS(processing_descriptor_start, dst_port)# Import source csv
    df2 = importCsvAddFullTS(processing_descriptor_end, dst_port) # Import target csv

    ts = [] # Timestamp of delay measurement on target
    delay = [] # Measured delay
    jitter = [0] # Jitter. Starts with second timestamp cause we'll have fewer values

    plTs = []
    plSeqNum = []

    modOp = int(len(df.index)/100)
    progressProc = 0
    with open(fl, "a") as myFile:
        print('Starting analysis for port', dst_port, end='...\n', file=myFile)
    printProgress(fl, progressProc)
    return startTime, df, df2, ts, delay, jitter, plTs, plSeqNum, modOp, progressProc

def follow_up(fl, dst_port, delay, ts, plTs, plSeqNum, processing_descriptor, startTime):
    printProgress(fl, 100)
    with open(fl, "a") as myFile:
        print('Calculating jitter for port', dst_port, end='...\n', file=myFile)
    # Calculate Jitter
    for i in range(len(delay)-1):
        jitter.append(delay[i+1]-delay[i])
    
    # Create dataframe to easily export results to csv
    data = {'Timestamp' : ts, 'Delay' : delay, 'Jitter' : jitter, 'Timestamp Loss' : plTs, 'LostSeq' : plSeqNum}
    df = pd.DataFrame({key:pd.Series(value) for key, value in data.items()})

    # Export to CSV
    outPath = processing_descriptor.path_to_node() + 'csv-' + processing_descriptor.service_name(dst_port) + '-combined_' + str(dst_port) + '_' + processing_descriptor_end.iface + '.csv' #endiFace + 'DelayAndJitterFlowIperf' + str(dst_port) + '.csv'
    df.to_csv(outPath)
    printComplete('Analysis for port' + str(dst_port) + 'complete!', startTime, fl)

# TODO: unused, doesn't support other services than iperf

def saveDelayAndJitterToCsv(processing_descriptor_end, processing_descriptor_start):
    ''' Extracts e2e delay and jitter from results and exports it to csv '''
    startTimeGlob, fl = init(processing_descriptor_end, processing_descriptor_start)
    for dst_port in processing_descriptor_start.dst_ports:
        startTime, df, df2, ts, delay, jitter, plTs, plSeqNum, modOp, progressProc = init_single(fl, dst_port, processing_descriptor_end, processing_descriptor_start)

        # Iterate over all rows, find the related pacets on source and target and calculate the delay
        for index , row in df.iterrows():
            if processing_descriptor.service_name(dst_port) == 'iperf':
                sequence = process_iperf.sequence
            elif processing_descriptor.service_name(dst_port) == 'send_udp':
                sequence = process_send_udp.sequence
            else:
                print("TODO")
            seqNum = row[sequence]
            tempDf = df2.loc[df2[sequence] == seqNum] # Select row with corresponding sequence number
            if tempDf.empty:
                plTs.append(row['timestamp_full'])
                plSeqNum.append(int(seqNum))
                # print('Packet Loss at', row['timestamp_full'], 'seq', int(seqNum))
            else:
                foundFlag = False
                for _, row2 in tempDf.iterrows():
                    if row['iperf_ts_seconds'] == row2['iperf_ts_seconds'] and row['iperf_ts_microseconds'] == row2['iperf_ts_microseconds']: # Make sure we really have the right one in case sequence number overflows
                        d = row2['timestamp_full'] - row['timestamp_full'] - 37 # The 37 is a difference between TAI time and UTC time
                        if (index + 1) % modOp == 0: 
                            progressProc += 1
                            printProgress(fl, progressProc)
                        foundFlag = True
                        ts.append(row['timestamp_full'])
                        delay.append(d)
                if foundFlag == False:
                    plTs.append(row['timestamp_full'])
                    plSeqNum.append(int(seqNum))
                    # print('Also Packet Loss at', row['timestamp_full'], 'seq', row[sequence])
        follow_up(fl, dst_port, delay, ts, plTs, plSeqNum, processing_descriptor_start, startTime)
    printComplete('Analysis complete!', startTimeGlob, fl)

def onListsSaveDelayAndJitterToCsv(processing_descriptor_end, processing_descriptor_start):
    ''' Extracts e2e delay and jitter from results and exports it to csv '''
    startTimeGlob, fl = init(processing_descriptor_end, processing_descriptor_start)
    for dst_port in processing_descriptor_end.dst_ports:
        startTime, df, df2, ts, delay, jitter, plTs, plSeqNum, modOp, progressProc = init_single(fl, dst_port, processing_descriptor_end, processing_descriptor_start)

        sourceDict = {}
        sourceDict['timestamp_full'] = df['timestamp_full'].tolist()
        sourceDict['iperf_ts_seconds'] = df['timestamp_seconds'].tolist()
        sourceDict['iperf_ts_microseconds'] = df['timestamp_seconds'].tolist()
        if processing_descriptor_end.service_name(dst_port) == 'iperf':
            sequence = process_iperf.sequence
        elif processing_descriptor_end.service_name(dst_port) == 'send_udp':
            sequence = process_send_udp.sequence
        else:
            print("TODO")
        sourceDict[sequence] = df['timestamp_seconds'].tolist()
        with open(fl, "a") as myFile:
            print(len(sourceDict['timestamp_full']), len(sourceDict['iperf_ts_seconds']), len(sourceDict['iperf_ts_microseconds']), len(sourceDict[sequence]), file=myFile)
        destDict = {}
        destDict['timestamp_full'] = df2['timestamp_full'].tolist()
        destDict['iperf_ts_seconds'] = df2['timestamp_seconds'].tolist()
        destDict['iperf_ts_microseconds'] = df2['timestamp_seconds'].tolist()
        destDict[sequence] = df2['timestamp_seconds'].tolist()
        with open(fl, "a") as myFile:
            print(len(destDict['timestamp_full']), len(destDict['iperf_ts_seconds']), len(destDict['iperf_ts_microseconds']), len(destDict[sequence]), file=myFile)

        numLines = len(sourceDict[sequence])
        print(numLines)

        # Iterate over all rows, find the related pacets on source and target and calculate the delay
        for i in range(len(sourceDict[sequence])):
            # print(i, end=';')
            seqNum = sourceDict[sequence][i]
            if (i + 1) % modOp == 0: 
                progressProc += 1
                printProgress(fl, progressProc)
            try: # Select corresponding row
                dIndex = destDict[sequence].index(seqNum)
            except ValueError:
                plTs.append(sourceDict['timestamp_full'][i])
                plSeqNum.append(int(seqNum))
                continue
            while True:
                if sourceDict['iperf_ts_seconds'][i] == destDict['iperf_ts_seconds'][dIndex] and sourceDict['iperf_ts_microseconds'][i] == destDict['iperf_ts_microseconds'][dIndex]: # Make sure we really have the right one in case sequence number overflows
                    d = destDict['timestamp_full'][dIndex] - sourceDict['timestamp_full'][i] - 37 # The 37 is a difference between TAI time and UTC time
                    ts.append(destDict['timestamp_full'][dIndex])
                    delay.append(d)
                    break
                try: # Select corresponding row
                    dIndex = destDict[sequence].index(seqNum, dIndex + 1)
                    print('Whops...')
                except ValueError:
                    plTs.append(sourceDict['timestamp_full'][i])
                    plSeqNum.append(int(seqNum))
                    print('Done...')
                    break
                print('Hmmm...')
        follow_up(fl, dst_port, delay, ts, plTs, plSeqNum, processing_descriptor_end, startTime)
    printComplete('Analysis complete!', startTimeGlob, fl)

# TODO end

def main():
    pd_end, pd_start = processing_descriptor.create_processing_descriptors_cli('csv_parser_pcap_combined', 'Parse pcap to csv')
    print('Parsing experiment', pd_end.experiment, 'on', pd_start.node, pd_start.iface, pd_end.node, pd_end.iface, 'for UDP flows with target ports', pd_end.dst_ports)

    # Call the parsing function
    # saveDelayAndJitterToCsv(pd_end, pd_start)
    save_delay_and_jitter_to_csv(pd_end, pd_start)

if __name__ == "__main__":
    main()
