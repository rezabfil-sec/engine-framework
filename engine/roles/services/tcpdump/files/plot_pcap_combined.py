#!/usr/bin/env python3

# iperf pcap plots

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import statistics
import sys
import time
import os

sys.path.append("../../../process/files")
import processing_descriptor
import plot_plots as pp

font = {'weight' : 'normal',
        'size'   : 20}
matplotlib.rc('font', **font)
matplotlib.rc('lines', linewidth=2.0)
matplotlib.rc('lines', markersize=8)

def check_csvs(pd):
    '''deletes port from dst_ports if the corresponding csv does not exist (means tcpdump collection was not enabled for that port)'''
    for dst_port in pd.dst_ports[:]:
        fileName = pd.node_path() + 'csv-' + pd.service_name(dst_port) + '-combined_' + str(dst_port) + '_' + pd.iface + '.csv'
        if not os.path.isfile(fileName):
            pd.dst_ports.remove(dst_port)
            with open(pd.log_file(), "a") as myFile:
                print('csv-' + pd.service_name(dst_port) + '-combined_' + str(dst_port) + '_' + pd.iface + '.csv', ' does not exist.', end='...\n', file=myFile)

def read_csv(pd, dst_port):
    ''' loads csv corresponding to processing_descriptor '''
    df = pp.read_csv(pd.node_path() + 'csv-' + pd.service_name(dst_port) + '-combined_' + str(dst_port) + '_' + pd.iface + '.csv') #pd.iface + 'DelayAndJitterFlowIperf' + str(dst_port) + '.csv')
    df = df.loc[df['timestamp_ns'] >= df['timestamp_ns'].min() + pd.warmup]
    return df

def max_min_ts(df_dict, dst_ports):
    ''' gets max and min timestamp '''
    max_ts = max([float('-inf')] + [df_dict[x]['ts_max'] for x in dst_ports])
    min_ts = min([float('inf')] + [df_dict[x]['ts_min'] for x in dst_ports])
    return max_ts, min_ts

def df_delay(pd):
    ''' load csv for plotting delay '''
    delay = {}
    for dst_port in pd.dst_ports:
        df = read_csv(pd, dst_port)
        delay[dst_port] = {}
        timestamp_ns = df['timestamp_ns']
        delay_us = df['delay_ns'].div(1e3)
        delay[dst_port]['ts'] = timestamp_ns
        delay[dst_port]['val'] = delay_us
        delay[dst_port]['ts_min'] = timestamp_ns.min()
        delay[dst_port]['ts_max'] = timestamp_ns.max()
        delay[dst_port]['val_max'] = delay_us.max()
    return delay

def plotManualDelaycalcMultiFlow(processing_descriptor):
    ''' plot delay of a flow, both single ports individually and all ports combined in a plot'''
    check_csvs(processing_descriptor)
    if len(processing_descriptor.dst_ports) == 0:
        return
    topicLong = "Delay"
    topicShort = "delay"
    if pp.plots_exist(topicShort+processing_descriptor.png_string(), processing_descriptor, topicShort):
        return
    fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

    delay = df_delay(processing_descriptor)
    
    ports = [[port] for port in processing_descriptor.dst_ports]
    if len(processing_descriptor.dst_ports) > 1:
        ports.append(processing_descriptor.dst_ports)

    for dst_ports in ports:
        processing_descriptor.dst_ports = dst_ports
        maxTS, minTS = max_min_ts(delay, dst_ports)
        fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

        maxHeight = max([float('-inf')] + [x['val_max'] for x in delay.values()])
        for dst_port in processing_descriptor.dst_ports:
            ax.plot((delay[dst_port]['ts'] - minTS).div(1e9), delay[dst_port]['val'], '.', label='Flow ' + str(dst_port-1000), zorder=10-(dst_port-1000), color=pp.stream_to_color[dst_port%100])

        ax.set_xlim(0,(maxTS - minTS) / 1e9)
        ax.grid(which='both')
        ax.set_ylim(0,maxHeight)
        # ax.set_ylim(0,maxHeight*1e3)
        ax.ticklabel_format(useOffset=False, style='plain')

        plt.legend()
        plt.xlabel('Experiment Time [s]')
        plt.ylabel('End-To-End Delay [us]')

        plotName = topicShort+processing_descriptor.png_string()
        pp.follow_up(plotName, processing_descriptor, topicShort, fl, startTime, fig)

