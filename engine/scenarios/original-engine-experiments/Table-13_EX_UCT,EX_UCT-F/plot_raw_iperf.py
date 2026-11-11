#!/usr/bin/env python3
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import glob
import numpy as np
import os
import statistics
import time

font = {'weight' : 'normal',
        'size'   : 20}
matplotlib.rc('font', **font)
matplotlib.rc('lines', linewidth=2.0)
matplotlib.rc('lines', markersize=8)
matplotlib.rcParams['agg.path.chunksize'] = 10000

figSize = (24,12)
xLimit = (0,30)

flowToColor = {2201 : 'tab:blue',
               2202 : 'tab:orange',
               2203 : 'tab:green',
               2101 : 'tab:red',
               2102 : 'tab:purple',
               2103 : 'tab:brown',
               2301 : 'tab:pink',
               2302 : 'tab:gray',
               2303 : 'tab:olive',
               2304 : 'tab:cyan',
               2401 : 'black',
               2501 : 'black'}

flowToName = {2201 : 'Flow 2-SR-A-1 LIDAR',
              2202 : 'Flow 2-SR-A-2 RADAR',
              2203 : 'Flow 2-BE',
              2101 : 'Flow 1-SR-A-1 C and C',
              2102 : 'Flow 1-SR-A-2 Vid ADAS',
              2103 : 'Flow 1-BE',
              2301 : 'Flow 3-SR-B-1 RADAR',
              2302 : 'Flow 3-SR-B-2 ULTRA SOUND',
              2303 : 'Flow 3-SR-B-3 GPS',
              2304 : 'Flow 3-BE',
              2401 : 'Flow 4-BE',
              2501 : 'Flow 5-BE'}

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
        ax.plot([x - minTS for x in toPlot[iperfPort]['TS']], toPlot[iperfPort]['Val'], '.-', color=flowToColor[iperfPort], label=flowToName[iperfPort])

    ax.set_ylim(0,maxTP+10)
    ax.set_xlim(xLimit[0],xLimit[1])
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

def plotManualDelaycalcMultiFlow(experimentSubname, pathToExports, plotPath, endNodeNum, endiFace, iperfPorts):
    fl = pathToExports+'/pythonLog.txt'
    with open(fl, "a") as myFile:
        print('Plotting Delay for', experimentSubname, end='...\t', file=myFile)
    startTime = time.time()
    fig, ax = plt.subplots(1, figsize=figSize)
    maxHeight = 0
    minTS = float('inf')
    delay = {}
    for iperfPort in iperfPorts:
        prePath = pathToExports + '/' + experimentSubname + '/node-' + str(endNodeNum) + '/' + endiFace + 'DelayAndJitterFlowIperf' + str(iperfPort) + '.csv'
        fileName = glob.glob(prePath)
        df = pd.read_csv(fileName[0])
        maxHeight = max(maxHeight, max(df['Delay']))
        minTS = min(minTS, min(df['Timestamp']))
        delay[iperfPort] = {}
        delay[iperfPort]['TS'] = df['Timestamp']
        delay[iperfPort]['Val'] = [x/1e6 for x in df['Delay'].tolist()]

    for iperfPort in iperfPorts:
        ax.plot(delay[iperfPort]['TS'] - minTS, delay[iperfPort]['Val'], '.-', label=flowToName[iperfPort], zorder=iperfPort-980, color=flowToColor[iperfPort])

    ax.set_xlim(xLimit[0],xLimit[1])
    ax.grid(which='both')
    ax.set_ylim(0,maxHeight/1e6)
    ax.ticklabel_format(useOffset=False, style='plain')

    plt.legend()
    plt.xlabel('Experiment Time [s]')
    plt.ylabel('End-To-End Delay [ms]')

    # Plot saving code block
    plotName = 'iperfDelay_NodeDest-'+str(endNodeNum)+str(endiFace)+experimentSubname+'_ports'+str(iperfPorts)+'.png'
    plotPaths = ['/plots/', '/plots/delay/', '/plots/'+experimentSubname+'/']
    for pP in plotPaths:
        preOutPath = plotPath + pP
        if not os.path.exists(preOutPath):
            os.makedirs(preOutPath)
        fig.savefig(preOutPath + '/' + plotName, dpi=100, bbox_inches='tight', format='png')
    plt.close('all')

    with open(fl, "a") as myFile:
        print('It took', time.time() - startTime, 's', file=myFile)
    
    return minTS

