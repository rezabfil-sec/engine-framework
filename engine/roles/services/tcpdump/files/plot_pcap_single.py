#!/usr/bin/env python3

# iperf pcap plots

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import statistics
import sys
import time

sys.path.append("../../../process/files")
import processing_descriptor
import plot_plots as pp

font = {'weight' : 'normal',
        'size'   : 20}
matplotlib.rc('font', **font)
matplotlib.rc('lines', linewidth=2.0)
matplotlib.rc('lines', markersize=8)

def read_csv(pd, dst_port):
    df = pp.read_csv(pd.node_path() + 'csv-' + pd.service_name(dst_port) + '-single_' + str(dst_port) + '_' + pd.iface + '.csv') #pd.iface + 'PcapFlowIperf' + str(dst_port) + '.csv')
    df['timestamp_ns'] = df.apply(lambda row: row['timestamp_seconds'] * 1e9 + row['timestamp_nanoseconds'], axis=1)
    df = df.loc[df['timestamp_ns'] >= df['timestamp_ns'].min() + pd.warmup]
    return df

def df_tp(processing_descriptor, targetBitrate=0, calculationTimescale=10000000):
    toPlot = {}
    for dst_port in processing_descriptor.dst_ports:
        df = read_csv(processing_descriptor, dst_port)
        initialTime = df['timestamp_ns'].iloc[0]
        # df['timestamp_ns'] = df['timestamp_ns'] - initialTime
        calculationWindow = [initialTime, initialTime + calculationTimescale]
        ts = []
        bitrates = []
        while calculationWindow[0] <= df['timestamp_ns'].iloc[-1]:
            tempDf = df.loc[(df['timestamp_ns'] >= calculationWindow[0]) & (df['timestamp_ns'] <= calculationWindow[1])]
            mbps = (((tempDf['packet_size_bytes'].sum()*8)/1e6)/(calculationTimescale/1e9)) - targetBitrate
            ts.append(calculationWindow[1])
            bitrates.append(mbps)
            # if mbps > 1.05 * statistics.mean(bitrates) or mbps < 0.95 * statistics.mean(bitrates):
            #     print(calculationWindow[1], mbps)
            calculationWindow = [x + calculationTimescale for x in calculationWindow]
        toPlot[dst_port] = {}
        toPlot[dst_port]['TS'] = ts
        toPlot[dst_port]['Val'] = bitrates
    return toPlot

def plotManualTPcalcMultiFlowOptDiffToTargetBitrate(processing_descriptor, targetBitrate=0, calculationTimescale=10000000):
    '''
        Depending on targetBitrate==0 or targetBitrate>0 either plot throughput or difference of throughput and target bitrate
    '''
    topicLong = "Throughput"
    topicShort = "throughput"
    fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

    toPlot = df_tp(processing_descriptor, targetBitrate, calculationTimescale)
    minTS = min(float('inf'), min([min(x['TS']) for x in toPlot.values()]))
    maxTS = max(0, max([max(x['TS']) for x in toPlot.values()]))
    maxTPorDev = max(0, max([abs(max(x['Val'], key=abs)) for x in toPlot.values()])) ## max TP for TB = 0, max Dev fo TB > 0
    for dst_port in processing_descriptor.dst_ports:
        ax.plot([(x - minTS) / 1e9 for x in toPlot[dst_port]['TS']], toPlot[dst_port]['Val'], '.-', color=pp.stream_to_color[dst_port%100], label='Stream ' + str(dst_port%100))

    # major_ticks = np.arange(0, 1001, 200)
    # minor_ticks = np.arange(0, 1001, 100)
    # ax.set_yticks(major_ticks)
    # ax.set_yticks(minor_ticks, minor=True)
    # ax.set_ylim(0,1000)
    if targetBitrate == 0:
        ax.set_ylim(0,maxTPorDev+10)
    else:
        ax.set_ylim(-15,15)
    ax.set_xlim(0,(maxTS-minTS)/1e9) #0,90)
    ax.grid(which='both')

    plt.legend()
    plt.xlabel('Experiment Time [s]')
    plt.ylabel('Flow Throughput ' + ('' if targetBitrate == 0 else 'Difference ') + '[mbps]')
    
    plotName = 'throughput' + ('-diff' if targetBitrate > 0 else '') + '_' + processing_descriptor.node + processing_descriptor.iface+processing_descriptor.experiment+'_TimeGran'+str(int(calculationTimescale/1e3))+'us'+'_ports'+str(processing_descriptor.dst_ports)+'.png'
    pp.follow_up(plotName, processing_descriptor, topicShort, fl, startTime, fig)
    
    return minTS/1e9

def df_cdf_ifs(processing_descriptor):
    interFramSpacs = {}
    # allVals = []
    for dst_port in processing_descriptor.dst_ports:
        # previously operated on combined csv, yielding ifs for source pcap:
        # df = pp.read_csv(processing_descriptor.node_path() + 'csv-' + pd.service_name(dst_port) + '-combined_' + str(dst_port) + '_' + processing_descriptor.iface + '.csv') # processing_descriptor.iface + 'DelayAndJitterFlowIperf' + str(dst_port) + '.csv')
        # now uses pcap csv, for plotting ifs for both, source and destination:
        df = read_csv(processing_descriptor, dst_port)
        timestamps = df['timestamp_ns'].dropna().tolist()
        ifs = [(x - y) / 1e3 for x,y in zip(timestamps[1:], timestamps[:-1])]
        interFramSpacs[dst_port] = {}
        interFramSpacs[dst_port]['Val'] = ifs
        # allVals.extend(ifs)
    return interFramSpacs

