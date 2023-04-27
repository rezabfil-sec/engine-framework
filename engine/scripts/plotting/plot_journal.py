#!/usr/bin/env python3
from itertools import starmap
# from turtle import color
import matplotlib
import matplotlib.pyplot as plt
import tikzplotlib
import pandas as pd
import glob
import numpy as np
import sys
import os

import tikzplot_save as tiksav

import statistics

import time
import datetime

font = {'weight' : 'normal',
                    'size'   : 20}
matplotlib.rc('font', **font)
matplotlib.rc('lines', linewidth=2.0)
matplotlib.rc('lines', markersize=8)

flowToColor = {1001 : 'tab:blue',
               1002 : 'tab:blue', # 'tab:orange',
               1003 : 'tab:blue', # 'tab:green',
               1004 : 'tab:blue', # 'tab:red',
               1005 : 'tab:purple',
               1006 : 'tab:brown',
               1007 : 'tab:pink',
               1008 : 'tab:gray',
               1009 : 'tab:olive',
               1010 : 'tab:cyan',
               1011 : 'black',
               6601 : 'tab:blue'}

figSize = (10,6)

lineStyles = [(0, (3, 1, 1, 1, 1, 1)), 'dashed', 'solid']

def plotManualIfscalcMultiFlow(experimentSubname, pathToExports, plotPath, endNodeNum, endiFace, iperfPorts):
    print('Plotting Inter-Frame Spacing for', experimentSubname, end='...\t')
    startTime = time.time()
    fig, ax = plt.subplots(1, figsize=figSize)
    interFramSpacs = {}
    allVals = []
    for iperfPort in iperfPorts:
        prePath = pathToExports + '/' + experimentSubname + '/node-' + str(endNodeNum) + '/' + endiFace + 'DelayAndJitterFlow*' + str(iperfPort) + '.csv'
        fileName = glob.glob(prePath)
        df = pd.read_csv(fileName[0])
        timestamps = df['Timestamp'].dropna().tolist()
        ifs = [(x - y)*1e6 for x,y in zip(timestamps[1:], timestamps[:-1])]
        interFramSpacs[iperfPort] = {}
        interFramSpacs[iperfPort]['TS'] = [x - timestamps[0] for x in timestamps[1:]]
        interFramSpacs[iperfPort]['Val'] = ifs
        allVals.extend(ifs)
    for iperfPort in iperfPorts:
        additive = ''
        if iperfPort == 1003 or iperfPort == 1004:
            additive = ' CBS'
        sorted_data = [x for x in np.sort(interFramSpacs[iperfPort]['Val']) if x < 120 and x > 80]
        linspaced = np.linspace(0, 1, len(sorted_data), endpoint=True)
        lbl = 'Measured'
        if len(iperfPorts) > 1:
            lbl = 'Flow ' + str(iperfPort-1000) + additive
        ax.plot(sorted_data, linspaced, '-', label=lbl, zorder=iperfPort-980, color=flowToColor[iperfPort], linewidth=3, markersize=2)

    if len(iperfPorts) <= 1: 
        ax.plot([100 for _ in range(0,10000)], np.linspace(0, 1, 10000, endpoint=True), '-', alpha=0.9, zorder=5000, linewidth=3, markersize=1, color='tab:red', label='Target')

    ax.set_xlim(79,121)
    ax.set_xticks(np.arange(85,121,5))
    ax.set_xticks(np.arange(85,121,1), minor=True)
    ax.set_yticks(np.arange(0,1.1,0.2))
    ax.set_yticks(np.arange(0,1.1,0.1), minor=True)
    ax.grid(which='minor', alpha=0.2)
    ax.grid(which='major', alpha=0.5)
    ax.ticklabel_format(useOffset=False, style='plain')
    
    plt.minorticks_on()

    plt.legend()
    plt.xlabel('Inter-Frame Spacing [us]')
    plt.ylabel('ECDF')

    # Plot saving code block
    plotName = 'iperfInterFrameSpacing_NodeDest-'+str(endNodeNum)+str(endiFace)+experimentSubname+'_ports'+str(iperfPorts)+'.'
    plotPaths = ['/plots/ifs/']
    for pP in plotPaths:
        preOutPath = plotPath + pP
        if not os.path.exists(preOutPath):
            os.makedirs(preOutPath)
        fig.savefig(preOutPath + '/' + plotName+'png', dpi=100, bbox_inches='tight', format='png')
        tikzplotlib.clean_figure()
        axisParamList = ["minor grid style={line width=.001pt, draw=gray!10}","major grid style={line width=.5pt,draw=gray!50}","minor x tick num=0","minor y tick num=0","ytick={0,0.2,0.4,0.6,0.8,1.0}"]
        tikzplotlib.save(preOutPath +'/'+plotName+'tex', standalone=True, textsize=30, dpi=300, axis_width='275', axis_height='125', encoding='utf-8', extra_axis_parameters=axisParamList)
        os.chdir(preOutPath)
        os.system('pdflatex -synctex=1 -interaction=nonstopmode --shell-escape --extra-mem-bot=999999999999999999 ' + preOutPath +'/'+plotName+'tex')
        os.system('pdftops -eps ' + preOutPath+'/'+plotName+'pdf ' + preOutPath+'/'+plotName+'eps')

        # Cleanup after pdflatex
        for f in glob.glob('*.log'):
            os.remove(f)
        for f in glob.glob('*.aux'):
            os.remove(f)
        for f in glob.glob('*.gz'):
            os.remove(f)
        os.getcwd()

    plt.close('all')

    print('It took', time.time() - startTime, 's')