def df_jitter(pd):
    ''' load csv for plotting jitter '''
    jitter = {}
    for dst_port in pd.dst_ports:
        df = read_csv(pd, dst_port)
        jitter[dst_port] = {}
        timestamp_ns = df['timestamp_ns']
        jitter_us = df['jitter_ns'].div(1e3)
        jitter[dst_port]['ts'] = timestamp_ns
        jitter[dst_port]['val'] = jitter_us
        jitter[dst_port]['ts_min'] = timestamp_ns.min()
        jitter[dst_port]['ts_max'] = timestamp_ns.max()
        jitter[dst_port]['val_min'] = jitter_us.min()
        jitter[dst_port]['val_max'] = jitter_us.max()
    return jitter

def plotManualJittercalcMultiFlow(processing_descriptor):
    ''' plot jitter of a flow, both single ports individually and all ports combined in a plot'''
    check_csvs(processing_descriptor)
    if len(processing_descriptor.dst_ports) == 0:
        return
    topicLong = "Jitter"
    topicShort = "jitter"
    if pp.plots_exist(topicShort+processing_descriptor.png_string(), processing_descriptor, topicShort):
        return
    fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

    jitter = df_jitter(processing_descriptor)
    
    ports = [[port] for port in processing_descriptor.dst_ports]
    if len(processing_descriptor.dst_ports) > 1:
        ports.append(processing_descriptor.dst_ports)

    for dst_ports in ports:
        processing_descriptor.dst_ports = dst_ports
        maxTS, minTS = max_min_ts(jitter, dst_ports)
        fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)
        
        minHeight = min([float('inf')] + [x['val_min'] for x in jitter.values()])
        maxHeight = max([float('-inf')] + [x['val_max'] for x in jitter.values()])
        for dst_port in processing_descriptor.dst_ports:
            ax.plot((jitter[dst_port]['ts'] - minTS).div(1e9), jitter[dst_port]['val'], '.', label='Flow ' + str(dst_port-1000), zorder=10-(dst_port-1000), color=pp.stream_to_color[dst_port%100])
        ax.set_xlim(0,(maxTS-minTS)/1e9)
        ax.set_ylim(minHeight,maxHeight)
        # ax.set_ylim(minHeight*1e6,maxHeight*1e6)
        ax.grid(which='both')
        ax.ticklabel_format(useOffset=False, style='plain')

        plt.legend()
        plt.xlabel('Experiment Time [s]')
        plt.ylabel('Jitter [\u03BCs]')

        plotName = topicShort+processing_descriptor.png_string()
        pp.follow_up(plotName, processing_descriptor, topicShort, fl, startTime, fig)

def df_cdf_jitter(pd):
    ''' load csv for plotting CDF of jitter '''
    jitter = {}
    for dst_port in pd.dst_ports:
        df = read_csv(pd, dst_port)
        jitter[dst_port] = {}
        jitter_us = df['jitter_ns'].div(1e3)
        jitter[dst_port]['val'] = jitter_us
    return jitter

def plotManualJitterCDFcalcMultiFlow(processing_descriptor):
    ''' plot jitter CDF of a flow, both single ports individually and all ports combined in a plot'''
    check_csvs(processing_descriptor)
    if len(processing_descriptor.dst_ports) == 0:
        return
    topicLong = "Jitter CDF"
    topicShort = "jitterCDF"
    if pp.plots_exist(topicShort+processing_descriptor.png_string(), processing_descriptor, topicShort):
        return
    fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

    jitter = df_cdf_jitter(processing_descriptor)

    ports = [[port] for port in processing_descriptor.dst_ports]
    if len(processing_descriptor.dst_ports) > 1:
        ports.append(processing_descriptor.dst_ports)

    for dst_ports in ports:
        processing_descriptor.dst_ports = dst_ports
        fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)
        
        absMax = 0
        for dst_port in processing_descriptor.dst_ports:
            sorted_data = np.sort(jitter[dst_port]['val'])
            linspaced = np.linspace(0, 1, len(jitter[dst_port]['val']), endpoint=True)
            #cutOutliers = 0 # min(1500, int(len(sorted_data)/4))
            absMax = max(absMax, max([abs(x) for x in sorted_data]))
            ax.plot(sorted_data, linspaced, '.-', label='Flow ' + str(dst_port-1000), zorder=10-(dst_port-1000), color=pp.stream_to_color[dst_port%100])
            # ax.plot(jitter[dst_port]['Val'], '.-', label='Flow ' + str(dst_port-1000), zorder=dst_port-980, color=pp.stream_to_color[dst_port%100])

        # ax.set_xlim(0,15)
        ax.set_xlim(-absMax,absMax)
        ax.grid(which='both')
        ax.ticklabel_format(useOffset=False, style='plain')

        plt.legend()
        plt.xlabel('Jitter [\u03BCs]')
        plt.ylabel('CDF')

        plotName = topicShort+processing_descriptor.png_string()
        pp.follow_up(plotName, processing_descriptor, topicShort, fl, startTime, fig)

