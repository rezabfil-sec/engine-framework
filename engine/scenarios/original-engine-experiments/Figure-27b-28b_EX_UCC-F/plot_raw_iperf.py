#!/usr/bin/env python3
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import glob
import numpy as np
import os
import time

font = {'weight' : 'normal',
        'size'   : 20}
matplotlib.rc('font', **font)
matplotlib.rc('lines', linewidth=2.0)
matplotlib.rc('lines', markersize=8)
matplotlib.rcParams['agg.path.chunksize'] = 10000

figSize = (24,12)

flowToColor = {2201 : 'tab:blue',
               2202 : 'tab:orange',
               2203 : 'tab:green',
               2301 : 'tab:red',
               2302 : 'tab:purple',
               2303 : 'tab:brown',
               2304 : 'tab:pink',
               2101 : 'tab:gray',
               2102 : 'tab:olive',
               2103 : 'tab:cyan',
               2501 : 'black',
               2401 : 'yellow'}


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
        additive = ''
        if iperfPort == 1003 or iperfPort == 1004:
            additive = ' CBS'
        ax.plot(delay[iperfPort]['TS'] - minTS, delay[iperfPort]['Val'], '.-', label='Flow ' + str(iperfPort-1000) + additive, zorder=iperfPort-980, color=flowToColor[iperfPort])

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
        additive = ''
        if iperfPort == 1003 or iperfPort == 1004:
            additive = ' CBS'
        ax.plot(jitter[iperfPort]['TS'] - minTS, jitter[iperfPort]['Val'], '.-', label='Flow ' + str(iperfPort-1000) + additive, zorder=iperfPort-980, color=flowToColor[iperfPort])

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
        additive = ''
        if iperfPort == 1003 or iperfPort == 1004:
            additive = ' CBS'
        sorted_data = np.sort(jitter[iperfPort]['Val'])
        linspaced = np.linspace(0, 1, len(jitter[iperfPort]['Val']), endpoint=True)
        absMax = max(absMax, max([abs(x) for x in sorted_data]))
        ax.plot(sorted_data, linspaced, '.-', label='Flow ' + str(iperfPort-1000) + additive, zorder=iperfPort-980, color=flowToColor[iperfPort])

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
        additive = ''
        if iperfPort == 1003 or iperfPort == 1004:
            additive = ' CBS'
        ax.plot(packetLoss[iperfPort]['TS'] - refTS, packetLoss[iperfPort]['Val'], 'o-', label='Flow ' + str(iperfPort-1000) + additive, color=flowToColor[iperfPort])

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
        additive = ''
        if iperfPort == 1003 or iperfPort == 1004:
            additive = ' CBS'
        sorted_data = np.sort(interFramSpacs[iperfPort]['Val'])
        linspaced = np.linspace(0, 1, len(interFramSpacs[iperfPort]['Val']), endpoint=True)
        lbl = 'Measured'
        if len(iperfPorts) > 1:
            lbl = 'Flow ' + str(iperfPort-1000) + additive
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