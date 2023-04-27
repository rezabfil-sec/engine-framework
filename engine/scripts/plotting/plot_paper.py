#!/usr/bin/env python3

# This script is based on the plot_journal.py script provided by the original EnGINE authors

from itertools import starmap
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
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

figSize = (10,6)

def plotComp(expPortName, resultsSources, plotPath, endNodeNum, yLim, plotName, type, seps):
    print('Plotting', type ,'for', list(expPortName), end='...\n')
    startTime = time.time()
    fig, ax = plt.subplots(1, figsize=figSize)
    enum = 0
    ticks = []
    labels = []
    means = []
    mins = []
    maxs = []
    sepsList = [-1]
    sepsList.extend(list(seps.keys()))

    allFiles = []
    for resSrc in resultsSources:
        prePath = resSrc + '/**'
        allFiles.extend(glob.glob(prePath, recursive=True))

    availableFiles = []
    for name in expPortName:
        dirs = [x for x in allFiles if list(name)[0] in x]
        for dir in dirs:
            availableFiles.extend(glob.glob(dir+'/**/*.csv', recursive=True))

    for idx, expDict in enumerate(expPortName):
        experimentSubname = list(expDict)[0]
        if enum in seps:
            prev = sepsList[sepsList.index(enum)-1]
            if enum == sepsList[-1]:
                prev += 1
            # print('now:', enum, prev, sepsList.index(enum), (enum+prev)*0.5)
            yLimMax = 1.0
            # if type == 'Jitter':
            #     yLimMax = 1.1
            ax.text((enum+prev)*0.5, yLimMax*yLim[1], seps[enum], ha='center', va='center', fontsize=50, bbox=dict(facecolor='white', alpha=1.0, linewidth=1, edgecolor='black'), zorder=1000)
            if enum != sepsList[-1]:
                ax.plot([enum, enum], yLim, ls='dotted', color='blue')
                enum += 1
                
        possibleFiles = [x for x in availableFiles if '/'+experimentSubname in x]
        possibleFiles = list(dict.fromkeys(possibleFiles))
        iperfPorts = expDict[experimentSubname]
        for flow in iperfPorts:
            flowPorts = iperfPorts[flow]
            delays = []
            for port in flowPorts:
                for file in possibleFiles:
                    if str(port) in file and ('DelayAndJitter' in file or 'combined' in file):
                        print(port, file)
                        df = pd.read_csv(file)
                        if 'sim' in experimentSubname:
                            colName = type.lower() + '_ns'
                        else:
                            colName = type
                        delays.extend(df[colName].dropna().tolist())
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

    plt.xticks(ticks, labels, rotation=0)
    plt.xlabel('Experiment Type')
    ax.set_xlim(-1,enum)
    if type == 'Delay':
        ax.set_ylim(yLim[0], yLim[1])    
        plt.ylabel('Delay [ms]')
        plt.yscale('log')
        ax.minorticks_on()
        # ax.yaxis.set_major_formatter(mticker.ScalarFormatter())
        # ax.yaxis.get_major_formatter().set_scientific(False)
        plt.legend(loc='lower left', bbox_to_anchor=(0.003,0.01), fontsize=10)
    elif type == 'Jitter':
        plt.ylabel('Jitter [us]')
        plt.yscale('symlog')
        # ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%d"))
        plt.legend(loc='lower right', bbox_to_anchor=(0.997,0.01), fontsize=10)

    ax.grid(which='both')

    preOutPath = plotPath + '/plots/'
    if not os.path.exists(preOutPath):
        os.makedirs(preOutPath)

    outPath = preOutPath + plotName + type + '.png'
    fig.savefig(outPath, dpi=100, bbox_inches='tight', format='png')
    if type == 'Delay':
        tiksav.saveTikz(plotName + type, preOutPath, ["minor grid style={line width=.0001pt, draw=gray!10}","major grid style={line width=.8pt,draw=gray!50}", "minor x tick num=0", "legend style={font=\\tiny}", "scaled y ticks=false", "yticklabels={0.1,1.0}", "ytick={0.1,1.0}", "yminorticks=true", "minor y tick num=9", "minor ytick={0.06, 0.07, 0.08, 0.09, 0.3, 0.4, 0.6, 0.7, 0.8, 0.9, 3.0}", "extra y ticks={0.2,0.5,2.0}", "extra y tick labels={0.2,0.5,2.0}", "extra tick style={major grid style={line width=.0001pt, draw=gray!10},}", "clip marker paths=true", "clip=false"], 'small', True, False) # "yticklabels={,,0.1,,,,,,,,,1.0,,}", "ytick={0.08,0.09,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,2.0,3.0}"
    elif type == 'Jitter':
        tiksav.saveTikz(plotName + type, preOutPath, ["minor grid style={line width=.001pt, draw=gray!10}","major grid style={line width=.8pt,draw=gray!50}", "minor x tick num=0","minor y tick num=0","legend style={font=\\tiny}", "scaled y ticks=false", "yticklabels={-1000, -100, -10, -1, , 1, 10, 100, 1000}", "ytick={-1000, -100, -10, -1, 0, 1, 10, 100, 1000}", "clip marker paths=true", "clip=false"], 'small', True, True)
    plt.close('all')
    print('It took', time.time() - startTime, 's')

