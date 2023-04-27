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
    df = pp.read_csv(pd.node_path() + 'csv-' + pd.service_name(dst_port) + '-combined_' + str(dst_port) + '_' + pd.iface + '.csv') #pd.iface + 'DelayAndJitterFlowIperf' + str(dst_port) + '.csv')
    df = df.loc[df['timestamp_ns'] >= df['timestamp_ns'].min() + pd.warmup]
    return df

def max_min_ts(df_dict):
    max_ts = max([float('-inf')] + [x['ts_max'] for x in df_dict.values()])
    min_ts = min([float('inf')] + [x['ts_min'] for x in df_dict.values()])
    return max_ts, min_ts

def df_delay(pd):
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
    topicLong = "Delay"
    topicShort = "delay"
    fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

    delay = df_delay(processing_descriptor)
    maxTS, minTS = max_min_ts(delay)
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

    plotName = 'delay'+processing_descriptor.png_string()
    pp.follow_up(plotName, processing_descriptor, topicShort, fl, startTime, fig)

def df_jitter(pd):
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
    topicLong = "Jitter"
    topicShort = "jitter"
    fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

    jitter = df_jitter(processing_descriptor)
    maxTS, minTS = max_min_ts(jitter)
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

    plotName = 'jitter'+processing_descriptor.png_string()
    pp.follow_up(plotName, processing_descriptor, topicShort, fl, startTime, fig)

def df_cdf_jitter(pd):
    jitter = {}
    for dst_port in pd.dst_ports:
        df = read_csv(pd, dst_port)
        jitter[dst_port] = {}
        jitter_us = df['jitter_ns'].div(1e3)
        jitter[dst_port]['val'] = jitter_us
    return jitter

def plotManualJitterCDFcalcMultiFlow(processing_descriptor):
    topicLong = "Jitter CDF"
    topicShort = "jitterCDF"
    fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

    absMax = 0
    jitter = df_cdf_jitter(processing_descriptor)
    for dst_port in processing_descriptor.dst_ports:
        sorted_data = np.sort(jitter[dst_port]['val'])
        linspaced = np.linspace(0, 1, len(jitter[dst_port]['val']), endpoint=True)
        cutOutliers = 1 # min(1500, int(len(sorted_data)/4)) # TODO: find better way than just excluding 1500 elements on both sides
        absMax = max(absMax, max([abs(x) for x in sorted_data[cutOutliers:-cutOutliers]]))
        ax.plot(sorted_data[cutOutliers:-cutOutliers], linspaced[cutOutliers:-cutOutliers], '.-', label='Flow ' + str(dst_port-1000), zorder=10-(dst_port-1000), color=pp.stream_to_color[dst_port%100])
        # ax.plot(jitter[dst_port]['Val'], '.-', label='Flow ' + str(dst_port-1000), zorder=dst_port-980, color=pp.stream_to_color[dst_port%100])

    # ax.set_xlim(0,15)
    ax.set_xlim(-absMax,absMax)
    ax.grid(which='both')
    ax.ticklabel_format(useOffset=False, style='plain')

    plt.legend()
    plt.xlabel('Jitter [\u03BCs]')
    plt.ylabel('CDF')

    plotName = 'jitter-CDF'+processing_descriptor.png_string()
    pp.follow_up(plotName, processing_descriptor, topicShort, fl, startTime, fig)

def df_packet_loss(pd):
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
    topicLong = "Packet Loss"
    topicShort = "cumulativePacketLoss"
    fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

    packetLoss = df_packet_loss(processing_descriptor)
    maxTS, minTS = max_min_ts(packetLoss)
    for dst_port in processing_descriptor.dst_ports:
        ax.plot((packetLoss[dst_port]['ts'] - minTS).div(1e9), packetLoss[dst_port]['val'], 'o-', label='Flow ' + str(dst_port-1000), color=pp.stream_to_color[dst_port%100])

    # ax.set_ylim(0,2e6)
    ax.set_xlim(0,(maxTS-minTS)/1e9)
    ax.grid(which='both')
    ax.ticklabel_format(useOffset=False, style='plain')

    plt.legend()
    plt.xlabel('Experiment Time [s]')
    plt.ylabel('Cumulative Number of Lost Packets')

    plotName = 'cumulative-packet-loss'+processing_descriptor.png_string()
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

# if __name__ == '__main__':
#     print('Called:', str(sys.argv))
#     if len(sys.argv) < 2:
#         print('ERROR: Not enough positional arguments! See code for explanation (A nice help function is WIP ;) )')
#         exit()
    