def plotManualDelaycalcMultiFlow(experimentSubname, pathToExports, plotPath, endNodeNum, endiFace, iperfPorts,xTime,yHigh,axisParamList):
    print('Plotting Delay for', experimentSubname, end='...\n')
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
        ts = df['Timestamp'].tolist()
        val = df['Delay'].tolist()
        limTS = min(ts)+16*60
        delay[iperfPort]['TS'] = [x for x,_ in zip(ts,val) if x < limTS]
        delay[iperfPort]['Val'] = [x/1e6 for x,y in zip(val,ts) if y < limTS]
        

    for iperfPort in iperfPorts:
        additive = ''
        if iperfPort == 1003 or iperfPort == 1004:
            additive = ' CBS'
        timest = [(x - minTS)/60 for x in delay[iperfPort]['TS']]
        vals = delay[iperfPort]['Val']
        ax.plot(timest, vals, '-', label='Flow ' + str(iperfPort-1000) + additive, zorder=-1, color=flowToColor[iperfPort], linewidth=0.5)
        recentSpkBegin = 100
        recentSpkEnd = 0
        distanceThreshold = 0.2
        maxHeightSpk = 0
        
        spikes = []
        spikeThreshold = 6
        
        for x,y in zip(timest,vals):
            if y > spikeThreshold and recentSpkBegin == 100:
                recentSpkBegin = x
                maxHeightSpk = y
                
            elif y > spikeThreshold and x-recentSpkBegin < distanceThreshold  and x-recentSpkBegin > 0:
                recentSpkEnd = x
                maxHeightSpk = max(maxHeightSpk,y)
            elif y <= spikeThreshold and x-recentSpkBegin >= distanceThreshold:
                print('Spike:', recentSpkBegin, recentSpkEnd, x, y, distanceThreshold)
                spikes.append((recentSpkBegin,recentSpkEnd, maxHeightSpk))
                recentSpkBegin = 100
                recentSpkEnd = 0
                maxHeightSpk = 0
        
        for tm in spikes:
            plt.arrow((tm[0]+tm[1])/2, tm[2]+12, 0, -10, color='tab:red', width=0.01, head_width=0.2, head_length=2, length_includes_head=True)

    ax.set_xlim(0,xTime)
    ax.grid(which='both')
    ax.set_ylim(0,yHigh)
    ax.ticklabel_format(useOffset=False, style='plain')

    plt.xlabel('Experiment Time [min]')
    plt.ylabel('Delay [ms]')

    # Plot saving code block
    plotName = 'delaySpikes'+experimentSubname
    plotPaths = ['/plots/delay/']
    for pP in plotPaths:
        preOutPath = plotPath + pP
        if not os.path.exists(preOutPath):
            os.makedirs(preOutPath)
        print('Exporting to png...', end='\t')
        fig.savefig(preOutPath + '/' + plotName + '.png', dpi=100, bbox_inches='tight', format='png')
        print('Done!')
        tiksav.saveTikz(plotName, preOutPath, axisParamList, 'small', True, False)
    plt.close('all')

    print('Plotting took', time.time() - startTime, 's total')
    
    return minTS


def plotSysOptDelay(experimentSubname, pathToExports, plotPath, endNodeNum, endiFace, iperfPorts, xTime, yHigh, axisParamList, hLines, extExpName):
    print('Plotting Delay for', experimentSubname, end='...\n')
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
        ts = df['Timestamp'].tolist()
        val = df['Delay'].tolist()
        limTS = min(ts)+xTime
        delay[iperfPort]['TS'] = [x for x,_ in zip(ts,val) if x < limTS]
        delay[iperfPort]['Val'] = [x/1e6 for x,y in zip(val,ts) if y < limTS]
        

    for iperfPort in iperfPorts:
        additive = ''
        if iperfPort == 1003 or iperfPort == 1004:
            additive = ' CBS'
        timest = [(x - minTS) for x in delay[iperfPort]['TS']]
        vals = delay[iperfPort]['Val']
        ax.plot(timest, vals, '-', label='Flow ' + str(iperfPort-1000) + additive, zorder=-1, color=flowToColor[iperfPort], linewidth=0.5, markersize=0.5)

    for hLine in hLines:
        ax.plot([0,xTime], [hLine,hLine], color='tab:red', linewidth=2, linestyle='dashed')

    ax.set_xlim(0,xTime)
    ax.grid(which='both')
    ax.set_ylim(0,yHigh)
    ax.ticklabel_format(useOffset=False, style='plain')

    plt.xlabel('Experiment Time [s]')
    plt.ylabel('Delay [ms]')

    # Plot saving code block
    plotName = 'sysOpt'+extExpName
    plotPaths = ['/sysOpt/']
    for pP in plotPaths:
        preOutPath = plotPath + pP
        if not os.path.exists(preOutPath):
            os.makedirs(preOutPath)
        print('Exporting to png...', end='\t')
        fig.savefig(preOutPath + '/' + plotName + '.png', dpi=100, bbox_inches='tight', format='png')
        print('Done!')
        tiksav.saveTikz(plotName, preOutPath, axisParamList, 'small', True, False)
    plt.close('all')

    print('Plotting took', time.time() - startTime, 's total')
    
    return minTS

