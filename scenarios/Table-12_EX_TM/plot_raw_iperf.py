#!/usr/bin/env python3
import matplotlib as mpl
import matplotlib.pyplot as plt
mpl.rcParams['agg.path.chunksize'] = 500000000000000000
import pandas as pd
import glob
import numpy as np
import os
import math
import time
import statistics

font = {'weight' : 'normal',
        'size'   : 20}
mpl.rc('font', **font)
mpl.rc('lines', linewidth=2.0)
mpl.rc('lines', markersize=8)

figSize = (24,12)

flowToColor = {1001 : 'tab:blue',
               1002 : 'tab:orange',
               1003 : 'tab:green',
               1004 : 'tab:red',
               1005 : 'tab:purple',
               1006 : 'tab:brown',
               1007 : 'tab:pink',
               1008 : 'tab:gray',
               1009 : 'tab:olive',
               1010 : 'tab:cyan',
               1011 : 'black',
               6601 : 'tab:blue',
               6603 : 'tab:orange',
               6605 : 'tab:green'}


def plotManualTPcalcMultiFlow(experimentSubname, pathToExports, plotPath, nodeNum, iFace, iperfPorts, calculationTimescale):
    fl = pathToExports+'/pythonLog.txt'
    with open(fl, "a") as myFile:
        print('Plotting Throughput for', experimentSubname, end='...\t', file=myFile)
    startTime = time.time()
    fig, ax = plt.subplots(1, figsize=figSize)
    minTS = float('inf')
    maxTS = 0
    maxTP = 0
    toPlot = {}
    for iperfPort in iperfPorts:
        prePath = pathToExports + '/' + experimentSubname + '/node-' + str(nodeNum) + '/' + iFace + 'PcapFlowIperf' + str(iperfPort) + '.csv'
        fileName = glob.glob(prePath)
        df = pd.read_csv(fileName[0])
        df['Timestamp Full'] = df.apply(lambda row: row['Timestamp seconds'] + row['Timestamp nanoseconds']/1e9, axis=1)
        initialTime = df['Timestamp Full'].iloc[0]
        calculationWindow = [initialTime, initialTime + calculationTimescale]
        ts = []
        bitrates = []
        while calculationWindow[0] <= df['Timestamp Full'].iloc[-1]:
            tempDf = df.loc[(df['Timestamp Full'] >= calculationWindow[0]) & (df['Timestamp Full'] <= calculationWindow[1])]
            mbps = ((tempDf['Packet size bytes'].sum()*8)/1e6)/calculationTimescale
            ts.append(calculationWindow[1])
            bitrates.append(mbps)
            calculationWindow = [x + calculationTimescale for x in calculationWindow]
        minTS = min(minTS, min(ts))
        maxTS = max(maxTS, max(ts))
        maxTP = max(maxTP, max(bitrates))
        toPlot[iperfPort] = {}
        toPlot[iperfPort]['TS'] = ts
        toPlot[iperfPort]['Val'] = bitrates
    for iperfPort in iperfPorts:
        additive = ''
        if iperfPort == 1003 or iperfPort == 1004:
            additive = ' CBS'
        ax.plot([x - minTS for x in toPlot[iperfPort]['TS']], toPlot[iperfPort]['Val'], '.-', color=flowToColor[iperfPort], label='Flow ' + str(iperfPort-1000) + additive)

    ax.set_ylim(0,maxTP+10)
    ax.grid(which='both')

    plt.legend()
    plt.xlabel('Experiment Time [s]')
    plt.ylabel('Flow Throughput [mbps]')

    # Plot saving code block
    plotName = 'iperfThroughput_Node-'+str(nodeNum)+str(iFace)+experimentSubname+'_TimeGran'+str(int(calculationTimescale*1e6))+'us'+'_ports'+str(iperfPorts)+'.png'
    plotPaths = ['/plots/', '/plots/throughput/', '/plots/'+experimentSubname+'/']
    for pP in plotPaths:
        preOutPath = plotPath + pP
        if not os.path.exists(preOutPath):
            os.makedirs(preOutPath)
        fig.savefig(preOutPath + '/' + plotName, dpi=100, bbox_inches='tight', format='png')
    plt.close('all')

    with open(fl, "a") as myFile:
        print('It took', time.time() - startTime, 's\n', file=myFile)
    
    return minTS

