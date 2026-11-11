#!/usr/bin/env python3

# iperf pcap plots

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import statistics
import sys
import time
import ndn.encoding as ndn
import os
import glob

import processing_descriptor
import plot_plots as pp

font = {'weight' : 'normal',
        'size'   : 20}
matplotlib.rc('font', **font)
matplotlib.rc('lines', linewidth=2.0)
matplotlib.rc('lines', markersize=8)

def check_csvs(pd):
    '''
    delete port from dst_ports if the corresponding csv does not exist (means tcpdump collection was not enabled for that port)
    '''
    for dst_port in pd.dst_ports[:]:
        if pd.process_to_csv:
            print("Previous scheme with fixed format")
            fileName = pd.node_path() + 'csv-' + pd.service_name(dst_port) + '-single_' + pd.get_port(dst_port) + '.csv'
        else:
            print("Based on file only")
            fileName = pd.pre_path() + "*" + str(dst_port) + "*"
            fileName = glob.glob(fileName)
            if len(fileName) > 1:
                for file in fileName:
                    if ".csv" in file:
                        fileName = file
            else:
                fileName = fileName[0]
            print("found filename", fileName)
        if not os.path.isfile(fileName):
            pd.dst_ports.remove(dst_port)
            with open(pd.log_file(), "a") as myFile:
                print('csv ' + fileName, ' does not exist.', end='...\n', file=myFile)

def read_csv(pd, dst_port):
    ''' loads csv corresponding to processing_descriptor '''
    if pd.process_to_csv:
        fileName = pd.node_path() + 'csv-' + pd.service_name(dst_port) + '-single_' + pd.get_port(dst_port) + '.csv'
    else:
        fileName = pd.pre_path() + "*" + str(dst_port) + "*"
        fileName = glob.glob(fileName)
        if len(fileName) > 1:
            for file in fileName:
                if ".csv" in file:
                    fileName = file
        else:
            fileName = fileName[0]
    print(fileName)
    df = pp.read_csv(fileName)
    print(df)
    df = df.loc[df['timestamp_ns'] >= df['timestamp_ns'].min() + pd.warmup]
    df = df.iloc[pd.offset:-pd.limit]
    # filter out interest packets for throughput calculation
    return df

def df_tp(processing_descriptor, targetBitrate=0, calculationTimescale=100000000, ndn_filter = []):
    ''' loads csv and calculates throughput '''
    toPlot = {}
    for dst_port in processing_descriptor.dst_ports:
        df = read_csv(processing_descriptor, dst_port)
        if ndn_filter != []:
            df = df.loc[df['type'].isin(ndn_filter)]
        if len(df.index) < 10:
            return {}
        initialTime = df['timestamp_ns'].iloc[0]
        if 'packet_size_bytes' not in df.columns:
            return {}
        # df['timestamp_ns'] = df['timestamp_ns'] - initialTime
        calculationWindow = [initialTime, initialTime + calculationTimescale]
        ts = []
        bitrates = []
        begIndex = 0
        lastIndex = 0
        while calculationWindow[0] <= df['timestamp_ns'].iloc[-1]:
            begIndex = lastIndex
            lastIndex = df['timestamp_ns'].searchsorted(calculationWindow[1])
            if begIndex < lastIndex:
                #tempDf = df.loc[(df['timestamp_ns'] >= calculationWindow[0]) & (df['timestamp_ns'] <= calculationWindow[1])]
                #mbps = (((tempDf['packet_size_bytes'].sum()*8)/1e6)/(calculationTimescale/1e9)) - targetBitrate

                mbps = (((df['packet_size_bytes'].iloc[begIndex:lastIndex].sum()*8)/1e6)/(calculationTimescale/1e9)) - targetBitrate
                ts.append((calculationWindow[0] + calculationWindow[1]) / 2)
                bitrates.append(mbps)
            else:
                ts.append((calculationWindow[0] + calculationWindow[1]) / 2)
                bitrates.append(0)
            # if mbps > 1.05 * statistics.mean(bitrates) or mbps < 0.95 * statistics.mean(bitrates):
            #     print(calculationWindow[1], mbps)
            calculationWindow = [x + calculationTimescale for x in calculationWindow]
        toPlot[dst_port] = {}
        toPlot[dst_port]['TS'] = ts
        toPlot[dst_port]['Val'] = bitrates
    return toPlot

