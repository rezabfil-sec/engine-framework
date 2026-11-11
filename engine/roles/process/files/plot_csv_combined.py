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

import processing_descriptor
import plot_plots as pp
import db_queries as dq

font = {'weight' : 'normal',
        'size'   : 20}
matplotlib.rc('font', **font)
matplotlib.rc('lines', linewidth=2.0)
matplotlib.rc('lines', markersize=8)

# These are only debug flags to make it faster - already minimizing stuff on the input when reading the CSVs
offset = 1
limit = 1


# Remove
# def check_csvs(pd):
#     '''deletes port from dst_ports if the corresponding csv does not exist (means tcpdump collection was not enabled for that port)'''
#     for dst_port in pd.dst_ports[:]:
#         fileName = pd.node_path() + 'csv-' + pd.service_name(dst_port) + '-combined_' + pd.get_port(dst_port) + '_' + pd.iface + '.csv'
#         if not os.path.isfile(fileName):
#             pd.dst_ports.remove(dst_port)
#             with open(pd.log_file(), "a") as myFile:
#                 print('csv-' + pd.service_name(dst_port) + '-combined_' + pd.get_port(dst_port) + '_' + pd.iface + '.csv', ' does not exist.', end='...\n', file=myFile)

# def read_csv(pd, dst_port):
#     ''' loads csv corresponding to processing_descriptor '''
#     df = pp.read_csv(pd.node_path() + 'csv-' + pd.service_name(dst_port) + '-combined_' + pd.get_port(dst_port) + '_' + pd.iface + '.csv') #pd.iface + 'DelayAndJitterFlowIperf' + str(dst_port) + '.csv')
#     df = df.loc[df['timestamp_ns'] >= df['timestamp_ns'].min() + pd.warmup]
#     return df

def read_database_group(processing_descriptor, group_nr, experiment, column="delay"):
    ''' loads delay corresponding to processing_descriptor '''
    # Decide here if Scenario 1 - 1-1 mapping (source-sink, e.g., iperf3)
    # Scenario 2 - 1-N mapping (source - hops e.g., blockchain)
    if len(processing_descriptor.experiments) > 1:
        df = dq.query_delay_jitter(processing_descriptor, group_nr, experiment, column)
    else:
        df = dq.query_delay(processing_descriptor, group_nr)
    df = df.loc[df['timestamp_1'] >= df['timestamp_1'].min() + processing_descriptor.warmup]
    df = df.iloc[offset:-limit]
    return df

def read_database_packet_loss(processing_descriptor, group_nr=0, experiment=""):
    ''' loads delay corresponding to processing_descriptor '''
    df = dq.query_loss(processing_descriptor, group_nr, experiment) #pd.iface + 'DelayAndJitterFlowIperf' + str(dst_port) + '.csv')
    return df

def max_min_ts(df_dict, dst_ports):
    ''' gets max and min timestamp '''

    max_ts = max([df_dict[x]['ts_max'] for x in dst_ports], default=0)
    min_ts = min([df_dict[x]['ts_min'] for x in dst_ports], default=0)
    return max_ts, min_ts

def df_delay(processing_descriptor, ndn_filter=[]):
# change this logic to return df delay from the DB
    ''' load data for plotting delay '''
    # no need (at least here to loop through)
    # for dst_port in pd.dst_ports:
        # df = read_csv(pd, dst_port)
        # Here return the whole df query
    delay = {}
    df_delay_jitter = {}
    delay_format = processing_descriptor.delay_format
    for experiment in processing_descriptor.experiments:
        if experiment not in delay.keys():
            delay[experiment] = {}
        for dst_port in processing_descriptor.dst_ports:
            index = processing_descriptor.dst_ports.index(dst_port)
            tmp_df_delay_jitter = read_database_group(processing_descriptor, processing_descriptor.groups_to_add[index], experiment)
            df_delay_jitter[dst_port] = tmp_df_delay_jitter
            # FIXME NDN
            if ndn_filter != []:
                df_delay_jitter = df_delay_jitter.loc[df_delay_jitter['type'].isin(ndn_filter)]
            delay[experiment][dst_port] = {}
            # timestamp_1 corresponds to the source time
            timestamp_ns = tmp_df_delay_jitter['timestamp_1']
            delay[experiment][dst_port]['ts'] = timestamp_ns
            if delay_format == "ms":
                delay_ms = tmp_df_delay_jitter['delay'].div(1e6)
                delay[experiment][dst_port]['val'] = delay_ms
                delay[experiment][dst_port]['val_max'] = delay_ms.max()
                delay[experiment][dst_port]['val_min'] = delay_ms.min()
            elif delay_format == "us":
                delay_us = tmp_df_delay_jitter['delay'].div(1e3)
                delay[experiment][dst_port]['val'] = delay_us
                delay[experiment][dst_port]['val_max'] = delay_us.max()
                delay[experiment][dst_port]['val_min'] = delay_us.min()
            if len(timestamp_ns) > 0:
                delay[experiment][dst_port]['ts_min'] = timestamp_ns.min()
                delay[experiment][dst_port]['ts_max'] = timestamp_ns.max()
            else:
                delay[experiment][dst_port]['ts_min'] = 0
                delay[experiment][dst_port]['ts_max'] = 0
        # print("printing here in delay", delay)
    # sys.exit(0)
    # if len(pd.group_nrs) > 1:
    #     return delay, df_delay_jitter
    return delay, df_delay_jitter