def plotManualDelaycalcMultiFlow(experimentSubname, pathToExports, plotPath, endNodeNum, endiFace,ports, sourceOfPcap):
    fl = pathToExports+'/pythonLog.txt'
    with open(fl, "a") as myFile:
        print('Plotting Delay for', experimentSubname, end='...\t', file=myFile)
    startTime = time.time()
    fig, ax = plt.subplots(1, figsize=figSize)
    maxHeight = 0
    minTS = float('inf')
    delay = {}
    for port in ports:
        if sourceOfPcap == "iperf":
            prePath = pathToExports + '/' + experimentSubname + '/node-' + str(endNodeNum) + '/' + endiFace + 'DelayAndJitterFlowiperf' + str(port) + '.csv'
        elif sourceOfPcap == "send_udp":
            prePath = pathToExports + '/' + experimentSubname + '/node-' + str(endNodeNum) + '/' + endiFace + 'DelayAndJitterFlowsend_udp' + str(port) + '.csv'
        print(prePath)
        fileName = glob.glob(prePath)
        print(fileName)
        df = pd.read_csv(fileName[0])
        maxHeight = max(maxHeight, max(df['Delay']))
        minTS = min(minTS, min(df['Timestamp']))
        delay[port] = {}
        delay[port]['TS'] = df['Timestamp'].dropna()
        delay[port]['Val'] = [x/1e6 for x in df['Delay'].dropna().tolist()]
    for port in ports:
        start = 0
        offset = 100000
        end = len(delay[port]['TS']) - offset
        if sourceOfPcap == "iperf":   
            additive = ''
            if port == 1003 or port == 1004:
                additive = ' CBS'
            if port == "6605":
                ax.plot(delay[port]['TS'][start:end], delay[port]['Val'][start:end], '.-', label='Flow ' + str(int(port)) + additive, zorder=int(port), color=flowToColor[int(port)])
            else:
                ax.plot(delay[port]['TS'][start:end] - minTS, delay[port]['Val'][start:end], '.-', label='Flow ' + str(int(port)) + additive, zorder=int(port), color=flowToColor[int(port)])
            plotName = 'iperfDelay_NodeDest-'+str(endNodeNum)+str(endiFace)+experimentSubname+'_ports'+str(port)+'.png'

        
        elif sourceOfPcap == "send_udp":
            x_axis = delay[str(port)]['TS'][start:end] - minTS
            i = 0
            NaN = True
            while NaN:
                x = float(x_axis[i])
                if math.isnan(x):
                    i = i + 1
                else:
                    NaN = False
            print("number of NaN", i)
            if float(x_axis[i]) < 0 and str(port) != '6605':
                print("smaller", x_axis[i], delay[str(port)]['TS'][i], str(port))
                global diff
                diff = abs(float(x_axis[i]))
                x_axis = x_axis + diff
            ax.plot(x_axis, delay[str(port)]['Val'][start:end], '.-', label='Flow ' + str(port) +"len:"+ str(len(delay[str(port)]['Val'][start:end])), zorder=int(port), color=flowToColor[int(port)])

            plt.xlabel('Experiment Time [s]')
            plotName = 'sendUDPDelay_NodeDest-'+str(endNodeNum)+str(endiFace)+experimentSubname+'_ports'+str(port)+'.png'
    ax.grid(which='both')
    ax.ticklabel_format(useOffset=False, style='plain')

    plt.legend()
    plt.xlabel('Experiment Time [s]')
    plt.ylabel('End-To-End Delay [ms]')

    # Plot saving code block
    
    plotPaths = ['/plots/', '/plots/delay/', '/plots/'+experimentSubname+'/']
    for pP in plotPaths:
        preOutPath = plotPath + pP
        if not os.path.exists(preOutPath):
            os.makedirs(preOutPath)
        mpl.rcParams['agg.path.chunksize'] = 500000000000000000
        fig.savefig(preOutPath + '/' + plotName, dpi=50, bbox_inches='tight', format='jpg')
    plt.close('all')

    with open(fl, "a") as myFile:
        print('It took', time.time() - startTime, 's', file=myFile)
    
    return minTS


