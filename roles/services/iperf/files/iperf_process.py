#!/usr/bin/python3

# Post-process iperf3 log file
# Confert log file into csv format and create two graphs

import json
import sys
import argparse

# add custom script path and import scripts
sys.path.append("/root/scripts")
import gnu_graph

def parse_cli(args):
    """Parse command line arguments """
    parser = argparse.ArgumentParser(prog='iperf_process',
                description='Convert iperf log file to csv and create graphs')
    parser.add_argument('-l', '--logfile',
                        help='Path to the iperf log file')

    return parser.parse_args(args)

def process_iperf(logfile, outfile):
    """ Process iperf logs and create data log
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
        stamp = start_time + float(stream['sum']['end'])   # add base timestamp with duration
        vas = stream['sum']                                # stream values
        # index, timestamp, Mbit/s, packets, lost_packets, lost_percent, jitter_ms
        f.write("%s, %s, %s, %s, %s, %s, %s\n" % (str(index), str(stamp), str(mbits),
            str(vas['packets']), str(vas['lost_packets']),
            str(vas['lost_percent']), str(vas['jitter_ms'])))
    f. close()

    return True

# ---------------- START MAIN ---------------------

parser_args = parse_cli(sys.argv[1:])
infile  = parser_args.logfile
csvfile = infile.replace(".log", ".csv")

# convert log file into csv format
process_iperf(infile, csvfile)

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