def plotManualTPcalcMultiFlowOptDiffToTargetBitrate(processing_descriptor, targetBitrate=0, calculationTimescale=100000000, ndn_filter = [], add_name = ""):
    '''
        Depending on targetBitrate==0 or targetBitrate>0 either plot throughput or difference of throughput and target bitrate
    '''
    check_csvs(processing_descriptor)
    if len(processing_descriptor.dst_ports) == 0:
        return
    topicLong = "Throughput"
    topicShort = "throughput"
    if ndn_filter != [] and add_name != "":
        topicLong = topicLong + " " + add_name
        topicShort = topicShort + "_" + add_name
    plotName = topicShort+processing_descriptor.png_string()
    if pp.plots_exist(plotName, processing_descriptor, topicShort):
        return
    fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

    toPlot = df_tp(processing_descriptor, targetBitrate, calculationTimescale)
    ports = [[port] for port in processing_descriptor.dst_ports]
    if len(processing_descriptor.dst_ports) > 1:
        ports.append(processing_descriptor.dst_ports)
    for dst_ports in ports:
        processing_descriptor.dst_ports = dst_ports
        fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

        try:
            minTS = min(float('inf'), min([toPlot[x]['TS'][0] for x in dst_ports]))
        except KeyError:
            return
        minTS = min(float('inf'), min([toPlot[x]['TS'][0] for x in dst_ports]))
        maxTS = max(0, max([toPlot[x]['TS'][-1] for x in dst_ports]))
        maxTPorDev = max(0, max([abs(max(toPlot[x]['Val'], key=abs)) for x in dst_ports])) ## max TP for TB = 0, max Dev fo TB > 0
        color = 1
        for dst_port in processing_descriptor.dst_ports:
            ax.plot([(x - minTS) / 1e9 for x in toPlot[dst_port]['TS']], toPlot[dst_port]['Val'], '.-', color=pp.stream_to_color[color], label='Stream ' + processing_descriptor.get_stream(dst_port))
            color += 1

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

        plotName = topicShort+processing_descriptor.png_string()
        pp.follow_up(plotName, processing_descriptor, topicShort, fl, startTime, fig)


def df_cdf_ifs(processing_descriptor, ndn_filter = []):
    ''' loads csv and calculates inter frame spacing '''
    interFramSpacs = {}
    # allVals = []
    for dst_port in processing_descriptor.dst_ports:
        # previously operated on combined csv, yielding ifs for source pcap:
        # df = pp.read_csv(processing_descriptor.node_path() + 'csv-' + pd.service_name(dst_port) + '-combined_' + str(dst_port) + '_' + processing_descriptor.iface + '.csv') # processing_descriptor.iface + 'DelayAndJitterFlowIperf' + str(dst_port) + '.csv')
        # now uses pcap csv, for plotting ifs for both, source and destination:
        df = read_csv(processing_descriptor, dst_port)
        if ndn_filter != []:
            df = df.loc[df['type'].isin(ndn_filter)]
        ifs_tmp = df['timestamp_ns'].dropna().diff().tolist()[1:]
        ifs = []
        for value_ifs in ifs_tmp:
            # normalize TAI
            diff = value_ifs - 37000000000
            if diff > 0:
                ifs.append(diff)
            else:
                ifs.append(value_ifs)
        interFramSpacs[dst_port] = {}
        interFramSpacs[dst_port]['Val'] = ifs
        # allVals.extend(ifs)
    return interFramSpacs

