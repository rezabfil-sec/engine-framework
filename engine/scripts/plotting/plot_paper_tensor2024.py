#!/usr/bin/env python3

# This script is based on the plot_journal.py script provided by the original EnGINE authors

from itertools import starmap
import itertools
import math
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as patches
import matplotlib.transforms as transforms
import pandas as pd
import glob
import numpy as np
import os


import statistics

import time

DATA = 6
INTEREST = 5

resol = {
    5 : 'Interest',
    6 : "Data"
}

font = {'weight' : 'normal',
                    'size'   : 12}
matplotlib.rc('font', **font)
matplotlib.rc('lines', linewidth=2.0)
matplotlib.rc('lines', markersize=8)

figSize = (7,2.5)

prioDict = {
    3 : 'Priority 3 (SR-A)',
    2 : 'Priority 2 (SR-B)'
}

def y_tick_formatter(value, pos):
    if value == 0:
        return ''
    else:
        val = value
        if value < 0:
            val = -value
        exponent = int(math.log10(int(val)))
        if value < 0:
            return fr'$-10^{{{int(exponent)}}}$'
        else:
            return fr'$10^{{{int(exponent)}}}$'

def plotComp(expNamePrefs, resultsSources, plotPath, prios, yLim, plotName, type, ndn_filter, pltTitle):
    print('Plotting', type ,'for', expNamePrefs, 'and prio', prios, 'dir', ndn_filter, end='...\n')
    startTime = time.time()
    fig, ax = plt.subplots(1, figsize=figSize)
    ticks = []
    labels = []
    means = []
    mins = []
    maxs = []

    valDict = {}
    for prio in prios:
        valDict[prio] = {}

    for expNamePref in expNamePrefs:
        allFiles = []
        for resSrc in resultsSources:
            prePath = resSrc + '/**'
            allFiles.extend(glob.glob(prePath, recursive=True))

        availableFiles = []
        dirs = [x for x in allFiles if expNamePref in x]

        for dir in dirs:
            if 'combined' in dir:
                availableFiles.append(dir)

        
        for file in availableFiles:
            for prio in prios:
                if 'prio'+str(prio) in file or str(1000+prio) in file:
                    # print(file)
                    # numHops = int(file.split('hop')[0].split('-')[-1])
                    df = pd.read_csv(file)
                    # print(list(df))
                    if 'ndn' in expNamePref:
                        df = df.loc[df['type'].isin([ndn_filter])]
                    # print(df)
                    # exit()
                    div = 1e6
                    if type == 'jitter_ns':
                        df['jitter_ns'] = df['delay_ns'].diff()
                        # df.at[0, 'jitter_ns'] = 0
                        # print(df)
                        div = 1e3
                    vals = [x / div for x in sorted(df[type].dropna().tolist())]
                    valDict[prio][expNamePref] = vals
                # print(vals)
        # print(list(valDict))
    idxAdd = 0
    trans = transforms.blended_transform_factory(ax.transData, ax.transAxes)
    # print('Experiment name\t', 'Minimum\t;', 'Maximum\t;', 'Mean\t;', 'Median\t; Number of values')
    print(f"{'Exp Name':<30} {'Min':<10} {'Max':<10} {'Mean':<10} {'Median':<10} {'Length':<10}")
    for prio in prios:
        for idx, expNamePref in enumerate(expNamePrefs):
            index = idx+idxAdd
            vals = valDict[prio][expNamePref]
            min_val = round(min(vals), 2)
            max_val = round(max(vals), 2)
            mean_val = round(statistics.mean(vals), 2)
            median_val = round(statistics.median(vals), 2)
            length_val = round(len(vals), 2)
            # print(expNamePref,'\t',round(min(vals),2), '\t;', round(max(vals),2), '\t;', round(statistics.mean(vals),2), '\t;', round(statistics.median(vals),2), '\t;', round(len(vals),2))
            print(f"{expNamePref:<30} {min_val:<10} {max_val:<10} {mean_val:<10} {median_val:<10} {length_val:<10}")
            ax.boxplot(vals, positions=[index], notch=False, patch_artist=True,
                boxprops=dict(facecolor='white', color='black'),
                capprops=dict(color='black'),
                whiskerprops=dict(color='black'),
                flierprops=dict(color='black', markeredgecolor='black', markersize=3, linewidth=0.5),
                widths=0.75, zorder=100)

            means.append(statistics.mean(vals))
            mins.append(min(vals))
            maxs.append(max(vals))
            ticks.append(index)
            if 'iperf' in expNamePref:
                labels.append('Iperf3')
            if 'ndn' in expNamePref:
                if 'normal' in expNamePref:
                    labels.append('NDN-RR')
                if 'soft' in expNamePref:
                    labels.append('NDN-LL')
            if (index+1) % len(expNamePrefs) == len(expNamePrefs)/2 and index != 0:
                ax.plot([index+0.5,index+0.5], [-1e5,1e5], linestyle='dotted', color='black', zorder=600)
                plt.text(index-1, yLim[1], 'No Shaping', horizontalalignment='center', verticalalignment='center', fontsize=12, bbox=dict(facecolor='white', linewidth=0.75, edgecolor='black', boxstyle="round,pad=0.05"), zorder=600)
                ax.text(index+0.5, 1.05, prioDict[prio], ha='center', va='bottom', zorder=1500, transform=trans)
            if (index+1) % len(expNamePrefs) == 0 and index != 0:
                plt.text(index-1, yLim[1], 'CBS', horizontalalignment='center', verticalalignment='center', fontsize=12, bbox=dict(facecolor='white', linewidth=0.75, edgecolor='black', boxstyle="round,pad=0.05"), zorder=600)
                if index+1 != len(expNamePrefs)*len(prios):
                    ax.plot([index+0.5,index+0.5], [-1e5,1e5], linestyle='solid', color='black', zorder=600)
        idxAdd += len(expNamePrefs)

    ax.plot(ticks, means, '^', color='tab:green', markersize=4.5, label='Mean', zorder=105)
    ax.plot(ticks, maxs, 'D', color='tab:blue', markersize=4.5, label='Max', zorder=105)
    ax.plot(ticks, mins, 'D', color='tab:purple', markersize=4.5, label='Min', zorder=105)

    if type == 'delay_ns':
        ax.plot([min(ticks)-1, len(expNamePrefs)-0.5], [2,2], '--', color='tab:red', zorder=510)
        rect = patches.Rectangle((min(ticks)-0.5, 2), len(expNamePrefs), yLim[1]-2, linewidth=0, edgecolor='tab:red', facecolor='tab:red', hatch='////', fill=False, alpha=0.08, zorder=500)
        ax.add_patch(rect)

        ax.plot([len(expNamePrefs)-0.5, max(ticks)+1], [10,10], '--', color='tab:red', zorder=510)
        rect = patches.Rectangle((len(expNamePrefs)-0.5, 10), len(expNamePrefs), yLim[1]-10, linewidth=0, edgecolor='tab:red', facecolor='tab:red', hatch='////', fill=False, alpha=0.08, zorder=500)
        ax.add_patch(rect)
    if type == 'jitter_ns':
        ax.plot([min(ticks)-1, len(expNamePrefs)-0.5], [125,125], '--', color='tab:red', zorder=510)
        ax.plot([min(ticks)-1, len(expNamePrefs)-0.5], [-125,-125], '--', color='tab:red', zorder=510)
        rect = patches.Rectangle((min(ticks)-0.5, 125), len(expNamePrefs), yLim[1]-125, linewidth=0, edgecolor='tab:red', facecolor='tab:red', hatch='////', fill=False, alpha=0.08, zorder=500)
        ax.add_patch(rect)
        rect = patches.Rectangle((len(expNamePrefs)-0.5, 1000), len(expNamePrefs), yLim[1]-1000, linewidth=0, edgecolor='tab:red', facecolor='tab:red', hatch='////', fill=False, alpha=0.08, zorder=500)
        ax.add_patch(rect)

        ax.plot([len(expNamePrefs)-0.5, max(ticks)+1], [1000,1000], '--', color='tab:red', zorder=510)
        ax.plot([len(expNamePrefs)-0.5, max(ticks)+1], [-1000,-1000], '--', color='tab:red', zorder=510)
        rect = patches.Rectangle((min(ticks)-0.5, -125), len(expNamePrefs), yLim[0]+125, linewidth=0, edgecolor='tab:red', facecolor='tab:red', hatch='////', fill=False, alpha=0.08, zorder=500)
        ax.add_patch(rect)
        rect = patches.Rectangle((len(expNamePrefs)-0.5, -1000), len(expNamePrefs), yLim[0]+1000, linewidth=0, edgecolor='tab:red', facecolor='tab:red', hatch='////', fill=False, alpha=0.08, zorder=500)
        ax.add_patch(rect)


    
    plt.xticks(ticks, labels, rotation=30, horizontalalignment='right')
    plt.xlabel('Scenario')
    ax.set_xlim(-0.5,idxAdd-0.5)
    if type == 'delay_ns':
        ax.set_ylim(yLim[0], yLim[1])    
        plt.ylabel('Delay [ms]')
        plt.yscale('log')
        ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%d"))
        plt.legend(loc='upper left', bbox_to_anchor=(-0.11,-0.27), fontsize=8, ncol=3).set_zorder(700)
    elif type == 'jitter_ns':
        plt.ylabel('Jitter [us]')
        ax.set_ylim(yLim[0], yLim[1]) 
        plt.yscale('symlog')
        plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(y_tick_formatter))
        plt.legend(loc='upper left', bbox_to_anchor=(-0.11,-0.27), fontsize=8, ncol=3).set_zorder(700)

    ax.grid(which='both')

    preOutPath = plotPath
    if not os.path.exists(preOutPath):
        os.makedirs(preOutPath)

    outPath = preOutPath + plotName + type + '.png'
    fig.savefig(outPath, dpi=200, bbox_inches='tight', format='png')
    outPath = preOutPath + plotName + type + '.pdf'
    fig.savefig(outPath, dpi=100, bbox_inches='tight', format='pdf')
    plt.close('all')
    print('It took', time.time() - startTime, 's')


#############################
# PUT YOUR PARAMETERS HERE! #
#############################
# Common function parameters:
preResPath = # Path to where you put your results folders
plotFolder =  # Path to where you want your plots

resultsFolder = preResPath + # Folder name containing the four experiment results defined in line 220; generated with scenario TENSOR2024_ndn-verification

prios = [3, 2]
directions = [DATA]
types = ['delay_ns', 'jitter_ns']
test_prefs = ['ndn-test-mqprio-normal-7hop', 'ndn-test-mqprio-soft-7hop', 'ndn-test-cbs-normal-7hop', 'ndn-test-cbs-soft-7hop']

for (type, direction) in itertools.product(types, directions):
    dir = 'Data'
    if direction == INTEREST:
        dir = 'Interest'
    if type == 'delay_ns':
        plotComp(test_prefs, [resultsFolder], plotFolder + 'initial/', prios, [0.3, 60], 'Comparison' + '_prio' + str(prios) + '_direction' + dir, type, direction, 'Comparison')
    if type == 'jitter_ns':
        plotComp(test_prefs, [resultsFolder], plotFolder + 'initial/', prios, [-4e4, 4e4], 'Comparison' + '_prio' + str(prios) + '_direction' + dir, type, direction, 'Comparison')