def plotManualDelaycalcMultiFlow(processing_descriptor, ndn_filter = [], add_name = ""):
    ''' plot delay of a flow, both single ports individually and all ports combined in a plot'''
    # Not relevant
    # check_csvs(processing_descriptor)
    # if len(processing_descriptor.dst_ports) == 0:
    #     return
    topicLong = "Delay"
    topicShort = "delay"
    delay_format = processing_descriptor.delay_format
    label_format = processing_descriptor.label_format
    if ndn_filter != [] and add_name != "":
        topicLong = topicLong + " " + add_name
        topicShort = topicShort + "_" + add_name

    fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)
    # here modify and provide delays from DB
    delay, df_delay_jitter = df_delay(processing_descriptor)

    if pp.plots_exist(topicShort + processing_descriptor.png_string(), processing_descriptor, topicShort):
        return df_delay_jitter
    
    # Those could be extracted from the same experiment
    # e.g., 3 ports in the same experiment, for now assume 1
    ports = [[port] for port in processing_descriptor.dst_ports]
    if len(processing_descriptor.dst_ports) > 1:
        ports.append(processing_descriptor.dst_ports)
    maxTSs = {}
    minTSs = {}
    maxHeights = {}
    minHeights = {}
    for experiment in processing_descriptor.experiments:
        minTSs[experiment] = {}
        maxTSs[experiment] = {}
        maxHeights[experiment] = {}
        minHeights[experiment] = {}
        for dst_ports in ports:
            # FIXME - the X axis cannot be limited like this - the stuff was run during differnt times
            maxTSs[experiment]['values'] = []
            minTSs[experiment]['values'] = []
            maxTS, minTS = max_min_ts(delay[experiment], dst_ports)
            maxTSs[experiment]['values'].append(maxTS)
            minTSs[experiment]['values'].append(minTS)

            maxHeights[experiment]['values'] = []
            minHeights[experiment]['values'] = []
            maxHeight = max([x['val_max'] for x in delay[experiment].values()], default=0)
            minHeight = max([x['val_min'] for x in delay[experiment].values()], default=0)
            maxHeights[experiment]['values'].append(maxHeight)
            minHeights[experiment]['values'].append(minHeight)
            # print("max, min, limit", maxTS, minTS, (maxTS - minTS) / 1e9)
    # Compute a diff between experiment 1 and experiment 2
    # localMins = []
    # localMaxs = []
    # diff = []
    # for experiment in minTSs.keys():
    #     localMins.append(min(minTSs[experiment]['values']))
    #     localMaxs.append(max(maxTSs[experiment]['values']))
    # for localMin in localMins:
    #     index = localMins.index(localMin)
    #     if index + 1 < len(localMins):
    #         diff.append(localMins[index+1] - localMaxs[index])
    # run = 0
    # for experiment in minTSs.keys():
    #     print(run)
    #     if run == 0:
    #        minTSs[experiment]["diff"] = 0
    #     else:
    #         minTSs[experiment]["diff"] = diff[run-1]
    #     run = run + 1
    for dst_ports in ports:
        processing_descriptor.dst_ports = dst_ports
        fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)
        color = 1
        run = 0
        for experiment in processing_descriptor.experiments:
            print("Here is in the ss experiment", experiment)
            for dst_port in processing_descriptor.dst_ports:
                print("Here is in the ss port", dst_port, delay[experiment][dst_port]['ts'][:5], delay[experiment][dst_port]['val'][:5])
                if label_format == "flow":
                    label = 'Flow ' + str(dst_port) + "_" + str(run)
                elif label_format == "algorand":
                    label = 'AV Delay' + str(dst_port) + "_" + str(run)
                else:
                    label = label_format + str(dst_port) + "-" + str(run)
                ax.plot((delay[experiment][dst_port]['ts'] - min(minTSs[experiment]['values'])).div(1e9), delay[experiment][dst_port]['val'], '.', label=label, color=pp.stream_to_color[color])    
                color += 1
            run += 1

        ax.grid(which='both')
        # 0 is clear, maxTS and minTS
        # Experiment dependent
        # ax.set_xlim(0, 6)
        # Keep an eye on this one
        if min(minHeights[experiment]['values']) > 0:
        # print("height below 0", minHeight, maxHeight)
            ax.set_ylim(0, max(maxHeights[experiment]['values']))
        else:
            ax.set_ylim(0, max(maxHeights[experiment]['values']))
        ax.ticklabel_format(useOffset=False, style='plain')

        plt.legend()
        plt.xlabel('Experiment Time [s]')

        if delay_format == "ms":
            plt.ylabel('End-To-End Delay [ms]')
        elif delay_format == "us":
            plt.ylabel('End-To-End Delay [us]')

        plotName = topicShort + processing_descriptor.png_string()
        pp.follow_up(plotName, processing_descriptor, topicShort, fl, startTime, fig)
    # Relevant not only for the initial combined
    return df_delay_jitter