def plotManualJittercalcMultiFlow(experimentSubname, pathToExports, plotPath, endNodeNum, endiFace, ports, sourceOfPcap):
    fl = pathToExports+'/pythonLog.txt'
    with open(fl, "a") as myFile:
        print('Plotting Jitter for', experimentSubname, end='...\t', file=myFile)
    startTime = time.time()
    fig, ax = plt.subplots(1, figsize=figSize)
    maxHeight = 0
    minHeight = 0
    minTS = float('inf')
    maxMean = 0
    jitter = {}
    for port in ports:
        if sourceOfPcap == "iperf":
            prePath = pathToExports + '/' + experimentSubname + '/node-' + str(endNodeNum) + '/' + endiFace + 'DelayAndJitterFlowiperf' + str(port) + '.csv'
        elif sourceOfPcap == "send_udp":
            prePath = pathToExports + '/' + experimentSubname + '/node-' + str(endNodeNum) + '/' + endiFace + 'DelayAndJitterFlowsend_udp' + str(port) + '.csv'
        fileName = glob.glob(prePath)
        df = pd.read_csv(fileName[0])
        maxHeight = max(maxHeight, max(df['Jitter']))
        minHeight = min(minHeight, min(df['Jitter']))
        minTS = min(minTS, min(df['Timestamp']))
        jitter[port] = {}
        jitter[port]['TS'] = df['Timestamp']
        jitter[port]['Val'] = [x/1e3 for x in df['Jitter'].tolist()]
    for port in ports:
        start = 0
        end = len(jitter[port]['TS']) - 1000
        if sourceOfPcap == "iperf":
            additive = ''
            if port == 1003 or port == 1004:
                additive = ' CBS'
            if port == "6605":
                ax.plot(jitter[port]['TS'][start:end] - minTS, jitter[port]['Val'][start:end], '.-', label='Flow ' + str(int(port)) + additive, zorder=int(port), color=flowToColor[int(port)])
            else:
                ax.plot(jitter[port]['TS'][start:end] - minTS, jitter[port]['Val'][start:end], '.-', label='Flow ' + str(int(port)) + additive, zorder=int(port), color=flowToColor[int(port)])
            
            plotName = 'iperfJitter_NodeDest-'+str(endNodeNum)+str(endiFace)+experimentSubname+'_ports'+str(ports)+'.png'
        elif sourceOfPcap == "send_udp":
            ax.plot(jitter[str(port)]['TS'][start:end] - minTS, jitter[str(port)]['Val'][start:end], '.-', label='Flow ' + str(port), zorder=int(port), color=flowToColor[int(port)])
            
            plt.xlabel('Experiment Time [s]')
            ax.set_ylim(minHeight/1e3, maxMean+100)
            plotName = 'sendUDPJitter_NodeDest-'+str(endNodeNum)+str(endiFace)+experimentSubname+'_ports'+str(ports)+'.png'

    ax.grid(which='both')
    ax.ticklabel_format(useOffset=False, style='plain')

    plt.legend()
    plt.xlabel('Experiment Time [s]')
    plt.ylabel('Jitter [\u03BCs]')


    plotPaths = ['/plots/', '/plots/jitter/', '/plots/'+experimentSubname+'/']
    for pP in plotPaths:
        preOutPath = plotPath + pP
        if not os.path.exists(preOutPath):
            os.makedirs(preOutPath)
        fig.savefig(preOutPath + '/' + plotName, dpi=100, bbox_inches='tight', format='png')
    plt.close('all')

    with open(fl, "a") as myFile:
        print('It took', time.time() - startTime, 's', file=myFile)

