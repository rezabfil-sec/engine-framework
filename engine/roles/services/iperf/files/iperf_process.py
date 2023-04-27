#!/usr/bin/python3

# Post-process iperf3 log file
# Confert log file into csv format and create two graphs

import json
import sys
import argparse

import pandas as pd

# add custom script path and import scripts
sys.path.append("/root/scripts")
import gnu_graph

def parse_cli(args):
    """ Parse command line arguments """
    parser = argparse.ArgumentParser(prog='iperf_process', description='Convert iperf log file to csv and create graphs')
    parser.add_argument('-l', '--logfile', help='Path to the iperf log file')
    parser.add_argument('-f', '--file', help='File name base (simulation)')
    return parser.parse_args(args)

def process_iperf(logfile, outfile):
    """
        Process iperf logs and create data log
        Write one data log file for every iperf file
    """
    role = logfile.split("/")[-1].split("_")[1]
    if role != "server":
        print("ERROR: only process server log files")
        return False

    try:
        with open(logfile, "r") as f:
            iperf = json.load(f)
    except Exception as err:
        msg = 'Json error [%s]!\n' % logfile
        msg += '\tError: {0}'.format(err)
        print(msg)
        return False

    if iperf['start'].get('timestamp', None) == None:
        print("ERROR: no start timestamp")
        return False

    start_time = float(iperf['start']['timestamp']['timesecs'])
    index = 0

    # extract values from iperf log
    f = open(outfile, "w")
    f.write("# index, timestamp, mbit/s, packets, lost_packets, lost_percent, jitter_ms\n")
    for stream in iperf['intervals']:
        index += 1
        mbits = float(stream['sum']['bits_per_second']) / 1000000  # convert to Mbit/s
        stamp = float(stream['sum']['end']) # + start_time # add base timestamp with duration
        vas = stream['sum']                                # stream values
        # index, timestamp, Mbit/s, packets, lost_packets, lost_percent, jitter_ms
        f.write("%s, %s, %s, %s, %s, %s, %s\n" % (str(index), str(stamp), str(mbits),
            str(vas['packets']), str(vas['lost_packets']),
            str(vas['lost_percent']), str(vas['jitter_ms'])))
    f. close()

    return True