def df_jitter(processing_descriptor, df_delay_jitter, ndn_filter=[]):
    ''' load csv for plotting jitter '''
    # Change here to read from DB
    jitter = {}
    for experiment in processing_descriptor.experiments:
        jitter[experiment] = {}
        for dst_port in processing_descriptor.dst_ports:
            index = processing_descriptor.dst_ports.index(dst_port)
            if len(processing_descriptor.experiments) > 1:
                df_delay_jitter = read_database_group(processing_descriptor, processing_descriptor.groups_to_add[index], experiment, "jitter")
                df_delay_jitter.at[0, 'jitter'] = 0
                timestamp_ns = df_delay_jitter['timestamp_1']
                jitter_us = df_delay_jitter['jitter'].div(1e3)
            else:
                df_delay_jitter[dst_port].at[0, 'jitter'] = 0
                timestamp_ns = df_delay_jitter[dst_port]['timestamp_1']
                jitter_us = df_delay_jitter[dst_port]['jitter'].div(1e3)
            # df = read_csv(pd, dst_port)
            # FIXME
            if ndn_filter != []:
                df = df_delay_jitter.loc[df_delay_jitter['jitter'].isin(ndn_filter)]
            # df['jitter'] = df['delay_ns'].diff()
            jitter[experiment][dst_port] = {}
            jitter[experiment][dst_port]['ts'] = timestamp_ns
            jitter[experiment][dst_port]['val'] = jitter_us
            jitter[experiment][dst_port]['ts_min'] = timestamp_ns.min()
            jitter[experiment][dst_port]['ts_max'] = timestamp_ns.max()
            jitter[experiment][dst_port]['val_min'] = jitter_us.min()
            jitter[experiment][dst_port]['val_max'] = jitter_us.max()
    return jitter