def plotSysOptJitter(experimentSubname, pathToExports, plotPath, endNodeNum, endiFace, iperfPorts, xTime, yHigh, axisParamList, extExpName):
    print('Plotting Delay for', experimentSubname, end='...\n')
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
        ts = df['Timestamp'].tolist()
        val = df['Jitter'].tolist()
        limTS = min(ts)+xTime
        delay[iperfPort]['TS'] = [x for x,_ in zip(ts,val) if x < limTS]
        delay[iperfPort]['Val'] = [x/1e3 for x,y in zip(val,ts) if y < limTS]
        

    for iperfPort in iperfPorts:
        additive = ''
        if iperfPort == 1003 or iperfPort == 1004:
            additive = ' CBS'
        vals = delay[iperfPort]['Val']
        sorted_data = [x for x in np.sort(vals) if x < yHigh and x > -yHigh]
        linspaced = np.linspace(0, 1, len(sorted_data), endpoint=True)
        ax.plot(sorted_data, linspaced, '-', label='Flow ' + str(iperfPort-1000) + additive, zorder=-1, color=flowToColor[iperfPort], linewidth=2, markersize=1)

    ax.set_xlim(-yHigh,yHigh)
    ax.grid(which='both')
    ax.ticklabel_format(useOffset=False, style='plain')

    plt.xlabel('ECDF')
    plt.ylabel('Jitter [us]')

    # Plot saving code block
    plotName = 'sysOptJitter'+extExpName
    plotPaths = ['/sysOpt/']
    for pP in plotPaths:
        preOutPath = plotPath + pP
        if not os.path.exists(preOutPath):
            os.makedirs(preOutPath)
        print('Exporting to png...', end='\t')
        fig.savefig(preOutPath + '/' + plotName + '.png', dpi=100, bbox_inches='tight', format='png')
        print('Done!')
        tiksav.saveTikz(plotName, preOutPath, axisParamList, 'small', True, False)
    plt.close('all')

    print('Plotting took', time.time() - startTime, 's total')
    
    return minTS

def typeToName(type):
    if type == 'offload':
        return 'Off'
    elif type == 'nooffload':
        return 'No Off'
    elif type == 'offload*175delta':
        return 'Off, 175us'
    elif type == 'offload*275delta':
        return 'Off, 275us'
    elif type == 'nooffload*175delta':
        return 'No Off, 175us'
    elif type == 'nooffload*275delta':
        return 'No Off, 175us'
    elif type == 'with-hop-cbs-cs':
        return '$EX_{CS2}$'
    elif type == 'no-hop-cbs-cs':
        return '$EX_{CS1}$'
    elif type == 'with-hop-cbs-cm':
        return '$EX_{CM2}$'
    elif type == 'no-hop-cbs-cm':
        return '$EX_{CM1}$'
    else:
        return type

def typeToColor(type):
    if type == 'offload':
        return 'tab:blue'
    elif type == 'nooffload':
        return 'tab:orange'
    elif type == 'offload*175delta':
        return 'tab:blue'
    elif type == 'offload*275delta':
        return 'tab:orange'
    elif type == 'nooffload*175delta':
        return 'tab:green'
    elif type == 'nooffload*275delta':
        return 'tab:purple'
    elif type == 'with-hop-cbs':
        return 'tab:blue'
    elif type == 'no-hop-cbs':
        return 'tab:orange'
    else:
        return 'black'