def plotManualJittercalcMultiFlow(experimentSubname, pathToExports, plotPath, endNodeNum, endiFace, iperfPorts):
    fl = pathToExports+'/pythonLog.txt'
    with open(fl, "a") as myFile:
        print('Plotting Jitter for', experimentSubname, end='...\t', file=myFile)
    startTime = time.time()
    fig, ax = plt.subplots(1, figsize=figSize)
    maxHeight = 0
    minHeight = 0
    minTS = float('inf')
    jitter = {}
    for iperfPort in iperfPorts:
        prePath = pathToExports + '/' + experimentSubname + '/node-' + str(endNodeNum) + '/' + endiFace + 'DelayAndJitterFlowIperf' + str(iperfPort) + '.csv'
        fileName = glob.glob(prePath)
        df = pd.read_csv(fileName[0])
        maxHeight = max(maxHeight, max(df['Jitter']))
        minHeight = min(minHeight, min(df['Jitter']))
        minTS = min(minTS, min(df['Timestamp']))
        jitter[iperfPort] = {}
        jitter[iperfPort]['TS'] = df['Timestamp']
        jitter[iperfPort]['Val'] = [x/1e3 for x in df['Jitter'].tolist()]
    for iperfPort in iperfPorts:
        ax.plot(jitter[iperfPort]['TS'] - minTS, jitter[iperfPort]['Val'], '.-', label=flowToName[iperfPort], zorder=iperfPort-980, color=flowToColor[iperfPort])

    ax.set_xlim(xLimit[0],xLimit[1])
    ax.set_ylim(minHeight/1e3,maxHeight/1e3)
    ax.grid(which='both')
    ax.ticklabel_format(useOffset=False, style='plain')

    plt.legend()
    plt.xlabel('Experiment Time [s]')
    plt.ylabel('Jitter [\u03BCs]')

    # Plot saving code block
    plotName = 'iperfJitter_NodeDest-'+str(endNodeNum)+str(endiFace)+experimentSubname+'_ports'+str(iperfPorts)+'.png'
    plotPaths = ['/plots/', '/plots/jitter/', '/plots/'+experimentSubname+'/']
    for pP in plotPaths:
        preOutPath = plotPath + pP
        if not os.path.exists(preOutPath):
            os.makedirs(preOutPath)
        fig.savefig(preOutPath + '/' + plotName, dpi=100, bbox_inches='tight', format='png')
    plt.close('all')

    with open(fl, "a") as myFile:
        print('It took', time.time() - startTime, 's', file=myFile)

def plotManualJitterCDFcalcMultiFlow(experimentSubname, pathToExports, plotPath, endNodeNum, endiFace, iperfPorts):
    fl = pathToExports+'/pythonLog.txt'
    with open(fl, "a") as myFile:
        print('Plotting Jitter CDF for', experimentSubname, end='...\t', file=myFile)
    startTime = time.time()
    fig, ax = plt.subplots(1, figsize=figSize)
    absMax = 0
    jitter = {}
    for iperfPort in iperfPorts:
        prePath = pathToExports + '/' + experimentSubname + '/node-' + str(endNodeNum) + '/' + endiFace + 'DelayAndJitterFlowIperf' + str(iperfPort) + '.csv'
        fileName = glob.glob(prePath)
        df = pd.read_csv(fileName[0])
        jitter[iperfPort] = {}
        jitter[iperfPort]['Val'] = [x/1e3 for x in df['Jitter'].tolist()]
    for iperfPort in iperfPorts:
        sorted_data = np.sort(jitter[iperfPort]['Val'])
        linspaced = np.linspace(0, 1, len(jitter[iperfPort]['Val']), endpoint=True)
        absMax = max(absMax, max([abs(x) for x in sorted_data]))
        ax.plot(sorted_data, linspaced, '.-', label=flowToName[iperfPort], zorder=iperfPort-980, color=flowToColor[iperfPort])

    ax.set_xlim(-absMax,absMax)
    ax.grid(which='both')
    ax.ticklabel_format(useOffset=False, style='plain')

    plt.legend()
    plt.xlabel('Jitter [\u03BCs]')
    plt.ylabel('CDF')

    # Plot saving code block
    plotName = 'iperfJitterCDF_NodeDest-'+str(endNodeNum)+str(endiFace)+experimentSubname+'_ports'+str(iperfPorts)+'.png'
    plotPaths = ['/plots/', '/plots/jitterCDF/', '/plots/'+experimentSubname+'/']
    for pP in plotPaths:
        preOutPath = plotPath + pP
        if not os.path.exists(preOutPath):
            os.makedirs(preOutPath)
        fig.savefig(preOutPath + '/' + plotName, dpi=100, bbox_inches='tight', format='png')
    plt.close('all')

    with open(fl, "a") as myFile:
        print('It took', time.time() - startTime, 's', file=myFile)