def plotManualJittercalcMultiFlow(processing_descriptor, ndn_filter = [], add_name = "", df = {}):
    ''' plot jitter of a flow, both single ports individually and all ports combined in a plot'''
    # check_csvs(processing_descriptor)
    # if len(processing_descriptor.dst_ports) == 0:
    #     return
    topicLong = "Jitter"
    topicShort = "jitter"
    if ndn_filter != [] and add_name != "":
        topicLong = topicLong + " " + add_name
        topicShort = topicShort + "_" + add_name
    if pp.plots_exist(topicShort+processing_descriptor.png_string(), processing_descriptor, topicShort):
        return
    fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

    # jitter already calculated with delay as a part of the query
    # jitter = df
    jitter = df_jitter(processing_descriptor, df)
    
    ports = [[port] for port in processing_descriptor.dst_ports]
    if len(processing_descriptor.dst_ports) > 1:
        ports.append(processing_descriptor.dst_ports)
    maxTSs = {}
    minTSs = {}
    maxHeights = {}
    minHeights = {}
    for experiment in processing_descriptor.experiments:
        minTSs[experiment] = {}
        maxTSs[experiment] = {}
        maxHeights[experiment] = {}
        minHeights[experiment] = {}
        for dst_ports in ports:
            processing_descriptor.dst_ports = dst_ports
            # FIXME - the X axis cannot be limited like this - the stuff was run during differnt times
            maxTSs[experiment]['values'] = []
            minTSs[experiment]['values'] = []
            maxHeights[experiment]['values'] = []
            minHeights[experiment]['values'] = []
            maxTS, minTS = max_min_ts(jitter[experiment], dst_ports)
            maxTSs[experiment]['values'].append(maxTS)
            minTSs[experiment]['values'].append(minTS)
            # print("max, min, limit", maxTS, minTS, (maxTS - minTS) / 1e9)
            fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)
            maxHeight = max([x['val_max'] for x in jitter[experiment].values()], default=0)
            minHeight = max([x['val_min'] for x in jitter[experiment].values()], default=0)
            maxHeights[experiment]['values'].append(maxHeight)
            minHeights[experiment]['values'].append(minHeight)

    for dst_ports in ports:
        processing_descriptor.dst_ports = dst_ports
        fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)
        color = 1
        run = 0
        for experiment in processing_descriptor.experiments:
            for dst_port in processing_descriptor.dst_ports:
                ax.plot((jitter[experiment][dst_port]['ts'] - min(minTSs[experiment]['values'])).div(1e9), jitter[experiment][dst_port]['val'], '.', label='Flow ' + str(dst_port) + "_" +str(run), color=pp.stream_to_color[color])
                color += 1
            run +=1
        # FIXME
        # ax.set_xlim(0,(maxTS-minTS)/1e9)
        ax.set_ylim(minHeight,maxHeight)
        # ax.set_ylim(minHeight*1e6,maxHeight*1e6)
        ax.grid(which='both')
        ax.ticklabel_format(useOffset=False, style='plain')
        plt.legend()
        plt.xlabel('Experiment Time [s]')
        plt.ylabel('Jitter [\u03BCs]')
        plotName = topicShort+processing_descriptor.png_string()
        pp.follow_up(plotName, processing_descriptor, topicShort, fl, startTime, fig)

def df_cdf_jitter(processing_descriptor, df, ndn_filter=[]):
    ''' load csv for plotting CDF of jitter '''
    jitter = {}
    for experiment in processing_descriptor.experiments:
        jitter[experiment] = {}
        for dst_port in processing_descriptor.dst_ports:
            if len(processing_descriptor.experiments) > 1:
                index = processing_descriptor.dst_ports.index(dst_port)
                df = read_database_group(processing_descriptor, processing_descriptor.groups_to_add[index], experiment, "jitter")
                df.at[0, 'jitter'] = 0
                jitter_us = df['jitter'].div(1e3)
            else:
                df[dst_port].at[0, 'jitter'] = 0
                jitter_us = df[dst_port]['jitter'].div(1e3)
            # FIXME
            if ndn_filter != []:
                df = df.loc[df['type'].isin(ndn_filter)]
            # df['jitter_ns'] = df['delay'].diff()
            jitter[experiment][dst_port] = {}
            jitter[experiment][dst_port]['val'] = jitter_us
    return jitter