def plotManualJitterCDFcalcMultiFlow(experimentSubname, pathToExports, plotPath, endNodeNum, endiFace, ports, sourceOfPcap):
    fl = pathToExports+'/pythonLog.txt'
    with open(fl, "a") as myFile:
        print('Plotting Jitter CDF for', experimentSubname, end='...\t', file=myFile)
    startTime = time.time()
    fig, ax = plt.subplots(1, figsize=figSize)
    absMax = 0
    jitter = {}
    for port in ports:
        if sourceOfPcap == "iperf":
            prePath = pathToExports + '/' + experimentSubname + '/node-' + str(endNodeNum) + '/' + endiFace + 'DelayAndJitterFlowiperf' + str(port) + '.csv'
        elif sourceOfPcap == "send_udp":
            prePath = pathToExports + '/' + experimentSubname + '/node-' + str(endNodeNum) + '/' + endiFace + 'DelayAndJitterFlowsend_udp' + str(port) + '.csv'
        fileName = glob.glob(prePath)
        df = pd.read_csv(fileName[0])
        jitter[port] = {}
        jitter[port]['Val'] = [x/1e3 for x in df['Jitter'].tolist()]

    for port in ports:
        start = 0
        end = len(jitter[port]['Val'])
        sorted_data = np.sort(jitter[port]['Val'])
        linspaced = np.linspace(0, 1, len(jitter[port]['Val']), endpoint=True)
        cutOutliers = 1500
        additive = ''
        absMax = max(absMax, max([abs(x) for x in sorted_data[cutOutliers:-cutOutliers]]))
        
        if port == 1003 or port == 1004:
            additive = ' CBS'

        if sourceOfPcap == "iperf":
            additive = ''
            if port == 1003 or port == 1004:
                additive = ' CBS'
            if port == "6605":
                ax.plot(sorted_data[start:end], linspaced[start:end], '.-', label='Flow ' + str(port) + additive, zorder=int(port), color=flowToColor[int(port)])
            else:
                ax.plot(sorted_data[start:end], linspaced[start:end], '.-', label='Flow ' + str(port) + additive, zorder=int(port), color=flowToColor[int(port)])
            plotName = 'iperfJitterCDF_NodeDest-'+str(endNodeNum)+str(endiFace)+experimentSubname+'_ports'+str(ports)+'.png'
        elif sourceOfPcap == "send_udp":
            #lengthData = len(sorted_data) - 1000
            ax.plot(sorted_data[start:end], linspaced[start:end], '.-', label='Flow ' + str(port), zorder=int(port), color=flowToColor[int(port)])
            plotName = 'sendUDPJitterCDF_NodeDest-'+str(endNodeNum)+str(endiFace)+experimentSubname+'_ports'+str(ports)+'.png'  
    ax.set_xlim(-absMax,absMax)
    ax.grid(which='both')
    ax.ticklabel_format(useOffset=False, style='plain')

    plt.legend()
    plt.xlabel('Jitter [\u03BCs]')
    plt.ylabel('CDF')

    # Plot saving code block
    plotPaths = ['/plots/', '/plots/jitterCDF/', '/plots/'+experimentSubname+'/']
    for pP in plotPaths:
        preOutPath = plotPath + pP
        if not os.path.exists(preOutPath):
            os.makedirs(preOutPath)
        fig.savefig(preOutPath + '/' + plotName, dpi=100, bbox_inches='tight', format='png')
    plt.close('all')

    with open(fl, "a") as myFile:
        print('It took', time.time() - startTime, 's', file=myFile)