def plotDelayGenericLine(scenarioFolders, expTypes, identRange, pathToExports, plotPath, yMax, plotName, type, totalPkt, port, modif):
    print('Plotting', type, 'for campaigns:', scenarioFolders, 'and experiment types:', expTypes, end='...\n')
    startTime = time.time()
    fig, ax = plt.subplots(1, figsize=figSize)
    normalTypes = ['Delay', 'Jitter']
    if type == 'PktDrop':
        ax2 = ax.twinx()
    expDict = {}
    for scenarioF in scenarioFolders:
        possibleFiles = glob.glob(pathToExports+'/'+scenarioF+'/*/*/*DelayAndJitter*'+str(port)+'*.csv', recursive=True)
        for file in possibleFiles:
            name = file.split(scenarioF+'/')[-1].split('/')[0]
            expDict[name] = {}
            expDict[name]['file'] = file
            expDict[name]['ident'] = int(name.split(identRange[0])[-1].split(identRange[1])[0])
            for expType in expTypes:
                matchList = []
                if '*' in expType:
                    matchList = expType.split('*')
                else:
                    matchList = [expType]
                if all(word in name for word in matchList):
                    expDict[name]['type'] = expType

    resultDict = {}
    for expType in expTypes:
        resultDict[expType] = {}

    for experiment in expDict:
        expInfo = expDict[experiment]
        print(experiment)
        df = pd.read_csv(expInfo['file'])
        resultDict[expInfo['type']][expInfo['ident']] = {}
        if type in normalTypes:
            dataList = df[type].dropna().tolist()
            if type == 'Delay':
                dataList = [x/1e6 for x in dataList]
            elif type == 'Jitter':
                dataList = [x/1e3 for x in dataList]
            resultDict[expInfo['type']][expInfo['ident']]['mean'] = statistics.mean(dataList)
            resultDict[expInfo['type']][expInfo['ident']]['median'] = statistics.median(dataList)
            resultDict[expInfo['type']][expInfo['ident']]['min'] = min(dataList)
            resultDict[expInfo['type']][expInfo['ident']]['max'] = max(dataList)
            resultDict[expInfo['type']][expInfo['ident']]['1pcile'] = np.percentile(dataList,1)
            resultDict[expInfo['type']][expInfo['ident']]['99pcile'] = np.percentile(dataList,99)
        elif type == 'PktDrop':
            dataList = df['Delay'].dropna().tolist()
            receivedLen = len(dataList)
            resultDict[expInfo['type']][expInfo['ident']]['received'] = receivedLen
            resultDict[expInfo['type']][expInfo['ident']]['total'] = totalPkt
            resultDict[expInfo['type']][expInfo['ident']]['drop'] = (totalPkt-receivedLen)*100/totalPkt
        

    for typeRes in resultDict:
        dataDict = resultDict[typeRes]
        sortedIdent = sorted(dataDict)
        if type in normalTypes:
            xArr = []
            meanArr = []
            topArr = []
            botArr = []
            per99 = []
            per1 = []
            for exp in sortedIdent:
                expInfo = dataDict[exp]
                xArr.append(exp)
                meanArr.append(expInfo['mean'])
                per99.append(expInfo['99pcile'])
                per1.append(expInfo['1pcile'])
                topArr.append(expInfo['max'])
                botArr.append(expInfo['min'])
            ax.plot(xArr, meanArr, 'o-', markersize=2, label=typeToName(typeRes+modif), color=typeToColor(typeRes))
            ax.plot(xArr, per99, linestyle='dotted', linewidth=2, color=typeToColor(typeRes), alpha=0.6)
            ax.plot(xArr, per1, linestyle='dotted', linewidth=2, color=typeToColor(typeRes), alpha=0.6)
            if type == 'Delay':
                ax.fill_between(xArr,botArr,topArr,label=typeToName(typeRes+modif)+' min-max',alpha=.4, color=typeToColor(typeRes))
            else:
                ax.fill_between(xArr,botArr,topArr,alpha=.4, color=typeToColor(typeRes))
        elif type == 'PktDrop':
            xArr = []
            rcvdPkt = []
            dropPkt = []
            for exp in sortedIdent:
                expInfo = dataDict[exp]
                xArr.append(exp)
                rcvdPkt.append(expInfo['received'])
                dropPkt.append(expInfo['drop'])
            ax.plot(xArr, rcvdPkt, 'o--', markersize=2, label=typeToName(typeRes+modif), color=typeToColor(typeRes), zorder=-1)
            ax2.plot(xArr, dropPkt, 's-', markersize=2, label=typeToName(typeRes+modif), color=typeToColor(typeRes), zorder=-1)

    if any('ETF' in str for str in scenarioFolders) or any('TAPRIO' in str for str in scenarioFolders):
        plt.xlabel('Delta [us]')
    else :
        plt.xlabel('Number of Hops')
    if type == 'Delay':
        if port == 1004:
            ax.hlines([2], xmin=1, xmax=7, colors='red', linestyles='dashed')
        ax.set_ylim(-0.01*yMax,1.01*yMax)    
        plt.ylabel('Delay [ms]')
        plt.legend(loc='upper left', fontsize=10, ncol=2)
    elif type == 'Jitter':
        if port == 1004:
            ax.hlines([-125,125], xmin=1, xmax=7, colors='red', linestyles='dashed')
        if port == 1003:
            ax.hlines([-1000,1000], xmin=1, xmax=7, colors='red', linestyles='dashed')
        ax.set_ylim(-1.01*yMax,1.01*yMax)
        plt.ylabel('Jitter [us]')
        plt.yscale('symlog')
        plt.legend(loc='upper left', fontsize=10, ncol=2)
    elif type == 'PktDrop':
        if any('ETF' in str for str in scenarioFolders): 
            ax.set_ylim(297000, 300500)
            ax2.set_ylim(0,1.4)
        if any('TAPRIO' in str for str in scenarioFolders): 
            ax.set_ylim(99980, 100000)
            ax2.set_ylim(0,0.04)
        ax.ticklabel_format(useOffset=False)    
        ax.set_ylabel('Recieved')
        ax2.set_ylabel('Drop Rate [%]')
        ax.legend(loc='upper left', fontsize=10, ncol=2)
        ax2.legend(loc='upper right', fontsize=10, ncol=1)

    ax.grid(which='both')
    

    preOutPath = plotPath + '/plots/'
    if not os.path.exists(preOutPath):
        os.makedirs(preOutPath)

    outPath = preOutPath + plotName + '.png'
    fig.savefig(outPath, dpi=100, bbox_inches='tight', format='png')
    if type == 'Delay':
        tiksav.saveTikz(plotName, preOutPath, ["minor grid style={line width=.001pt, draw=gray!10}","major grid style={line width=.5pt,draw=gray!50}","minor x tick num=0","minor y tick num=0","legend style={font=\\tiny}"], 'small', True, False)
    elif type == 'Jitter':
        tiksav.saveTikz(plotName, preOutPath, ["minor grid style={line width=.001pt, draw=gray!10}","major grid style={line width=.5pt,draw=gray!50}","minor x tick num=0","minor y tick num=0","legend style={font=\\tiny}"], 'small', True, True)
    elif type == 'PktDrop':
        if any('TAPRIO' in str for str in scenarioFolders): tiksav.saveTikz(plotName, preOutPath, ["minor grid style={line width=.001pt, draw=gray!10}","major grid style={line width=.5pt,draw=gray!50}","minor x tick num=0","minor y tick num=0","legend style={font=\\tiny}", "yticklabel style={/pgf/number format/fixed, /pgf/number format/precision=2, /pgf/number format/fixed zerofill}", "scaled y ticks=false", "yticklabels={0,0.01,0.02,0.03,0.04,99980,99985,99990,99995,100000}", "ytick={0,0.01,0.02,0.03,0.04,99980,99985,99990,99995,100000}"], 'small', False, False) #"ytick={0,0.4,0.8,1.2,297000,298000,299000,300000}" ; "ytick={0,0.01,0.02,0.03,0.04,99980,99985,99990,99995,100000}"
        if any('ETF' in str for str in scenarioFolders): tiksav.saveTikz(plotName, preOutPath, ["minor grid style={line width=.001pt, draw=gray!10}","major grid style={line width=.5pt,draw=gray!50}","minor x tick num=0","minor y tick num=0","legend style={font=\\tiny}", "yticklabel style={/pgf/number format/fixed, /pgf/number format/precision=2, /pgf/number format/fixed zerofill}", "scaled y ticks=false", "ytick={0,0.4,0.8,1.2,297000,298000,299000,300000}", "yticklabels={0,0.4,0.8,1.2,297000,298000,299000,300000}"], 'small', False, False) #"ytick={0,0.4,0.8,1.2,297000,298000,299000,300000}" ; "ytick={0,0.01,0.02,0.03,0.04,99980,99985,99990,99995,100000}"
    plt.close('all')
    print('It took', time.time() - startTime, 's')