def df_packet_loss(pd):
    ''' load csv for plotting packet loss '''
    packet_loss = {}
    for dst_port in pd.dst_ports:
        df = read_csv(pd, dst_port)
        packet_loss[dst_port] = {}
        timestamp_loss_ns = df['timestamp_loss_ns'].dropna()
        cumulative_pkt_lost = [x+1 for x in range(len(timestamp_loss_ns))]
        packet_loss[dst_port]['ts'] = timestamp_loss_ns
        packet_loss[dst_port]['val'] = cumulative_pkt_lost
        timestamp_ns = df['timestamp_ns']
        packet_loss[dst_port]['ts_min'] = timestamp_ns.min()
        packet_loss[dst_port]['ts_max'] = timestamp_ns.max()
    return packet_loss

def plotManualPacketLosscalcMultiFlow(processing_descriptor):
    ''' plot packet loss of a flow, both single ports individually and all ports combined in a plot'''
    check_csvs(processing_descriptor)
    if len(processing_descriptor.dst_ports) == 0:
        return
    topicLong = "Packet Loss"
    topicShort = "cumulativePacketLoss"
    if pp.plots_exist(topicShort+processing_descriptor.png_string(), processing_descriptor, topicShort):
        return
    fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

    packetLoss = df_packet_loss(processing_descriptor)

    ports = [[port] for port in processing_descriptor.dst_ports]
    if len(processing_descriptor.dst_ports) > 1:
        ports.append(processing_descriptor.dst_ports)

    for dst_ports in ports:
        processing_descriptor.dst_ports = dst_ports
        maxTS, minTS = max_min_ts(packetLoss, dst_ports)
        fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

        for dst_port in processing_descriptor.dst_ports:
            ax.plot((packetLoss[dst_port]['ts'] - minTS).div(1e9), packetLoss[dst_port]['val'], 'o-', label='Flow ' + str(dst_port-1000), color=pp.stream_to_color[dst_port%100])

        # ax.set_ylim(0,2e6)
        ax.set_xlim(0,(maxTS-minTS)/1e9)
        ax.grid(which='both')
        ax.ticklabel_format(useOffset=False, style='plain')

        plt.legend()
        plt.xlabel('Experiment Time [s]')
        plt.ylabel('Cumulative Number of Lost Packets')

        plotName = topicShort+processing_descriptor.png_string()
        pp.follow_up(plotName, processing_descriptor, topicShort, fl, startTime, fig)

def plot_all(pd):
    plotManualDelaycalcMultiFlow(pd)
    plotManualJittercalcMultiFlow(pd)
    plotManualJitterCDFcalcMultiFlow(pd)
    plotManualPacketLosscalcMultiFlow(pd)

def main():
    pd = processing_descriptor.create_processing_descriptor_cli('plot_pcap_combined', 'Plots based on combined pcaps')

    plot_all(pd)
    #plotManualDelaycalcMultiFlow(pd)
    #plotManualJittercalcMultiFlow(pd)
    #plotManualJitterCDFcalcMultiFlow(pd)
    #plotManualPacketLosscalcMultiFlow(pd)

if __name__ == "__main__":
    main()

def prepColors(n):
    color=iter(plt.cm.rainbow(np.linspace(0,1,n)))
    for i in range(n):
        c=next(color)
        print('              ', 1000 + i, ':', '(', c[0], ',', c[1], ',', c[2], ',', c[3], '),')

# prepColors(50)