def plotManualJitterCDFcalcMultiFlow(processing_descriptor, ndn_filter = [], add_name = "", df ={}):
    ''' plot jitter CDF of a flow, both single ports individually and all ports combined in a plot'''
    # check_csvs(processing_descriptor)
    # if len(processing_descriptor.dst_ports) == 0:
    #     return
    topicLong = "Jitter CDF"
    topicShort = "jitterCDF"
    if ndn_filter != [] and add_name != "":
        topicLong = topicLong + " " + add_name
        topicShort = topicShort + "_" + add_name
    if pp.plots_exist(topicShort+processing_descriptor.png_string(), processing_descriptor, topicShort):
        return
    fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

    jitter = df_cdf_jitter(processing_descriptor, df)

    ports = [[port] for port in processing_descriptor.dst_ports]
    if len(processing_descriptor.dst_ports) > 1:
        ports.append(processing_descriptor.dst_ports)

    for dst_ports in ports:
        processing_descriptor.dst_ports = dst_ports
        fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)
        absMax = 0
        color = 1
        run = 0
        for experiment in processing_descriptor.experiments:
            for dst_port in processing_descriptor.dst_ports:
                sorted_data = np.sort(jitter[experiment][dst_port]['val'])
                linspaced = np.linspace(0, 1, len(jitter[experiment][dst_port]['val']), endpoint=True)
                #cutOutliers = 0 # min(1500, int(len(sorted_data)/4))
                absMax = max(absMax, max([abs(x) for x in sorted_data]))
                ax.plot(sorted_data, linspaced, '.-', label='Flow ' + str(dst_port) + "_"  + str(run), color=pp.stream_to_color[color])
                    # ax.plot(jitter[dst_port]['Val'], '.-', label='Flow ' + str(dst_port-1000), zorder=dst_port-980, color=pp.stream_to_color[dst_port%100])

                # ax.set_xlim(0,15)
                color += 1
            run += 1
        ax.set_xlim(-absMax,absMax)
        ax.grid(which='both')
        ax.ticklabel_format(useOffset=False, style='plain')

        plt.legend()
        plt.xlabel('Jitter [\u03BCs]')
        plt.ylabel('CDF')

        plotName = topicShort+processing_descriptor.png_string()
        pp.follow_up(plotName, processing_descriptor, topicShort, fl, startTime, fig)


def df_packet_loss(processing_descriptor, df, ndn_filter=[]):
    ''' load csv for plotting packet loss '''
    packet_loss = {}
    data_to_plot = {}
    for experiment in processing_descriptor.experiments:
        if experiment not in packet_loss.keys():
            packet_loss[experiment] = {}
            data_to_plot[experiment] = []
        for dst_port in processing_descriptor.dst_ports:
            index = processing_descriptor.dst_ports.index(dst_port)
            tmp_df = read_database_packet_loss(processing_descriptor, processing_descriptor.groups_to_add[index], experiment)
            if tmp_df.shape[0] == 0:
                print("no packet loss")
                break
            if ndn_filter != []:
                df = df.loc[df['type'].isin(ndn_filter)]
            data_to_plot[experiment].append(dst_port)
            packet_loss[experiment][dst_port] = {}
            timestamp_loss_ns = tmp_df['timestamp_source'].dropna()
            cumulative_pkt_lost = [x+1 for x in range(len(timestamp_loss_ns))]
            packet_loss[experiment][dst_port]['ts'] = timestamp_loss_ns
            packet_loss[experiment][dst_port]['val'] = cumulative_pkt_lost
            timestamp_ns = tmp_df['timestamp_source']
            packet_loss[experiment][dst_port]['ts_min'] = timestamp_ns.min()
            packet_loss[experiment][dst_port]['ts_max'] = timestamp_ns.max()

    return packet_loss, data_to_plot