def plotDelayUseCase(experimentSubnames, pathToExports, plotPath, endNodeNum, iperfPorts, yMax, plotName, type):
    print('Plotting Delay for ', experimentSubnames, end='...\n')
    startTime = time.time()
    fig, ax = plt.subplots(1, figsize=figSize)
    enum = 0
    ticks = []
    labels = []
    means = []
    mins = []
    maxs = []
    for experimentSubname in experimentSubnames:
        prePath = pathToExports + '/' + experimentSubname + '/node-' + str(endNodeNum) + '/*'
        possibleFiles = glob.glob(prePath)
        for flow in iperfPorts:
            flowPorts = iperfPorts[flow]
            delays = []
            for port in flowPorts:
                for file in possibleFiles:
                    if str(port) in file and 'DelayAndJitter' in file:
                        print(port, file)
                        df = pd.read_csv(file)
                        delays.extend(df[type].dropna().tolist())
            if len(delays) > 0:
                dela = sorted([float(x) for x in delays])
                if type == 'Delay':
                    dela = [x/1e6 for x in dela]
                elif type == 'Jitter':
                    dela = [x/1e3 for x in dela]
                print('\t',round(min(dela),2), '\t;', round(max(dela),2), '\t;', round(statistics.mean(dela),2), '\t;', round(statistics.median(dela),2), '\t;', round(len(dela),2))
                ax.boxplot(dela, positions=[enum], notch=False, patch_artist=True,
                    boxprops=dict(facecolor='white', color='black'),
                    capprops=dict(color='black'),
                    whiskerprops=dict(color='black'),
                    flierprops=dict(color='black', markeredgecolor='black', markersize=3, linewidth=0.5),
                    widths=0.75, zorder=-1)

                means.append(statistics.mean(dela))
                mins.append(min(dela))
                maxs.append(max(dela))
                ticks.append(enum)
                labels.append(str(flow))
                enum += 1

    ax.plot(ticks, means, '^', color='tab:green', markersize=4.5, label='Mean')
    ax.plot(ticks, maxs, 'D', color='tab:blue', markersize=4.5, label='Max')
    ax.plot(ticks, mins, 'D', color='tab:purple', markersize=4.5, label='Min')

    plt.xticks(ticks, labels, rotation=30, ha='right')
    plt.xlabel('Flow Identifier')
    ax.set_xlim(-1,enum)
    if type == 'Delay':
        ax.set_ylim(-0.01*yMax,1.01*yMax)    
        plt.ylabel('Delay [ms]')
    elif type == 'Jitter':
        ax.set_ylim(-1.01*yMax,1.01*yMax)
        plt.ylabel('Jitter [us]')
        plt.yscale('symlog')

    ax.grid(which='both')
    plt.legend(loc='upper left', fontsize=10)
    

    preOutPath = plotPath + '/plots/'
    if not os.path.exists(preOutPath):
        os.makedirs(preOutPath)

    outPath = preOutPath + plotName + '.png'
    fig.savefig(outPath, dpi=100, bbox_inches='tight', format='png')
    if type == 'Delay':
        tiksav.saveTikz(plotName, preOutPath, ["minor grid style={line width=.001pt, draw=gray!10}","major grid style={line width=.5pt,draw=gray!50}","minor x tick num=0","minor y tick num=0","legend style={font=\\tiny}"], 'small', True, False)
    elif type == 'Jitter':
        tiksav.saveTikz(plotName, preOutPath, ["minor grid style={line width=.001pt, draw=gray!10}","major grid style={line width=.5pt,draw=gray!50}","minor x tick num=0","minor y tick num=0","legend style={font=\\tiny}"], 'small', True, True)
    plt.close('all')
    print('It took', time.time() - startTime, 's')