#     typePlot = sys.argv[1]
#     experimentName = sys.argv[2]
#     sourcePath = sys.argv[3]
#     path = sys.argv[4]

#     if typePlot == 'all': # plot everything
#         if len(sys.argv) < 5:
#             print('ERROR: Not enough positional arguments! See code for explanation (A nice help function is WIP ;) )')
#             exit()
#         nodeIface = sys.argv[5] # A list of node correlated with interfaces in format '[node-3:enp9s0, node-3:enp10s0] node identifier in format 'node-6' of the node from which to get the pcaps
#         nodeIfaceList = [(int(x.split(':')[0].split('-')[1]), x.split(':')[1]) for x in nodeIface.strip('[]').split(',')]
#         dstPorts = sys.argv[6] # A list of iperf destination ports. We are only interested in the traffic from sender to receiver at the moment.
#         dstPortsList = [int(x) for x in dstPorts.strip('[]').split(',')]
#         calcTimescale = sys.argv[7] # How often to calculate throughput in seconds
#         for node, iface in nodeIfaceList:
#             plotManualTPcalcMultiFlowOptTargetBitrate(experimentName, sourcePath, path, node, iface, dstPortsList, float(calcTimescale), 0)
#         plotManualDelaycalcMultiFlow(experimentName, sourcePath, path, nodeIfaceList[-1][0], nodeIfaceList[-1][1], dstPortsList)
#         plotManualJittercalcMultiFlow(experimentName, sourcePath, path, nodeIfaceList[-1][0], nodeIfaceList[-1][1], dstPortsList)

#     elif typePlot == 'singleBand': # plot throughput on one node/interface only
#         if len(sys.argv) < 5:
#             print('ERROR: Not enough positional arguments! See code for explanation (A nice help function is WIP ;) )')
#             exit()
#         node = sys.argv[5] # A single node identifier in format 'node-6' of the node from which to get the pcaps
#         iFace = sys.argv[6] # The interface for which to parse the pcap
#         dstPorts = sys.argv[7] # A list of iperf destination ports. We are only interested in the traffic from sender to receiver at the moment.
#         dstPortsList = [int(x) for x in dstPorts.strip('[]').split(',')]
#         calcTimescale = sys.argv[8] # How often to calculate throughput in seconds
#         plotManualTPcalcMultiFlowOptTargetBitrate(experimentName, sourcePath, path, int(node.split('-')[1]), iFace, dstPortsList, float(calcTimescale), 0)

#     elif typePlot == 'allBand': # plot throughput on all nodes/interfaces
#         if len(sys.argv) < 5:
#             print('ERROR: Not enough positional arguments! See code for explanation (A nice help function is WIP ;) )')
#             exit()
#         nodeIface = sys.argv[5] # A list of node correlated with interfaces in format '[node-3:enp9s0, node-3:enp10s0] node identifier in format 'node-6' of the node from which to get the pcaps
#         nodeIfaceList = [(int(x.split(':')[0].split('-')[1]), x.split(':')[1]) for x in nodeIface.strip('[]').split(',')]
#         dstPorts = sys.argv[6] # A list of iperf destination ports. We are only interested in the traffic from sender to receiver at the moment.
#         dstPortsList = [int(x) for x in dstPorts.strip('[]').split(',')]
#         calcTimescale = sys.argv[7] # How often to calculate throughput in seconds
#         for node, iface in nodeIfaceList:
#             plotManualTPcalcMultiFlowOptTargetBitrate(experimentName, sourcePath, path, node, iface, dstPortsList, float(calcTimescale), 0)


#     elif typePlot == 'delayJitterLossOnly': # plot only delay, jitter and packet loss between source and target
#         if len(sys.argv) < 5:
#             print('ERROR: Not enough positional arguments! See code for explanation (A nice help function is WIP ;) )')
#             exit()
#         node = sys.argv[5] # A single node identifier in format 'node-6' of the node from which to get the pcaps
#         iFace = sys.argv[6] # The interface for which to parse the pcap
#         dstPorts = sys.argv[7] # A list of iperf destination ports. We are only interested in the traffic from sender to receiver at the moment.
#         dstPortsList = [int(x) for x in dstPorts.strip('[]').split(',')]
        
#         plotManualDelaycalcMultiFlow(experimentName, sourcePath, path, int(node.split('-')[1]), iFace, dstPortsList)
#         # plotManualJittercalcMultiFlow(experimentName, sourcePath, path, int(node.split('-')[1]), iFace, dstPortsList)

#     else:
#         print('ERROR: Invalid plot type!')
#         exit()