def plotManualIfsCDFcalcMultiFlow(processing_descriptor, ndn_filter = [], add_name = ""):
    ''' plots inter frame spacing CDF '''
    check_csvs(processing_descriptor)
    if len(processing_descriptor.dst_ports) == 0:
        return
    topicLong = "Inter-Frame Spacing"
    topicShort = "ifsCDF"
    if ndn_filter != [] and add_name != "":
        topicLong = topicLong + " " + add_name
        topicShort = topicShort + "_" + add_name
    plotName = topicShort+processing_descriptor.png_string()
    if pp.plots_exist(plotName, processing_descriptor, topicShort):
        return
    fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

    interFramSpacs = df_cdf_ifs(processing_descriptor)

    ports = [[port] for port in processing_descriptor.dst_ports]
    if len(processing_descriptor.dst_ports) > 1:
        ports.append(processing_descriptor.dst_ports)

    for dst_ports in ports:
        processing_descriptor.dst_ports = dst_ports
        fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)
        color = 1
        for dst_port in processing_descriptor.dst_ports:
            sorted_data = np.sort(interFramSpacs[dst_port]['Val'])
            linspaced = np.linspace(0, 1, len(interFramSpacs[dst_port]['Val']), endpoint=True)
            lbl = 'Measured'
            if len(processing_descriptor.dst_ports) > 1:
                lbl = 'Flow ' + str(dst_port)
            ax.plot(sorted_data, linspaced, '.-', label=lbl, color=pp.stream_to_color[color])
            color += 1

        if len(processing_descriptor.dst_ports) <= 1: ax.vlines(100, ymin=0, ymax=1, alpha=0.9, zorder=1000, color='tab:red', label='Target')

        ax.set_xlim(0, max([max(x['Val'], default=0) for x in interFramSpacs.values()])) # max(allVals))
        # ax.set_ylim(0,1)
        ax.grid(which='both')
        ax.ticklabel_format(useOffset=False, style='plain')

        plt.legend()
        plt.xlabel('Inter-Frame Spacing [\u03BCs]')
        plt.ylabel('CDF')

        plotName = topicShort+processing_descriptor.png_string()
        pp.follow_up(plotName, processing_descriptor, topicShort, fl, startTime, fig)

def max_min_ts(df_dict, dst_ports):
    ''' returns max/min timestamp '''
    max_ts = max([float('-inf')] + [df_dict[x]['ts_max'] for x in dst_ports])
    min_ts = min([float('inf')] + [df_dict[x]['ts_min'] for x in dst_ports])
    return max_ts, min_ts

def df_ifs(processing_descriptor, ndn_filter = []):
    ''' loads csv and calculates inter frame spacing '''
    ifs = {}
    for dst_port in processing_descriptor.dst_ports:
        df = read_csv(processing_descriptor, dst_port)
        if ndn_filter != []:
            df = df.loc[df['type'].isin(ndn_filter)]
        if len(df.index) < 10:
            return {}
        ifs[dst_port] = {}
        timestamp_ns = df['timestamp_ns'].dropna()#.tolist()
        # ifs_us = [(x - y) / 1e3 for x,y in zip(timestamp_ns[1:], timestamp_ns[:-1])]
        ifs_us = timestamp_ns.diff().tolist()[1:]
        ifs[dst_port]['ts'] = timestamp_ns.iloc[1:] # use later ts
        ifs[dst_port]['val'] = ifs_us
        ifs[dst_port]['ts_min'] = timestamp_ns.min()
        ifs[dst_port]['ts_max'] = timestamp_ns.max()
        ifs[dst_port]['val_min'] = min(ifs_us, default=0)#.min()
        ifs[dst_port]['val_max'] = max(ifs_us, default=0)#.max()
    return ifs