def plotTaprioShift(experimentSubnames, pathToExports, plotPath, endNodeNum, iperfPorts, yMax, plotName, type):
    print('Plotting Delay for ', experimentSubnames, end='...\n')
    startTime = time.time()
    fig, ax = plt.subplots(1, figsize=figSize)
    enum = 0
    ticks = []
    labels = []
    means = []
    mins = []
    maxs = []
    for experimentSubname in experimentSubnames:
        prePath = pathToExports + '/' + experimentSubname + '/node-' + str(endNodeNum) + '/*'
        possibleFiles = glob.glob(prePath)
        for flow in iperfPorts:
            flowPorts = iperfPorts[flow]
            delays = []
            for port in flowPorts:
                for file in possibleFiles:
                    if str(port) in file and 'DelayAndJitter' in file:
                        print(port, file)
                        df = pd.read_csv(file)
                        delays.extend(df[type].dropna().tolist())
            if len(delays) > 0:
                dela = sorted([float(x) for x in delays])
                if type == 'Delay':
                    dela = [x/1e6 for x in dela]
                    print(len([x for x in dela if x > 2.0]))
                elif type == 'Jitter':
                    dela = [x/1e3 for x in dela]
                print('\t',round(min(dela),2), '\t;', round(max(dela),2), '\t;', round(statistics.mean(dela),2), '\t;', round(statistics.median(dela),2), '\t;', round(len(dela),2))
                ax.boxplot(dela, positions=[enum], notch=False, patch_artist=True,
                    boxprops=dict(facecolor='white', color='black'),
                    capprops=dict(color='black'),
                    whiskerprops=dict(color='black'),
                    flierprops=dict(color='black', markeredgecolor='black', markersize=3, linewidth=0.5),
                    widths=0.75, zorder=-1)

                means.append(statistics.mean(dela))
                mins.append(min(dela))
                maxs.append(max(dela))
                ticks.append(enum)
                lblName = ''
                if '_offload' in experimentSubname:
                    lblName = 'Offload '
                elif '_nooffload' in experimentSubname:
                    lblName = 'No Offload '
                else:
                    lblName = str(flow)
                if '200perhop_400windows' in experimentSubname:
                    lblName += '$EX_{TS-T}$'
                elif '20perhop_40windows' in experimentSubname:
                    lblName += '$EX_{TS-W}$'
                labels.append(lblName)
                enum += 1

    ax.plot(ticks, means, '^', color='tab:green', markersize=4.5, label='Mean')
    ax.plot(ticks, maxs, 'D', color='tab:blue', markersize=4.5, label='Max')
    ax.plot(ticks, mins, 'D', color='tab:purple', markersize=4.5, label='Min')

    plt.xticks(ticks, labels)
    plt.xlabel('Experiment')
    ax.set_xlim(-0.8,enum-0.2)
    if type == 'Delay':
        ax.hlines([2], xmin=-0.8, xmax=enum-0.2, colors='red', linestyles='dashed')
        ax.set_ylim(-0.01*yMax,1.01*yMax)    
        plt.ylabel('Delay [ms]')
    elif type == 'Jitter':
        ax.hlines([-125, 125], xmin=-0.8, xmax=enum-0.2, colors='red', linestyles='dashed')
        ax.set_ylim(-1.01*yMax,1.01*yMax)
        plt.ylabel('Jitter [us]')
        plt.yscale('symlog')

    ax.grid(which='both')
    plt.legend(loc='upper left', fontsize=10)
    

    preOutPath = plotPath + '/plots/'
    if not os.path.exists(preOutPath):
        os.makedirs(preOutPath)

    outPath = preOutPath + plotName + '.png'
    fig.savefig(outPath, dpi=100, bbox_inches='tight', format='png')
    if type == 'Delay':
        tiksav.saveTikz(plotName, preOutPath, ["minor grid style={line width=.001pt, draw=gray!10}","major grid style={line width=.5pt,draw=gray!50}","minor x tick num=0","minor y tick num=0","legend style={font=\\tiny}", "xticklabel style={align=center,text width=2.5cm}"], 'small', False, False)
    elif type == 'Jitter':
        tiksav.saveTikz(plotName, preOutPath, ["minor grid style={line width=.001pt, draw=gray!10}","major grid style={line width=.5pt,draw=gray!50}","minor x tick num=0","minor y tick num=0","legend style={font=\\tiny}", "xticklabel style={align=center,text width=2.5cm}"], 'small', True, True)
    plt.close('all')
    print('It took', time.time() - startTime, 's')


# Common function parameters:
prePathToResults = # Put path to your result folder here!!!
journalPlotFolder = prePathToResults + 'ieeeAccessPlots/'

### Figure-9
plotManualIfscalcMultiFlow('4-queue_2-cbs_2-be_1-stream_1-hop-cbs100-iperf100', prePathToResults + 'Figure-9', journalPlotFolder, 3, 'enp3s0', [1003])

### Figure-10
plotManualIfscalcMultiFlow('1_hop-etf_100_strict_nooffload_d300_zgw', prePathToResults + 'Figure-10', journalPlotFolder, 2, 'enp5s0', [6601])

### Figure-12_EX_SP1
plotManualDelaycalcMultiFlow('4-queue_2-cbs_2-be_1-streams_3-hop_with-hop-cbs-iperf-line-limit100-20min', prePathToResults + 'Figure-12_EX_SP1', journalPlotFolder, 4, 'enp3s0', [1004],16,90, [])

### Figure-13_EX_SP2
# For plotting of this figure see the folder in the results

### Figure-14_EX_SP3
plotManualDelaycalcMultiFlow('4-queue_2-cbs_2-be_1-streams_3-hop_with-hop-cbs-iperf-line-limit100-2min', prePathToResults + 'Figure-14_EX_SP3', journalPlotFolder, 4, 'enp3s0', [1004],3,1.1, ["minor grid style={line width=.001pt, draw=gray!10}","major grid style={line width=.5pt,draw=gray!50}","minor x tick num=0","minor y tick num=0","ytick={0,0.2,0.4,0.6,0.8,1.0}"])