def plotManualPacketLosscalcMultiFlow(experimentSubname, pathToExports, plotPath, endNodeNum, endiFace, iperfPorts, refTS):
    fl = pathToExports+'/pythonLog.txt'
    with open(fl, "a") as myFile:
        print('Plotting Packet Loss for', experimentSubname, end='...\t', file=myFile)
    startTime = time.time()
    fig, ax = plt.subplots(1, figsize=figSize)
    packetLoss = {}
    for iperfPort in iperfPorts:
        prePath = pathToExports + '/' + experimentSubname + '/node-' + str(endNodeNum) + '/' + endiFace + 'DelayAndJitterFlowIperf' + str(iperfPort) + '.csv'
        fileName = glob.glob(prePath)
        # print(fileName[0])
        df = pd.read_csv(fileName[0])
        cumulativePktLost = [x+1 for x in range(len(df['Timestamp Loss'].dropna()))]
        packetLoss[iperfPort] = {}
        packetLoss[iperfPort]['TS'] = df['Timestamp Loss'].dropna()
        packetLoss[iperfPort]['Val'] = cumulativePktLost
        
    for iperfPort in iperfPorts:
        ax.plot(packetLoss[iperfPort]['TS'] - refTS, packetLoss[iperfPort]['Val'], 'o-', label=flowToName[iperfPort], color=flowToColor[iperfPort])

    ax.set_xlim(xLimit[0],xLimit[1])
    ax.grid(which='both')
    ax.ticklabel_format(useOffset=False, style='plain')

    plt.legend()
    plt.xlabel('Experiment Time [s]')
    plt.ylabel('Cumulative Number of Lost Packets')

    # Plot saving code block
    plotName = 'iperfCumulativePacketLoss_NodeDest-'+str(endNodeNum)+str(endiFace)+experimentSubname+'_ports'+str(iperfPorts)+'.png'
    plotPaths = ['/plots/', '/plots/cumulativePacketLoss/', '/plots/'+experimentSubname+'/']
    for pP in plotPaths:
        preOutPath = plotPath + pP
        if not os.path.exists(preOutPath):
            os.makedirs(preOutPath)
        fig.savefig(preOutPath + '/' + plotName, dpi=100, bbox_inches='tight', format='png')
    plt.close('all')

    with open(fl, "a") as myFile:
        print('It took', time.time() - startTime, 's', file=myFile)