def plotManualPacketLosscalcMultiFlow(experimentSubname, pathToExports, plotPath, endNodeNum, endiFace, ports, refTS, sourceOfPcap):
    fl = pathToExports+'/pythonLog.txt'
    with open(fl, "a") as myFile:
        print('Plotting Packet Loss for', experimentSubname, end='...\t', file=myFile)
    startTime = time.time()
    fig, ax = plt.subplots(1, figsize=figSize)
    packetLoss = {}
    for port in ports:
        if sourceOfPcap == "iperf":
            prePath = pathToExports + '/' + experimentSubname + '/node-' + str(endNodeNum) + '/' + endiFace + 'DelayAndJitterFlowiperf' + str(port) + '.csv'
        elif sourceOfPcap == "send_udp":
            prePath = pathToExports + '/' + experimentSubname + '/node-' + str(endNodeNum) + '/' + endiFace + 'DelayAndJitterFlowsend_udp' + str(port) + '.csv'
        fileName = glob.glob(prePath)
        df = pd.read_csv(fileName[0])
        cumulativePktLost = [x+1 for x in range(len(df['Timestamp Loss'].dropna()))]
        packetLoss[port] = {}
        packetLoss[port]['TS'] = df['Timestamp Loss'].dropna()
        packetLoss[port]['Val'] = cumulativePktLost
        
    for port in ports:
        if sourceOfPcap == "iperf":
            additive = ''
            if port == 1003 or port == 1004:
                additive = ' CBS'
            ax.plot(packetLoss[port]['TS'] - refTS, packetLoss[port]['Val'], 'o-', label='Flow ' + str(port-1000) + additive, color=flowToColor[port])
            plotName = 'iperfCumulativePacketLoss_NodeDest-'+str(endNodeNum)+str(endiFace)+experimentSubname+'_ports'+str(ports)+'.png'
        elif sourceOfPcap == "send_udp":
            ax.plot(packetLoss[str(port)]['TS'] - refTS, packetLoss[str(port)]['Val'], 'o-', label='Flow ' + str(port), color=flowToColor[int(port)])
            plotName = 'sendUDPCumulativePacketLoss_NodeDest-'+str(endNodeNum)+str(endiFace)+experimentSubname+'_ports'+str(ports)+'.png'

    ax.grid(which='both')
    ax.ticklabel_format(useOffset=False, style='plain')

    plt.legend()
    plt.xlabel('Experiment Time [s]')
    plt.ylabel('Cumulative Number of Lost Packets')

    # Plot saving code block

    plotPaths = ['/plots/', '/plots/cumulativePacketLoss/', '/plots/'+experimentSubname+'/']
    for pP in plotPaths:
        preOutPath = plotPath + pP
        if not os.path.exists(preOutPath):
            os.makedirs(preOutPath)
        fig.savefig(preOutPath + '/' + plotName, dpi=100, bbox_inches='tight', format='png')
    plt.close('all')

    with open(fl, "a") as myFile:
        print('It took', time.time() - startTime, 's', file=myFile)