def plot_ifs(processing_descriptor, ndn_filter = [], add_name = ""):
    ''' plots inter frame spacing '''
    check_csvs(processing_descriptor)
    if len(processing_descriptor.dst_ports) == 0:
        return
    topicLong = "IFS"
    topicShort = "ifs"
    if ndn_filter != [] and add_name != "":
        topicLong = topicLong + " " + add_name
        topicShort = topicShort + "_" + add_name
    plotName = topicShort+processing_descriptor.png_string()
    if pp.plots_exist(plotName, processing_descriptor, topicShort):
        return
    fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

    ifs = df_ifs(processing_descriptor)
    if not bool(ifs):
        print("not enough data")
        return

    ports = [[port] for port in processing_descriptor.dst_ports]
    if len(processing_descriptor.dst_ports) > 1:
        ports.append(processing_descriptor.dst_ports)

    for dst_ports in ports:
        processing_descriptor.dst_ports = dst_ports
        fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

        maxTS, minTS = max_min_ts(ifs, dst_ports)
        minHeight = min([float('inf')] + [ifs[x]['val_min'] for x in dst_ports])
        maxHeight = max([float('-inf')] + [ifs[x]['val_max'] for x in dst_ports])
        color = 1
        for dst_port in processing_descriptor.dst_ports:
            ax.plot((ifs[dst_port]['ts'] - minTS).div(1e9), ifs[dst_port]['val'], '.', label='Flow ' + str(dst_port), color=pp.stream_to_color[color])
            color += 1

        # if len(processing_descriptor.dst_ports) <= 1: ax.hlines(100, xmin=0, xmax=maxTS-minTS, alpha=0.9, zorder=1000, color='tab:red', label='Target')

        ax.set_xlim(0,(maxTS-minTS)/1e9)
        ax.set_ylim(minHeight,maxHeight)
        # ax.set_ylim(minHeight*1e6,maxHeight*1e6)
        ax.grid(which='both')
        ax.ticklabel_format(useOffset=False, style='plain')

        plt.legend()
        plt.xlabel('Experiment Time [s]')
        plt.ylabel('IFS [\u03BCs]')

        plotName = topicShort+processing_descriptor.png_string()
        pp.follow_up(plotName, processing_descriptor, topicShort, fl, startTime, fig)

def df_ndn_rtt(pd, ndn_filter = []):
    ''' loads csv and calculates ndn rtt '''
    ndn_rtt = {}
    for dst_port in pd.dst_ports:
        df = read_csv(pd, dst_port)
        if ndn_filter != []:
            df = df.loc[df['type'].isin(ndn_filter)]
        ndn_rtt[dst_port] = {}
        # match interest packets to data packets
        df_int = df.loc[(df['type'] == ndn.TypeNumber.INTEREST) & (df['direction'] == 'out')]
        df_data = df.loc[df['type'].isin([ndn.TypeNumber.DATA, ndn.LpTypeNumber.LP_PACKET]) & (df['direction'] == 'in')]
        df = df_int.merge(df_data, how='left', on='ndn_name')
        df = df.dropna()
        df['timestamp_ns_y'] = df['timestamp_ns_y'].astype(np.int64)
        df['delay'] = df.apply(lambda row: row['timestamp_ns_y'] - row['timestamp_ns_x'], axis=1)
        ndn_rtt[dst_port]['ts'] = df['timestamp_ns_y']
        ndn_rtt[dst_port]['delay'] = df['delay']
        if len(ndn_rtt[dst_port]['ts']) == 0:
            ndn_rtt[dst_port]['ts_min'] = 0
            ndn_rtt[dst_port]['ts_max'] = 0
            continue
        ndn_rtt[dst_port]['ts_min'] = ndn_rtt[dst_port]['ts'].iloc[0]
        ndn_rtt[dst_port]['ts_max'] = ndn_rtt[dst_port]['ts'].iloc[-1]

    return ndn_rtt

# plot delay between sending interest and receiving data
def plotNDNrtt(pd, ndn_filter = [], add_name = ""):
    check_csvs(pd)
    if len(pd.dst_ports) == 0:
        return
    topicLong = "ndn_rtt"
    topicShort = "ndn_rtt"
    if ndn_filter != [] and add_name != "":
        topicLong = topicLong + " " + add_name
        topicShort = topicShort + "_" + add_name
    plotName = topicShort+pd.png_string()
    if pp.plots_exist(plotName, pd, topicShort):
        return
    fl, startTime, fig, ax = pp.prepare(topicLong, pd)

    ndn_rtt = df_ndn_rtt(pd)


    ports = [[port] for port in pd.dst_ports]
    if len(pd.dst_ports) > 1:
        ports.append(pd.dst_ports)

    for dst_ports in ports:
        pd.dst_ports = dst_ports
        fl, startTime, fig, ax = pp.prepare(topicLong, pd)

        maxTS, minTS = max_min_ts(ndn_rtt, dst_ports)
        #minHeight = min([float('inf')] + [ndn_rtt[x]['val_min'] for x in dst_ports])
        #maxHeight = max([float('-inf')] + [ndn_rtt[x]['val_max'] for x in dst_ports])
        color = 1
        notEmpty = False
        for dst_port in pd.dst_ports:
            if len(ndn_rtt[dst_port]['ts']) == 0:
                continue
            notEmpty = True
            ax.plot((ndn_rtt[dst_port]['ts'] - minTS).div(1e9), ndn_rtt[dst_port]['delay'].div(1e3), '.', label='Flow ' + str(dst_port), color=pp.stream_to_color[color])
            color += 1

        if not notEmpty:
            continue
        ax.set_xlim(0,(maxTS-minTS)/1e9)
        #ax.set_ylim(minHeight,maxHeight)
        # ax.set_ylim(minHeight*1e6,maxHeight*1e6)
        ax.grid(which='both')
        ax.ticklabel_format(useOffset=False, style='plain')

        plt.legend()
        plt.xlabel('Experiment Time [s]')
        plt.ylabel('RTT [\u03BCs]')

        plotName = topicShort+pd.png_string()
        pp.follow_up(plotName, pd, topicShort, fl, startTime, fig)