def tableSummarizeAllValuesFlow(experimentSubname, pathToExports, tablePath, endNodeNum, endiFace,ports, sourceOfPcap="iperf"):
    fl = pathToExports+'/pythonLog.txt'
    with open(fl, "a") as myFile:
        print('Preparing Table values for', experimentSubname, end='...\t', file=myFile)
    startTime = time.time()
    delay = {}
    jitter = {}
    packetLoss = {}
    tableName = 'iperfTable_NodeDest-'+str(endNodeNum)+str(endiFace)+experimentSubname+'.csv'
    tablePathLocal = '/plots/'+experimentSubname+'/'
    f2 = tablePath + tablePathLocal + tableName
    print(f2)
    with open(f2, "a") as myFile:
        print('Adding results for ', experimentSubname, end='...\t', file=myFile)
    
    for port in ports:
        prePath = pathToExports + '/' + experimentSubname + '/node-' + str(endNodeNum) + '/' + endiFace + 'DelayAndJitterFlowIperf' + str(port) + '.csv'
        fileName = glob.glob(prePath)
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
    percentileValue = 99
    for port in ports:
        port = int(port)
        global diff
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
            print('Packet send len of tcpdump:\n ', str(lenTCPDump), end='...\n', file=myFile)
            print(round(meanDelay, 4), "&", round(medianDelay, 4), "&", round(delay99Percentil, 4), "&", round(meanJitter, 4), "&", round(medianJitter, 4), "&", round(jitter99Percentil, 4), "&", lenTCPDump, end='...\n', file=myFile)
            print(meanDelay, "&", medianDelay, "&",delay99Percentil, "&", meanJitter, "&", medianJitter, "&", jitter99Percentil, "&", lenTCPDump, end='...\n', file=myFile)
   # Table saving code block
    with open(fl, "a") as myFile:
        print('It took', time.time() - startTime, 's', file=myFile)


def plotManualIfsCDFcalcMultiFlow(experimentSubname, pathToExports, plotPath, endNodeNum, endiFace, iperfPorts):
    fl = pathToExports+'/pythonLog.txt'
    with open(fl, "a") as myFile:
        print('Plotting Inter-Frame Spacing for', experimentSubname, end='...\t', file=myFile)
    startTime = time.time()
    fig, ax = plt.subplots(1, figsize=figSize)
    interFramSpacs = {}
    allVals = []
    for iperfPort in iperfPorts:
        prePath = pathToExports + '/' + experimentSubname + '/node-' + str(endNodeNum) + '/' + endiFace + 'DelayAndJitterFlowIperf' + str(iperfPort) + '.csv'
        fileName = glob.glob(prePath)
        df = pd.read_csv(fileName[0])
        timestamps = df['Timestamp'].dropna().tolist()
        ifs = [(x - y)*1e6 for x,y in zip(timestamps[1:], timestamps[:-1])]
        interFramSpacs[iperfPort] = {}
        interFramSpacs[iperfPort]['Val'] = ifs
        allVals.extend(ifs)
    for iperfPort in iperfPorts:
        sorted_data = np.sort(interFramSpacs[iperfPort]['Val'])
        linspaced = np.linspace(0, 1, len(interFramSpacs[iperfPort]['Val']), endpoint=True)
        lbl = 'Measured'
        if len(iperfPorts) > 1:
            lbl = flowToName[iperfPort]
        ax.plot(sorted_data, linspaced, '.-', label=lbl, zorder=iperfPort-980, color=flowToColor[iperfPort])

    if len(iperfPorts) <= 1: ax.vlines(100, ymin=0, ymax=1, alpha=0.9, zorder=1000, color='tab:red', label='Target')

    ax.set_xlim(0,max(allVals))
    ax.grid(which='both')
    ax.ticklabel_format(useOffset=False, style='plain')

    plt.legend()
    plt.xlabel('Inter-Frame Spacing [\u03BCs]')
    plt.ylabel('CDF')

    # Plot saving code block
    plotName = 'iperfInterFrameSpacingCDF_NodeDest-'+str(endNodeNum)+str(endiFace)+experimentSubname+'_ports'+str(iperfPorts)+'.png'
    plotPaths = ['/plots/', '/plots/ifsCDF/', '/plots/'+experimentSubname+'/']
    for pP in plotPaths:
        preOutPath = plotPath + pP
        if not os.path.exists(preOutPath):
            os.makedirs(preOutPath)
        fig.savefig(preOutPath + '/' + plotName, dpi=100, bbox_inches='tight', format='png')
    plt.close('all')

    with open(fl, "a") as myFile:
        print('It took', time.time() - startTime, 's', file=myFile)