def tableSummarizeAllValuesFlow(experimentSubname, pathToExports, tablePath, endNodeNum, endiFace,ports, sourceOfPcap):
    fl = pathToExports+'/pythonLog.txt'
    with open(fl, "a") as myFile:
        print('Preparing Table values for', experimentSubname, end='...\t', file=myFile)
    startTime = time.time()
    delay = {}
    jitter = {}
    packetLoss = {}
    if sourceOfPcap == "iperf":
        tableName = 'iperfTable_NodeDest-'+str(endNodeNum)+str(endiFace)+experimentSubname+'.csv'
    elif sourceOfPcap == "send_udp":
        tableName = 'sendUdpTable_NodeDest-'+str(endNodeNum)+str(endiFace)+experimentSubname+'.csv'
    tablePathLocal = '/plots/'+experimentSubname+'/'
    f2 = tablePath + tablePathLocal + tableName
    print(f2)
    with open(f2, "a") as myFile:
        print('Adding results for ', experimentSubname, end='...\t', file=myFile)
    
    for port in ports:
        if sourceOfPcap == "iperf":
            prePath = pathToExports + '/' + experimentSubname + '/node-' + str(endNodeNum) + '/' + endiFace + 'DelayAndJitterFlowiperf' + str(port) + '.csv'
        elif sourceOfPcap == "send_udp":
            prePath = pathToExports + '/' + experimentSubname + '/node-' + str(endNodeNum) + '/' + endiFace + 'DelayAndJitterFlowsend_udp' + str(port) + '.csv'
        print(prePath)
        fileName = glob.glob(prePath)
        print(fileName)
        df = pd.read_csv(fileName[0])
        port = int(port)
        delay[port] = {}
        jitter[port] = {}
        delay[port]['TS'] = df['Timestamp'].dropna()
        delay[port]['Val'] = [x/1e6 for x in df['Delay'].dropna().tolist()]
        jitter[port]['TS'] = df['Timestamp']
        jitter[port]['Val'] = [x/1e3 for x in df['Jitter'].dropna().tolist()]
        cumulativePktLost = [x+1 for x in range(len(df['Timestamp Loss'].dropna()))]
        packetLoss[port] = {}
        packetLoss[port]['TS'] = df['Timestamp Loss'].dropna()
        packetLoss[port]['Val'] = cumulativePktLost
    packet_from_source = 300000
    packet_from_source = 100000
    percentileValue = 99
    for port in ports:
        port = int(port)
        global diff
        if sourceOfPcap == "iperf":
            start = 0
            offset = 0
            end = len(delay[port]['TS']) - offset
            with open(f2, "a") as myFile:
                print('Delay values for port number: ', 'Flow ' + str(int(port)), end='...\t', file=myFile)
                meanDelay = statistics.mean(delay[port]['Val'][start:end])
                medianDelay = statistics.median(delay[port]['Val'][start:end])
                stdevDelay = statistics.stdev(delay[port]['Val'][start:end])
                delay99Percentil = np.percentile(delay[port]['Val'][start:end], percentileValue)
                minValueDelay = min(delay[port]['Val'][start:end])
                maxValueDelay = max(delay[port]['Val'][start:end])
                npJitterAbsValue = np.absolute(jitter[port]['Val'][start:end])
                meanJitter = statistics.mean(npJitterAbsValue)
                medianJitter = statistics.median(npJitterAbsValue)
                stdevJitter = statistics.stdev(npJitterAbsValue)
                jitter99Percentil = np.percentile(npJitterAbsValue, percentileValue)
                minValueJitter = min(jitter[port]['Val'][start:end])
                maxValueJitter = max(jitter[port]['Val'][start:end])
                lenTCPDump = len(delay[port]['Val'][start:end])
                if not packetLoss[port]['Val']:
                    packetLossAnalysis = 0
                    ratioSendLostTcpdump = 1
                else:
                    packetLossAnalysis = packetLoss[port]['Val'][-1]
                    ratioSendLostTcpdump = 1.0 - lenTCPDump/packetLossAnalysis
                ratioOrigoSendLostTcpdump = lenTCPDump/packet_from_source
               
                print('Mean:\n', meanDelay, end='...\n', file=myFile)
                print('Median:\n', medianDelay, end='...\n', file=myFile)
                print('Stdev:\n', stdevDelay, end='...\n', file=myFile)
                print('Max:\n', minValueDelay, end='...\n', file=myFile)
                print('Min:\n', maxValueDelay, end='...\n', file=myFile)
                print('Jitter', end='...\n', file=myFile)
                print('Mean:\n', meanJitter, end='...\n', file=myFile)
                print('Median:\n', medianJitter, end='...\n', file=myFile)
                print('Stdev:\n', stdevJitter, end='...\n', file=myFile)
                print('Max:\n', maxValueJitter, end='...\n', file=myFile)
                print('Min:\n', minValueJitter, end='...\n', file=myFile)
                print('Packet send total:\n ', str(packet_from_source), end='...\n', file=myFile)
                print('Packet send len of tcpdump:\n ', str(lenTCPDump), end='...\n', file=myFile)
                print('Packet lost tcpdump info total:\n ', str(packetLossAnalysis), end='...\n', file=myFile)
                print('Packet lost ratio (total send vs tcpdump) total: \n', str(ratioOrigoSendLostTcpdump), end='...\n', file=myFile)
                print('Packet lost ratio (tcpdump vs packet) total: \n', str(ratioSendLostTcpdump), end='...\n', file=myFile)
                print('Latex output: \n', str(ratioOrigoSendLostTcpdump), end='...\n', file=myFile)
                print(round(meanDelay, 4), "&", round(medianDelay, 4), "&", round(delay99Percentil, 4), "&", round(meanJitter, 4), "&", round(medianJitter, 4), "&", round(jitter99Percentil, 4), "&", lenTCPDump, "&", packetLossAnalysis, "&", round(ratioOrigoSendLostTcpdump, 4), end='...\n', file=myFile)
                print(meanDelay, "&", medianDelay, "&",delay99Percentil, "&", meanJitter, "&", medianJitter, "&", jitter99Percentil, "&", lenTCPDump, "&", packetLossAnalysis, "&",ratioOrigoSendLostTcpdump, end='...\n', file=myFile)

        elif sourceOfPcap == "send_udp":
            start = 0
            offset = 0
            end = len(delay[port]['TS']) - offset
            with open(f2, "a") as myFile:
                print('Delay values for port number: ', 'Flow ' + str(int(port)), end='...\t', file=myFile)
                meanDelay = statistics.mean(delay[port]['Val'][start:end])
                medianDelay = statistics.median(delay[port]['Val'][start:end])
                stdevDelay = statistics.stdev(delay[port]['Val'][start:end])
                delay99Percentil = np.percentile(delay[port]['Val'][start:end], percentileValue)
                minValueDelay = min(delay[port]['Val'][start:end])
                maxValueDelay = max(delay[port]['Val'][start:end])
                npJitterAbsValue = np.absolute(jitter[port]['Val'][start:end])
                meanJitter = statistics.mean(npJitterAbsValue)
                medianJitter = statistics.median(npJitterAbsValue)
                stdevJitter = statistics.stdev(npJitterAbsValue)
                jitter99Percentil = np.percentile(npJitterAbsValue, percentileValue)
                minValueJitter = min(jitter[port]['Val'][start:end])
                maxValueJitter = max(jitter[port]['Val'][start:end])
                lenTCPDump = len(delay[port]['Val'][start:end])
                print(packetLoss[port]['Val'])
                if not packetLoss[port]['Val']:
                    print("empty")
                    packetLossAnalysis = 1
                else:
                    packetLossAnalysis = packetLoss[str(port)]['Val'][-1]
                ratioOrigoSendLostTcpdump = 1.0 - lenTCPDump/packet_from_source
                ratioSendLostTcpdump = 1.0 - lenTCPDump/packetLossAnalysis
                print('Mean:\n', meanDelay, end='...\n', file=myFile)
                print('Median:\n', medianDelay, end='...\n', file=myFile)
                print('Stdev:\n', stdevDelay, end='...\n', file=myFile)
                print('Max:\n', minValueDelay, end='...\n', file=myFile)
                print('Min:\n', maxValueDelay, end='...\n', file=myFile)
                print('Jitter', end='...\n', file=myFile)
                print('Mean:\n', meanJitter, end='...\n', file=myFile)
                print('Median:\n', medianJitter, end='...\n', file=myFile)
                print('Stdev:\n', stdevJitter, end='...\n', file=myFile)
                print('Max:\n', maxValueJitter, end='...\n', file=myFile)
                print('Min:\n', minValueJitter, end='...\n', file=myFile)
                print('Packet send total:\n ', str(packet_from_source), end='...\n', file=myFile)
                print('Packet send len of tcpdump:\n ', str(lenTCPDump), end='...\n', file=myFile)
                print('Packet lost tcpdump info total:\n ', str(packetLossAnalysis), end='...\n', file=myFile)
                print('Packet lost ratio (total send vs tcpdump) total: \n', str(ratioOrigoSendLostTcpdump), end='...\n', file=myFile)
                print('Packet lost ratio (tcpdump vs packet) total: \n', str(ratioSendLostTcpdump), end='...\n', file=myFile)
                print('Latex output: \n', str(ratioOrigoSendLostTcpdump), end='...\n', file=myFile)
                print(round(meanDelay, 4), "&", round(medianDelay, 4), "&", round(delay99Percentil, 4), "&", round(meanJitter, 4), "&", round(medianJitter, 4), "&", round(jitter99Percentil, 4), "&", lenTCPDump, "&", packetLossAnalysis, "&", round(ratioOrigoSendLostTcpdump, 4), end='...\n', file=myFile)
                print(meanDelay, "&", medianDelay, "&",delay99Percentil, "&", meanJitter, "&", medianJitter, "&", jitter99Percentil, "&", lenTCPDump, "&", packetLossAnalysis, "&",ratioOrigoSendLostTcpdump, end='...\n', file=myFile)
                
    # Table saving code block
    with open(fl, "a") as myFile:
        print('It took', time.time() - startTime, 's', file=myFile)
    