### Figure-15a-16a_EX_SO1
plotSysOptDelay('4-queue_2-cbs_2-be_1-streams_2-hop_with-hop-cbs-iperf-line-limit100-2min-nocpuperf', prePathToResults + 'Figure-15a-16a_EX_SO1', journalPlotFolder, 3, 'enp5s0', [1004],10,0.75, ["minor grid style={line width=.001pt, draw=gray!10}","major grid style={line width=.5pt,draw=gray!50}","minor x tick num=0","minor y tick num=0","ytick={0,0.1,0.2,0.3,0.4,0.5,0.6,0.7}"], [0.15,0.35], 'EX-SO3')
plotSysOptJitter('4-queue_2-cbs_2-be_1-streams_2-hop_with-hop-cbs-iperf-line-limit100-2min-nocpuperf', prePathToResults + 'Figure-15a-16a_EX_SO1', journalPlotFolder, 3, 'enp5s0', [1004],10,300, ["minor grid style={line width=.001pt, draw=gray!10}","major grid style={line width=.5pt,draw=gray!50}","minor x tick num=0","minor y tick num=0","ytick={0,0.2,0.4,0.6,0.8,1.0}"], 'EX-SO3')

### Figure-15b-16b_EX_SO2
plotSysOptDelay('4-queue_2-cbs_2-be_1-streams_2-hop_with-hop-cbs-iperf-line-limit100-2min-noturbo-noht-cpuperf', prePathToResults + 'Figure-15b-16b_EX_SO2', journalPlotFolder, 3, 'enp5s0', [1004],10,0.75, ["minor grid style={line width=.001pt, draw=gray!10}","major grid style={line width=.5pt,draw=gray!50}","minor x tick num=0","minor y tick num=0","ytick={0,0.1,0.2,0.3,0.4,0.5,0.6,0.7}"], [0.15,0.35], 'EX-SO1')
plotSysOptJitter('4-queue_2-cbs_2-be_1-streams_2-hop_with-hop-cbs-iperf-line-limit100-2min-noturbo-noht-cpuperf', prePathToResults + 'Figure-15b-16b_EX_SO2', journalPlotFolder, 3, 'enp5s0', [1004],10,300, ["minor grid style={line width=.001pt, draw=gray!10}","major grid style={line width=.5pt,draw=gray!50}","minor x tick num=0","minor y tick num=0","ytick={0,0.2,0.4,0.6,0.8,1.0}"], 'EX-SO1')

### Figure-15c-16c_EX-SO3
plotSysOptDelay('4-queue_2-cbs_2-be_1-streams_2-hop_with-hop-cbs-iperf-line-limit100-2min-cpuperf-noht', prePathToResults + 'Figure-15c-16c_EX_SO3', journalPlotFolder, 3, 'enp5s0', [1004],10,0.75, ["minor grid style={line width=.001pt, draw=gray!10}","major grid style={line width=.5pt,draw=gray!50}","minor x tick num=0","minor y tick num=0","ytick={0,0.1,0.2,0.3,0.4,0.5,0.6,0.7}"], [0.15,0.35], 'EX-SO2')
plotSysOptJitter('4-queue_2-cbs_2-be_1-streams_2-hop_with-hop-cbs-iperf-line-limit100-2min-cpuperf-noht', prePathToResults + 'Figure-15c-16c_EX_SO3', journalPlotFolder, 3, 'enp5s0', [1004],10,300, ["minor grid style={line width=.001pt, draw=gray!10}","major grid style={line width=.5pt,draw=gray!50}","minor x tick num=0","minor y tick num=0","ytick={0,0.2,0.4,0.6,0.8,1.0}"], 'EX-SO2')

### Figure-15d-16d_EX-SO4
plotSysOptDelay('4-queue_2-cbs_2-be_1-streams_2-hop_with-hop-cbs-iperf-line-limit100-2min-cpuperf', prePathToResults + 'Figure-15d-16d_EX_SO4', journalPlotFolder, 3, 'enp5s0', [1004],10,0.75, ["minor grid style={line width=.001pt, draw=gray!10}","major grid style={line width=.5pt,draw=gray!50}","minor x tick num=0","minor y tick num=0","ytick={0,0.1,0.2,0.3,0.4,0.5,0.6,0.7}"], [0.15,0.35], 'EX-SO4')
plotSysOptJitter('4-queue_2-cbs_2-be_1-streams_2-hop_with-hop-cbs-iperf-line-limit100-2min-cpuperf', prePathToResults + 'Figure-15d-16d_EX_SO4', journalPlotFolder, 3, 'enp5s0', [1004],10,300, ["minor grid style={line width=.001pt, draw=gray!10}","major grid style={line width=.5pt,draw=gray!50}","minor x tick num=0","minor y tick num=0","ytick={0,0.2,0.4,0.6,0.8,1.0}"], 'EX-SO4')

### Figure-17_ETF_Params
scenarios = ['Figure-17_ETF_Params']
totalPkt = 300000
experimentTypes = ['offload', 'nooffload']
port = 6601
plotDelayGenericLine(scenarios, experimentTypes, ['etf_','_strict'], prePathToResults, journalPlotFolder + 'etf_delta/', 0.4, 'etfDelata_delay', 'Delay', totalPkt, port, '')
plotDelayGenericLine(scenarios, experimentTypes, ['etf_','_strict'], prePathToResults, journalPlotFolder + 'etf_delta/', 100, 'etfDelata_jitter', 'Jitter', totalPkt, port, '')
plotDelayGenericLine(scenarios, experimentTypes, ['etf_','_strict'], prePathToResults, journalPlotFolder + 'etf_delta/', 100, 'etfDelata_pktdrop', 'PktDrop', totalPkt, port, '')