def process_iperf_sim(file_name_base, packets_per_second=10000):
    """
        Processes simulation statistics, writes a csv file containing iperf3 like statistics with the same columns as process_iperf


        Expects statistics as recorded by PassivePacketSinkBase (extended by PassivePacketSink which is used to realize the iperf3 like servers).
        Expects different statistics in individual csv files as exported by 'opp_scavetool -F CSV-S [...]', to be named with the given file name base, containing the respective statistics:
         - <file_name_base>_sink-dataRate:vector.csv
         - <file_name_base>_sink-packetJitter:vector.csv
         - <file_name_base>_sink-packetJitter:vector(count).csv

        In contrast to the results for iperf3, which are periodically logged with the interval being configurable via command line option,
        the *packetJitter* statistics are recorded on a per packet granularity, while the *dataRate* statistic seems to be logged after a certain number of packets or a maximum interval is reached.
        For the latter, the number of packets seems to be the limiting factor after the warm up period. Thus relevant timestamps in *dataRate* will match those in *packetJitter* and the *dataRate* timestamps* are chosen as timestamps for the output file.
    """
    # set file names
    data_rate_file = file_name_base + "_sink-dataRate:vector.csv" # throughput (per interval / packet batch)
    jitter_file = file_name_base + "_sink-packetJitter:vector.csv" # jitter (per packet)
    count_file = file_name_base + "_sink-packetJitter:vector(count).csv" # total number of packets received (per packet)
    outfile = file_name_base + ".csv"

    # read csvs, ignore first line, name columns
    data_rate_df = pd.read_csv(data_rate_file, skiprows=1, header=None, names=['timestamp', 'value'])
    jitter_df = pd.read_csv(jitter_file, skiprows=1, header=None, names=['timestamp', 'value'])
    count_df = pd.read_csv(count_file, skiprows=1, header=None, names=['timestamp', 'value'])

    f = open(outfile, "w")
    f.write("# index, timestamp, mbit/s, packets, lost_packets, lost_percent, jitter_ms\n")

    # initialize variable to be used in loop
    total_packets_old = 0 # total number of packets received from previous interval
    lost_total_packets_old = 0 # total number of lost packets (estimated) from previous interval
    jitter_ms = 0 # smoothed mean jitter from previous interval

    timestamp_old = 0 # interval start, interval end from previous interval
    timestamp_new = 0 # interval end
    # loop over dataRate rows, accumulate jitter and packets for respective interval
    for data_rate_index, data_rate_row in data_rate_df.iterrows():
        timestamp_old = timestamp_new
        timestamp_new = data_rate_row['timestamp']
        # ignore warmup_period # TODO: replace hardcoded value
        if timestamp_old < 5:
            continue

        jitter_temp_df = jitter_df.loc[(jitter_df['timestamp'] > timestamp_old) & (jitter_df['timestamp'] <= timestamp_new)]
        count_temp_df = count_df.loc[(count_df['timestamp'] > timestamp_old) & (count_df['timestamp'] <= timestamp_new)]

        stamp = timestamp_new # interval end
        mbits = data_rate_row['value'] / 1000000 # convert to Mbit/s

        total_packets_new = count_temp_df.max()['value'] # total number of received packets
        packets = int(total_packets_new - total_packets_old) # received packets in current interval

        # currently dropped packets aren't recordable via the modules used
        # (TODO: implement based on sequence number)
        # a workaround is used where the expected number of sent packets per second can be provided
        # which will then be used to roughly estimate the loss by calculating the difference with actually received packets per interval
        expected_total_packets = (timestamp_new - 5) * packets_per_second # expected total number of packets
        lost_total_packets_new = int(expected_total_packets - total_packets_new) # total number of lost packets (estimated)
        lost_packets = lost_total_packets_new - lost_total_packets_old # number of lost packets in current interval (estimated)
        lost_packets_percent = (lost_packets / ((timestamp_new - timestamp_old) * packets_per_second)) * 100 # percentage of lost packets in current interval (estimated)
        lost_total_packets_old = lost_total_packets_new # value from previous interval

        total_packets_old = total_packets_new # value from previous interval

        # jitter field in the iPerf3 logs is a smoothed mean, calculation is based on a RFC:
        # "Jitter calculations are continuously computed by the server, as specified by RTP in RFC 1889." [https://iperf.fr/iperf-doc.php]
        # algorithm in RFC1889 calculates jitter (using the that clock differences eventually cancel out), takes the absoulte value and then applies some kind of smoothing:
        # "s->jitter += (1./16.) * ((double)d - s->jitter);" [https://www.rfc-editor.org/rfc/rfc1889#appendix-A.8] where d is the current jitter, absolute value, and s->jitter is the smoothed mean.
        for jitter_index, jitter_row in jitter_temp_df.mul(1000).abs().iterrows():  # have signed value in seconds, get milliseconds, get abs
            jitter_ms += (jitter_row['value'] - jitter_ms) / 16
        # jitter_ms = jitter_temp_df.mul(1000).abs().mean()['value']

        # index, timestamp, Mbit/s, packets, lost_packets, lost_percent, jitter_ms
        f.write("%s, %s, %s, %s, %s, %s, %s\n" % (str(data_rate_index), str(stamp), str(mbits), str(packets), str(lost_packets), "{:.6f}".format(lost_packets_percent), "{:.15f}".format(jitter_ms)))
    f. close()

# ---------------- START MAIN ---------------------

def main():
    parser_args = parse_cli(sys.argv[1:])

    if parser_args.logfile:
        infile  = parser_args.logfile
        csvfile = infile.replace(".log", ".csv")
        # convert log file into csv format
        process_iperf(infile, csvfile)
    elif parser_args.file:
        file_name_base = parser_args.file
        process_iperf_sim(file_name_base)
        csvfile = file_name_base + '.csv'
    else:
        exit()

    # create graph : throughput + packets
    parameters_packets = {
        "x": "rx Timestamps [s]", "y1": "Throughput [mbit/s]", "y2": "Packets [num]", "vars":
        [{'file': csvfile, 'title': 'throughput', 'values': '2:3', 'axes': 'x1y1', 'style': '1' },
        {'file': csvfile, 'title': 'sent-packets', 'values': '2:4', 'axes': 'x1y2', 'style': '2' },
        {'file': csvfile, 'title': 'lost-packets', 'values': '2:5', 'axes': 'x1y2', 'style': '3' }]
    }
    artefacts_packet = gnu_graph.create(csvfile.replace(".csv", "_packet.png"), "iperf - graph - packet", parameters_packets)

    # create graph : throughput + jitter
    parameters_jitter = {
        "x": "rx Timestamps [s]", "y1": "Throughput [mbit/s]", "y2": "Jitter [ms]", "vars":
        [{'file': csvfile, 'title': 'throughput', 'values': '2:3', 'axes': 'x1y1', 'style': '1' },
        {'file': csvfile, 'title': 'jitter', 'values': '2:7', 'axes': 'x1y2', 'style': '2' }]
    }
    artefacts_jitter = gnu_graph.create(csvfile.replace(".csv", "_jitter.png"), "iperf - graph - jitter", parameters_jitter)

    # hand the generated files to ansible for collection
    print([csvfile] + artefacts_packet + artefacts_jitter)

if __name__ == "__main__":
    main()