def plotManualIfsCDFcalcMultiFlow(processing_descriptor):
    topicLong = "Inter-Frame Spacing"
    topicShort = "ifsCDF"
    fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

    interFramSpacs = df_cdf_ifs(processing_descriptor)
    for dst_port in processing_descriptor.dst_ports:
        sorted_data = np.sort(interFramSpacs[dst_port]['Val'])
        linspaced = np.linspace(0, 1, len(interFramSpacs[dst_port]['Val']), endpoint=True)
        lbl = 'Measured'
        if len(processing_descriptor.dst_ports) > 1:
            lbl = 'Flow ' + str(dst_port-1000)
        ax.plot(sorted_data, linspaced, '.-', label=lbl, zorder=dst_port-980, color=pp.stream_to_color[dst_port%100])

    if len(processing_descriptor.dst_ports) <= 1: ax.vlines(100, ymin=0, ymax=1, alpha=0.9, zorder=1000, color='tab:red', label='Target')

    ax.set_xlim(0, max([max(x['Val']) for x in interFramSpacs.values()])) # max(allVals))
    # ax.set_ylim(0,1)
    ax.grid(which='both')
    ax.ticklabel_format(useOffset=False, style='plain')

    plt.legend()
    plt.xlabel('Inter-Frame Spacing [\u03BCs]')
    plt.ylabel('CDF')

    plotName = 'inter-frame-spacing-CDF'+processing_descriptor.png_string()
    pp.follow_up(plotName, processing_descriptor, topicShort, fl, startTime, fig)

def max_min_ts(df_dict):
    max_ts = max([float('-inf')] + [x['ts_max'] for x in df_dict.values()])
    min_ts = min([float('inf')] + [x['ts_min'] for x in df_dict.values()])
    return max_ts, min_ts

def df_ifs(processing_descriptor):
    ifs = {}
    for dst_port in processing_descriptor.dst_ports:
        df = read_csv(processing_descriptor, dst_port)
        ifs[dst_port] = {}
        timestamp_ns = df['timestamp_ns'].dropna()#.tolist()
        ifs_us = [(x - y) / 1e3 for x,y in zip(timestamp_ns[1:], timestamp_ns[:-1])]
        ifs[dst_port]['ts'] = timestamp_ns[1:] # use later ts
        ifs[dst_port]['val'] = ifs_us
        ifs[dst_port]['ts_min'] = timestamp_ns.min()
        ifs[dst_port]['ts_max'] = timestamp_ns.max()
        ifs[dst_port]['val_min'] = min(ifs_us)#.min()
        ifs[dst_port]['val_max'] = max(ifs_us)#.max()
    return ifs

def plot_ifs(processing_descriptor):
    topicLong = "IFS"
    topicShort = "ifs"
    fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

    ifs = df_ifs(processing_descriptor)
    maxTS, minTS = max_min_ts(ifs)
    minHeight = min([float('inf')] + [x['val_min'] for x in ifs.values()])
    maxHeight = max([float('-inf')] + [x['val_max'] for x in ifs.values()])
    for dst_port in processing_descriptor.dst_ports:
        ax.plot((ifs[dst_port]['ts'] - minTS).div(1e9), ifs[dst_port]['val'], '.', label='Flow ' + str(dst_port-1000), zorder=10-(dst_port-1000), color=pp.stream_to_color[dst_port%100])

    # if len(processing_descriptor.dst_ports) <= 1: ax.hlines(100, xmin=0, xmax=maxTS-minTS, alpha=0.9, zorder=1000, color='tab:red', label='Target')

    ax.set_xlim(0,(maxTS-minTS)/1e9)
    ax.set_ylim(minHeight,maxHeight)
    # ax.set_ylim(minHeight*1e6,maxHeight*1e6)
    ax.grid(which='both')
    ax.ticklabel_format(useOffset=False, style='plain')

    plt.legend()
    plt.xlabel('Experiment Time [s]')
    plt.ylabel('IFS [\u03BCs]')

    plotName = 'ifs'+processing_descriptor.png_string()
    pp.follow_up(plotName, processing_descriptor, topicShort, fl, startTime, fig)

def plot_all(pd):
    plotManualTPcalcMultiFlowOptDiffToTargetBitrate(pd)
    plotManualIfsCDFcalcMultiFlow(pd)
    plot_ifs(pd)

def main():
    pd = processing_descriptor.create_processing_descriptor_cli('plot_pcap', 'Plots based on single pcaps')

    #plotManualTPcalcMultiFlowOptDiffToTargetBitrate(pd)
    #plotManualIfsCDFcalcMultiFlow(pd)
    #plot_ifs(pd)
    plot_all(pd)

if __name__ == "__main__":
    main()