def plotManualPacketLosscalcMultiFlow(processing_descriptor, ndn_filter = [], add_name = ""):
    ''' plot packet loss of a flow, both single ports individually and all ports combined in a plot'''
    # check_csvs(processing_descriptor)
    # if len(processing_descriptor.dst_ports) == 0:
    #     return
    topicLong = "Packet Loss"
    topicShort = "cumulativePacketLoss"
    delay_format = processing_descriptor.delay_format
    label_format = processing_descriptor.label_format
    if ndn_filter != [] and add_name != "":
        topicLong = topicLong + " " + add_name
        topicShort = topicShort + "_" + add_name
    if pp.plots_exist(topicShort+processing_descriptor.png_string(), processing_descriptor, topicShort):
        return
    fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)

    packetLoss, data_to_plot = df_packet_loss(processing_descriptor, ndn_filter)

    experiments_to_remove = []
    for experiment in data_to_plot.keys():
        if len(data_to_plot[experiment]) == 0:
            experiments_to_remove.append(experiment)
    print(experiments_to_remove, data_to_plot)
    for experiment_to_remove in experiments_to_remove:
        data_to_plot = data_to_plot.pop(experiment_to_remove)
    if not bool(data_to_plot):
        print("no packet loss", data_to_plot)
        return
    ports = [[port] for port in processing_descriptor.dst_ports]
    if len(processing_descriptor.dst_ports) > 1:
        ports.append(processing_descriptor.dst_ports)

    maxTSs = {}
    minTSs = {}
    print(experiments_to_remove, data_to_plot)
    for experiment in data_to_plot.keys():
        print(experiment)
        minTSs[experiment] = {}
        maxTSs[experiment] = {}
        for dst_port in data_to_plot[experiment]:
            print(dst_port)
            # FIXME - the X axis cannot be limited like this - the stuff was run during different times
            maxTSs[experiment]['values'] = []
            minTSs[experiment]['values'] = []
            maxTS, minTS = max_min_ts(packetLoss[experiment], [dst_port])
            maxTSs[experiment]['values'].append(maxTS)
            minTSs[experiment]['values'].append(minTS)

    for experiment in data_to_plot.keys():
        for dst_port in data_to_plot[experiment]:
            fl, startTime, fig, ax = pp.prepare(topicLong, processing_descriptor)
            color = 1
            run = 0
            for experiment in data_to_plot:
                for dst_port in data_to_plot[experiment]:
                    if label_format == "flow":
                        label = 'Flow ' + str(dst_port) + "_" + str(run)
                    elif label_format == "algorand":
                        label = 'AV Delay' + str(dst_port) + "_" + str(run)
                    else:
                        label = label_format + str(dst_port) + "-" + str(run)
                    ax.plot((packetLoss[experiment][dst_port]['ts'] - - min(minTSs[experiment]['values'])).div(1e9), packetLoss[experiment][dst_port]['val'], 'o-', label=label, color=pp.stream_to_color[color])
                    color += 1
                run += 1
            # ax.set_ylim(0,2e6)
            # ax.set_xlim(0,(maxTS-minTS)/1e9)
            ax.grid(which='both')
            ax.ticklabel_format(useOffset=False, style='plain')

            plt.legend()
            plt.xlabel('Experiment Time [s]')
            plt.ylabel('Cumulative Number of Lost Packets')

            plotName = topicShort+processing_descriptor.png_string()
            pp.follow_up(plotName, processing_descriptor, topicShort, fl, startTime, fig)

def plot_all(processing_descriptor):
    if not processing_descriptor.ndn and len(processing_descriptor.experiments) < 2:
        print("Single experiment plotting")
        df_delay_jitter = plotManualDelaycalcMultiFlow(processing_descriptor)
        plotManualJittercalcMultiFlow(processing_descriptor, df=df_delay_jitter)
        plotManualJitterCDFcalcMultiFlow(processing_descriptor, df=df_delay_jitter)
        plotManualPacketLosscalcMultiFlow(processing_descriptor)
        for dst_port in processing_descriptor.dst_ports:
            index = processing_descriptor.dst_ports.index(dst_port)
            db_name = "delay_jitter_" + str(processing_descriptor.groups_to_add[index]) + "_" + processing_descriptor.experiment
            dq.store_in_database(processing_descriptor.db_path, df_delay_jitter[dst_port], db_name, if_exists='replace')
    elif not processing_descriptor.ndn and len(processing_descriptor.experiments) > 1:
        print("cross experiments setup")
        print(processing_descriptor.experiments)
        plotManualDelaycalcMultiFlow(processing_descriptor)
        plotManualJittercalcMultiFlow(processing_descriptor)
        plotManualJitterCDFcalcMultiFlow(processing_descriptor)
        plotManualPacketLosscalcMultiFlow(processing_descriptor)
    else:
        filters = [([ndn.TypeNumber.DATA, ndn.LpTypeNumber.LP_PACKET], "data"), ([ndn.TypeNumber.INTEREST], "interest")]
        for ndn_filter, add_name in filters:
            df_delay_jitter = plotManualDelaycalcMultiFlow(processing_descriptor, ndn_filter, add_name)
            plotManualJittercalcMultiFlow(processing_descriptor, ndn_filter, add_name)
            plotManualJitterCDFcalcMultiFlow(processing_descriptor, ndn_filter, add_name)
            # plotManualPacketLosscalcMultiFlow(pd, ndn_filter, add_name)

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