def df_algo_rounds_interval(pd):
    ''' load csv for plotting Algorand rounds interval '''
    rounds_interval = {}
    for dst_port in pd.dst_ports:
        fileName = pd.node_path() + 'csv-' + pd.service_name(dst_port) + '-algo-rounds_' + pd.get_port(
            dst_port) + '.csv'
        if not os.path.isfile(fileName):
            return None
        df = pp.read_csv(fileName)
        rounds_interval[dst_port] = {}
        rnd = df['round'].iloc[2:-1] - 1
        timestamp_ns = df['timestamp_ns'].diff().div(1e9).iloc[2:-1]
        rounds_interval[dst_port]['round'] = rnd
        rounds_interval[dst_port]['interval_s'] = timestamp_ns
        rounds_interval[dst_port]['ts_min'] = timestamp_ns.min()
        rounds_interval[dst_port]['ts_max'] = timestamp_ns.max()
        rounds_interval[dst_port]['round_min'] = rnd.min()
        rounds_interval[dst_port]['round_max'] = rnd.max()

    return rounds_interval

def plotManualAlgorandRoundIntervals(processing_descriptor, ndn_filter=[], add_name=""):
    ''' plot rounds interval for Algorand '''
    check_csvs(processing_descriptor)
    if len(processing_descriptor.dst_ports) == 0:
        return
    topicLong = "Algorand Round Interval"
    topicShort = "algo-rounds"
    if ndn_filter != [] and add_name != "":
        topicLong = topicLong + " " + add_name
        topicShort = topicShort + "_" + add_name
    if pp.plots_exist(topicShort + processing_descriptor.png_string(), processing_descriptor, topicShort):
        return
    fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

    rounds_interval = df_algo_rounds_interval(processing_descriptor)
    if rounds_interval is None:
        return

    ports = [[port] for port in processing_descriptor.dst_ports]
    if len(processing_descriptor.dst_ports) > 1:
        ports.append(processing_descriptor.dst_ports)

    for dst_ports in ports:
        processing_descriptor.dst_ports = dst_ports
        maxTS, minTS = max_min_ts(rounds_interval, dst_ports)
        fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

        maxLen = max([x['round_max'] for x in rounds_interval.values()], default=0)
        minLen = max([x['round_min'] for x in rounds_interval.values()], default=0)
        color = 1
        for dst_port in processing_descriptor.dst_ports:
            ax.plot(rounds_interval[dst_port]['round'], rounds_interval[dst_port]['interval_s'], '.', label='Delta',
                    color=pp.stream_to_color[color])
            color += 1
        ax.set_xlim(minLen, maxLen)
        ax.grid(which='both')
        ax.set_ylim(minTS, maxTS)
        ax.ticklabel_format(useOffset=False, style='plain')

        plt.legend()
        plt.xlabel('Round Number')
        plt.ylabel('Round Time Interval [s]')

        plotName = topicShort + processing_descriptor.png_string()
        pp.follow_up(plotName, processing_descriptor, topicShort, fl, startTime, fig)