#############################
# PUT YOUR PARAMETERS HERE! #
#############################
# Common function parameters:
simulationResultsPath =  # Put absolute path to the folder with simulation results
hardwareResultsPath =  # Path absolute to folder with results provided by original EnGINE authors (downloaded from: https://nextcloud.in.tum.de/index.php/s/sWxadG8JeJss2Sy)
plotFolder =  # Path absolute to where you want your plots

resultsSources = [simulationResultsPath, hardwareResultsPath]

# Individual experiment names
expCBS = '4-queue_2-cbs_2-be_4-streams_7-hop_with-hop-cbs-iperf-line-limit100-90s'
expSimCBS = 'sim_4-queue_2-cbs_2-be_4-streams_7-hop_with-hop-cbs-iperf-line-limit100-15s'
expTAP = '1to7_hops-taprio_nooffload_180txtime_175delta_prio3_singlestrict_shift_200perhop_400windows'
expSimTAP = 'sim_1to7_hops-taprio_nooffload_180txtime_175delta_prio3_singlestrict_shift_200perhop_400windows'
expTAP_W = '1to7_hops-taprio_nooffload_180txtime_175delta_prio3_singlestrict_shift_20perhop_40windows'
expSimTAP_W = 'sim_1to7_hops-taprio_nooffload_180txtime_175delta_prio3_singlestrict_shift_20perhop_40windows'

expPortName = [
    {
        expCBS : {
            '$Hw$' : [1004]
        }
    },
    {
        expSimCBS : {
            '$Sim$' : [1004]
        }
    },
    {
        expCBS : {
            '$Hw$' : [1003]
        }
    },
    {
        expSimCBS : {
            '$Sim$' : [1003]
        }
    },
    {
        expTAP : {
            '$Hw$' : [1001]
        }
    },
    {
        expSimTAP : {
            '$Sim$' : [1001]
        }
    },
    {
        expTAP_W : {
            '$Hw$' : [1001]
        }
    },
    {
        expSimTAP_W : {
            '$Sim$' : [1001]
        }
    }
]

seps = {
    2 : '$CBS_{Hi}$',
    5 : '$CBS_{Lo}$',
    8 : '$TAS_T$',
    10 : '$TAS_W$'
}

plotComp(expPortName, resultsSources, plotFolder + 'final/', 8, [0.06, 3.7], 'comparison-all', 'Delay', seps)
plotComp(expPortName, resultsSources, plotFolder + 'final/', 8, [-6000, 6000], 'comparison-all', 'Jitter', seps)