### Figure-18_TAPRIO_Params
scenarios = ['Figure-18_TAPRIO_Params']
totalPkt = 100000
port = 1007
experimentTypes = ['offload*175delta', 'offload*275delta', 'nooffload*175delta', 'nooffload*275delta']
plotDelayGenericLine(scenarios, experimentTypes, ['offload_','txtime'], prePathToResults, journalPlotFolder + 'taprio_txtime/', 0.6, 'taprioTxTime_delay', 'Delay', totalPkt, port, '')
plotDelayGenericLine(scenarios, experimentTypes, ['offload_','txtime'], prePathToResults, journalPlotFolder + 'taprio_txtime/', 100, 'taprioTxTime_jitter', 'Jitter', totalPkt, port, '')
plotDelayGenericLine(scenarios, experimentTypes, ['offload_','txtime'], prePathToResults, journalPlotFolder + 'taprio_txtime/', 100, 'taprioTxTime_pktdrop', 'PktDrop', totalPkt, port, '')

### Figure-22_EX_CS1 and Figure-22_EX_CS2
scenarios = ['Figure-22_EX_CS1', 'Figure-22_EX_CS2']
totalPkt = 100000
port = 1004
experimentTypes = ['no-hop-cbs', 'with-hop-cbs']
modif = '-cs'
plotDelayGenericLine(scenarios, experimentTypes, ['streams_','-hop'], prePathToResults, journalPlotFolder + 'singleCBS-test/', 2.5, 'EX-CS_delay', 'Delay', totalPkt, port, modif)
plotDelayGenericLine(scenarios, experimentTypes, ['streams_','-hop'], prePathToResults, journalPlotFolder + 'singleCBS-test/', 5000, 'EX-CS_jitter', 'Jitter', totalPkt, port, modif)

### Figure-23-24_EX_CM1 and Figure-23-24_EX_CM2
scenarios = ['Figure-23-24_EX_CM1', 'Figure-23-24_EX_CM2']
totalPkt = 100000
ports = [1004,1003]
experimentTypes = ['no-hop-cbs', 'with-hop-cbs']
modif = '-cm'
for port in ports:
    plotDelayGenericLine(scenarios, experimentTypes, ['streams_','-hop'], prePathToResults, journalPlotFolder + 'multiCBS-test/', 2.5, 'EX-CM_delay'+str(port), 'Delay', totalPkt, port, modif)
    plotDelayGenericLine(scenarios, experimentTypes, ['streams_','-hop'], prePathToResults, journalPlotFolder + 'multiCBS-test/', 5000, 'EX-CM_jitter'+str(port), 'Jitter', totalPkt, port, modif)

### Figure-25ab_EX_TS-T,EX_TS-W
expNames = ['1to7_hops-taprio_nooffload_180txtime_175delta_prio3_singlestrict_shift_200perhop_400windows', '1to7_hops-taprio_nooffload_180txtime_175delta_prio3_singlestrict_shift_20perhop_40windows', '1to7_hops-taprio_offload_180txtime_175delta_prio3_singlestrict_shift_200perhop_400windows', '1to7_hops-taprio_offload_180txtime_175delta_prio3_singlestrict_shift_20perhop_40windows']
plotTaprioShift(expNames, prePathToResults + 'Figure-25ab_EX_TS-T,EX_TS-W/', journalPlotFolder + 'taprioShift/', 8, {'Flow' : [1001]}, 3.4, 'delayEX-TCWC', 'Delay')
plotTaprioShift(expNames, prePathToResults + 'Figure-25ab_EX_TS-T,EX_TS-W/', journalPlotFolder + 'taprioShift/', 8, {'Flow' : [1001]}, 1000, 'jitterEX-TCWC', 'Jitter')

### Figure-27a-28a_EX_UCC and Figure-27b-28b_EX_UCC-F
experimentsUCC = ['journal-use-case-version1_30s']
experimentsUCCF = ['journal-use-case-version1_justFlow1SRA_30s', 'journal-use-case-version1_justFlow2SRA_30s', 'journal-use-case-version1_justFlow3SRB_30s']
sourceFolderUCC = prePathToResults + 'Figure-27a-28a_EX_UCC/'
sourceFolderUCCF = prePathToResults + 'Figure-27b-28b_EX_UCC-F/'
expTypeNames = ['EX-UCC', 'EX-UCC-F']
endNodeNum = 7
portFlows = {'$F1_{C&C}$' : [2101],
             '$F1_{ADAS}$' : [2102],
             '$F2_{LIDAR}$' : [2201], 
             '$F2_{RADAR}$' : [2202],
             '$F3_{RADAR}$' : [2301], 
             '$F3_{US}$' : [2302], 
             '$F3_{GPS}$' : [2303]}

plotDelayUseCase(experimentsUCC, sourceFolderUCC, journalPlotFolder + 'useCase/', 7, portFlows, 1.2, 'delayEX-UCC', 'Delay')
plotDelayUseCase(experimentsUCCF, sourceFolderUCCF, journalPlotFolder + 'useCase/', 7, portFlows, 1.2, 'delayEX-UCC-F', 'Delay')
plotDelayUseCase(experimentsUCC, sourceFolderUCC, journalPlotFolder + 'useCase/', 7, portFlows, 1000, 'jitterEX-UCC', 'Jitter')
plotDelayUseCase(experimentsUCCF, sourceFolderUCCF, journalPlotFolder + 'useCase/', 7, portFlows, 1000, 'jitterEX-UCC-F', 'Jitter')