def df_etheruem_overhad_latency(pd):
    ''' load csv for plotting Algorand rounds interval '''
    latencies = {}
    for dst_port in pd.dst_ports:
        fileName = pd.node_path() + 'csv-' + pd.service_name(dst_port) + '-transactions-times_' + pd.get_port(
            dst_port) + '_' + pd.iface + '.csv'
        if not os.path.isfile(fileName):
            return None
        df = pp.read_csv(fileName)
        latencies[dst_port] = {}

        latency = df['pending_timestamp_ns'] - df['sent_timestamp_ns']
        timestamp_ns = df['sent_timestamp_ns']
        latencies[dst_port]['overhead'] = latency
        latencies[dst_port]['ts'] = timestamp_ns
        latencies[dst_port]['latency_min'] =  latency.min()
        latencies[dst_port]['latency_max'] =  latency.max()
    print(latencies)
    return latencies



# def plotManualEthereumOverhead(processing_descriptor, ndn_filter=[], add_name="" ):
#     ''' plot OVerhead Latency for Ethereum '''
#     print("plotting etheruen overhead")
#     check_csvs(processing_descriptor)
#     if len(processing_descriptor.dst_ports) == 0:
#         return

#     topicLong = "Ethreum Transaction Broadcast Overhead"
#     topicShort = "ethereum_overhead"
#     if ndn_filter != [] and add_name != "":
#         topicLong = topicLong + " " + add_name
#         topicShort = topicShort + "_" + add_name
#     if pp.plots_exist(topicShort + processing_descriptor.png_string(), processing_descriptor, topicShort):
#         return
#     fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)
#     overhead = df_etheruem_overhad_latency(processing_descriptor)
#     if overhead is None:
#         return
#     ports = [[port] for port in processing_descriptor.dst_ports]
#     if len(processing_descriptor.dst_ports) > 1:
#         ports.append(processing_descriptor.dst_ports)

#     for dst_ports in ports:
#         processing_descriptor.dst_ports = dst_ports
#         fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)
#         color = 1
      
#         for dst_port in processing_descriptor.dst_ports:
#             ax.plot(overhead[dst_port]['overhead'],'.' ,label='Delta',
#                     color=pp.stream_to_color[color])
#             color += 1
#             maxOverhead = overhead[dst_port]["latency_max"] + 200
#             minOverhead = overhead[dst_port]["latency_min"] - 200
     
#         ax.grid(which='both')
#         ax.ticklabel_format(useOffset=False, style='plain')
#         ax.set_ylim(minOverhead, maxOverhead)

#         plt.legend()
#         plt.xlabel('Experiment Time [s]')
#         plt.ylabel('Transaction Overhead Latency (ns)')

#         plotName = topicShort + processing_descriptor.png_string()
#         pp.follow_up(plotName, processing_descriptor, topicShort, fl, startTime, fig)

def plot_all(pd):
    if not pd.ndn:
        # Applies to algorand only
        if "av" in pd.msg_types:
            plotManualAlgorandRoundIntervals(pd)
        plotManualTPcalcMultiFlowOptDiffToTargetBitrate(pd)
        plotManualIfsCDFcalcMultiFlow(pd)
        plot_ifs(pd)
    if pd.ndn:
        plotManualTPcalcMultiFlowOptDiffToTargetBitrate(pd, ndn_filter=[ndn.TypeNumber.DATA, ndn.LpTypeNumber.LP_PACKET])
        plotManualIfsCDFcalcMultiFlow(pd, ndn_filter=[ndn.TypeNumber.DATA, ndn.LpTypeNumber.LP_PACKET])
        plot_ifs(pd, ndn_filter=[ndn.TypeNumber.DATA, ndn.LpTypeNumber.LP_PACKET])
        plotNDNrtt(pd)

def main():
    pd = processing_descriptor.create_processing_descriptor_cli('plot_pcap', 'Plots based on single pcaps')

    #plotManualTPcalcMultiFlowOptDiffToTargetBitrate(pd)
    #plotManualIfsCDFcalcMultiFlow(pd)
    #plot_ifs(pd)
    plot_all(pd)

if __name__ == "__main__":
    main()