def plotManualIfsCDFcalcMultiFlow(experimentSubname, pathToExports, plotPath, endNodeNum, endiFace, ports, sourceOfPcap):
    fl = pathToExports+'/pythonLog.txt'
    with open(fl, "a") as myFile:
        print('Plotting Inter-Frame Spacing for', experimentSubname, end='...\t', file=myFile)
    startTime = time.time()
    fig, ax = plt.subplots(1, figsize=figSize)
    interFramSpacs = {}
    allVals = []
    for port in ports:
        if sourceOfPcap == "iperf":
            prePath = pathToExports + '/' + experimentSubname + '/node-' + str(endNodeNum) + '/' + endiFace + 'DelayAndJitterFlowiperf' + str(port) + '.csv'
        elif sourceOfPcap == "send_udp":
            prePath = pathToExports + '/' + experimentSubname + '/node-' + str(endNodeNum) + '/' + endiFace + 'DelayAndJitterFlowsend_udp' + str(port) + '.csv'
        fileName = glob.glob(prePath)
        df = pd.read_csv(fileName[0])
        timestamps = df['Timestamp'].dropna().tolist()
        ifs = [(x - y)*1e6 for x,y in zip(timestamps[1:], timestamps[:-1])]
        interFramSpacs[port] = {}
        interFramSpacs[port]['Val'] = ifs
        allVals.extend(ifs)
    for port in ports:
        sorted_data = np.sort(interFramSpacs[port]['Val'])
        linspaced = np.linspace(0, 1, len(interFramSpacs[port]['Val']), endpoint=True)
        lbl = 'Measured'
        if sourceOfPcap == "iperf":
            additive = ""
            if port == 1003 or port == 1004:
                additive = ' CBS'
            if len(str(port)) > 1:
                lbl = 'Flow ' + str(port-1000) + additive
            ax.plot(sorted_data, linspaced, '.-', label=lbl, zorder=port-980, color=flowToColor[port])
            plotName = 'iperfInterFrameSpacingCDF_NodeDest-'+str(endNodeNum)+str(endiFace)+experimentSubname+'_ports'+str(ports)+'.png'
        elif sourceOfPcap == "send_udp":
            ax.plot(sorted_data, linspaced, '.-', label=lbl, zorder=int(port)-980, color=flowToColor[int(port)])
            plotName = 'sendUDPInterFrameSpacingCDF_NodeDest-'+str(endNodeNum)+str(endiFace)+experimentSubname+'_ports'+str(ports)+'.png'
        
        if len(ports) <= 1: ax.vlines(100, ymin=0, ymax=1, alpha=0.9, zorder=1000, color='tab:red', label='Target')
    ax.grid(which='both')
    ax.ticklabel_format(useOffset=False, style='plain')

    plt.legend()
    plt.xlabel('Inter-Frame Spacing [\u03BCs]')
    plt.ylabel('CDF')

    # Plot saving code block

    plotPaths = ['/plots/', '/plots/ifsCDF/', '/plots/'+experimentSubname+'/']
    for pP in plotPaths:
        preOutPath = plotPath + pP
        if not os.path.exists(preOutPath):
            os.makedirs(preOutPath)
        fig.savefig(preOutPath + '/' + plotName, dpi=100, bbox_inches='tight', format='png')
        # saveTikz(plotName, preOutPath, defParams, "small", True, False)
    plt.close('all')

    with open(fl, "a") as myFile:
        print('It took', time.time() - startTime, 's', file=myFile)