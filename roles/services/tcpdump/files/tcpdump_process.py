import sys
import getopt
import os.path
from pprint import pprint
import math
import ipaddress
import statistics
import csv
import glob
import struct
from scapy.all import *


def write_data_csv_rtt(data, filename):
    with open(str(filename)+'.csv', 'a+', newline='') as csvfile:
        writer = csv.writer(csvfile)
        if len(data) > 1:
            for item in data:
                writer.writerow(item)
        else:
            writer.writerow(data)


def write_data_csv(data, filename):
    with open(str(filename)+'.csv', 'a+', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(data)


def compute_deviation_fix_mean(data, fixed_mean):
    deviation = []
    for item in data:
        square = (item - fixed_mean) ** 2
        deviation.append(square)

    return math.sqrt(statistics.mean(deviation))


def check_arrival_within_window(arrival_times, send_times, window_size, delta_offset, process_num_packets):
    i = 0
    missed_packets = 0
    # offset covers the propagation and processing delay on the wire
    missed_packets_woffset = 0
    on_time_packets = 0
    for packet_stamp in arrival_times[:process_num_packets]:
        # In case the arrival is too late, it means we missed the time windows within which it supposed to arrive
        if abs(packet_stamp - send_times[i]) > window_size:
            # see if with delta it is better or not
            if abs(packet_stamp - send_times[i] - delta_offset) > window_size:
                missed_packets_woffset = missed_packets_woffset + 1
            else:
                missed_packets = missed_packets + 1
        else:
            on_time_packets = on_time_packets + 1
        i = i + 1

    print("Packets for a give stream arrived within window time {}, missed the window {}, missed the window even w/ arrival delay {}.".format(
        on_time_packets, missed_packets, missed_packets_woffset))


def read_pcap(file_path, process_num_packets, define_num_packets=False):
    # Read PCAP with scapy
    if os.path.exists(file_path):
        if define_num_packets is True:
            packets = rdpcap(file_path, process_num_packets)
        else:
            packets = rdpcap(file_path)
    else:
        error('File does not exist')
    return packets


def read_csv_simple(path):
    print(path)
    if os.path.exists(path):
        data = []
        with open(path) as csvfile:
            data = list(csv.reader(csvfile))
        return data
    else:
        error('File ' + path + ' does not exist')


def compute_basic_metrics(packet_stream, process_num_packets, define_num_packets=False, tai_format=False):
    TAI_OFFSET = 37000000000
    # Read epoch from packet
    arrival_tstamp = []
    # Read from packet payload
    send_tstamp = []
    # Compute delta of arrival (Rj-Ri)
    arrival_delta = []
    # Compute delta of send (Sj-Si)
    send_delta = []
    # jitter -  (Rj-Ri) - (Sj-Si)
    jitter = []
    # Latency Ri - Si
    latency = []
    i = 0
    if define_num_packets is False:
        process_num_packets = len(packet_stream)

    for frame in packet_stream[:process_num_packets]:
        arrival_tstamp.append(int(str(frame.time).replace('.', '')))
        # Extraction of info from payload
        tmp = frame['Raw'].load[:8]
        tmp = bytearray(tmp)
        txtime = struct.unpack('<Q', tmp)[0]

        if tai_format is True:
            send_tstamp.append(txtime + TAI_OFFSET)
        else:
            send_tstamp.append(txtime)
        if i >= 1:
            # Compute Rj - Ri
            tmp_arrival_delta = float(arrival_tstamp[i] - arrival_tstamp[i-1])
            arrival_delta.append(tmp_arrival_delta)
            # Compute Sj - Sj
            tmp_send_delta = float(send_tstamp[i] - send_tstamp[i-1])
            send_delta.append(tmp_send_delta)
            # Compute jitter (Rj-Ri) - (Sj - Si)
            jitter.append(tmp_arrival_delta - tmp_send_delta)
            # Latency
            latency.append(arrival_tstamp[i] - send_tstamp[i])
        i = i + 1

    return arrival_tstamp, send_tstamp, arrival_delta, send_delta, jitter, latency


def process_etf(file_path, write_to_csv, name):
    packets = read_pcap(
        file_path, process_num_packets, define_num_packets)
    arrival_tstamp, send_tstamp, arrival_delta, send_delta, jitter, latency = compute_basic_metrics(
        packets, process_num_packets, define_num_packets, tai_format)
    # The jitter caused by traffic fluctuations tend to cancel out, for if
    # a packet is late, and produces positive jitter, the next packet will be early in relation to it, and
    # produce negative jitter.

    jitter_stddev = statistics.stdev(jitter)
    latency_stddev = statistics.stdev(latency)
    # Compute standard deviation sigma w/ fixed mean

    sigma_standard_deviation = compute_deviation_fix_mean(
        arrival_delta, expected_mean)

    print("min of jitter:%e" % min(jitter))
    print("max of jitter:%e" % max(jitter))
    print("jitter (pk-pk):%e" % (jitter_stddev))
    print("jitter min_max difference (pk-pk):%e" %
          float(max(jitter) - min(jitter)))
    # print("avg of difference:\n%e" % statistics.mean(arrival_delta))
    print("std dev of difference using Expected Mean:%e" %
          sigma_standard_deviation)
    print("std dev of difference using difference Mean:%e" %
          statistics.stdev(arrival_delta))
    print("min of arrival_delta:%e" % min(arrival_delta))
    print("max of arrival_delta:%e" % max(arrival_delta))
    print("count number of packets:%d" % len(packets))
    print("min of latency:%e" % min(latency))
    print("max of latency:%e" % max(latency))
    print("Latency stdev:%e" % (latency_stddev))
    # TODO update where data stored ->
    if write_to_csv is True:
        store_to_file(file_path, arrival_tstamp, send_tstamp, arrival_delta,
                      send_delta, jitter, jitter_stddev, sigma_standard_deviation, len(packets), latency, latency_stddev, comment=name)


def store_to_file(file_path, arrival_tstamp, send_tstamp, arrival_delta, send_delta, jitter, jitter_stddev, sigma_standard_deviation, len_packets, latency=[], latency_stddev=0, comment=""):
    file_name = file_path.split('/')[-1].split('.')[0]
    file_name = file_name + comment
    write_data_csv(["params", "jitter", "arrival_tstamp",
                    "arrival_delta", "send_tstamp", "send_delta", " latency"], file_name)

    write_data_csv([min(jitter), max(jitter), jitter_stddev, float(max(jitter) - min(jitter)),
                    sigma_standard_deviation, statistics.stdev(arrival_delta), len_packets, latency_stddev], file_name)
    write_data_csv(jitter, file_name)
    write_data_csv(arrival_tstamp, file_name)
    write_data_csv(arrival_delta, file_name)
    write_data_csv(send_tstamp, file_name)
    write_data_csv(send_delta, file_name)
    write_data_csv(latency, file_name)


def help():
    print("(C) 2020, IVNRI sink capture")
    print("")
    print("Options: ")
    print("   -h              this help")
    print("   -s [string]     provide path to a file")
    print("   -w              write data to csv")
    print("   -m [int]        provide expected mean")
    print(
        "   -p [int]        process specific num of packets (if empty, process all)")
    print(
        "   -t [string]     specify test scenario - [etf, cbs, taprio, best_effort, rtt]")
    print("   -o              flag to count with TAI format of send packets")
    print("   -W [int]        specify window size for a given stream")
    print(
        "   -d [int]        specify estimated arrival delay (given in ns, default is 100)")
    print("   -D [path]       specify directory path for given test")
    print("   -n [name]       specify name of RTT file to be stored")
    print("   -h [int]        specify a number of hops you evalauted")
    print("Example:\n")
    print("python3 main.py -s data/pcap/etf_HW.pcap -w -m 1000000 -p 100")
    print("python3 main.py -s taprio-stream-2.pcap -w -t taprio -W 300000 -d 100")
    print("python3 main.py -D data/csv/packet_log_rtt_2_nodes_ovs/ -t rtt -w -n rtt_test")


def error(str_error):
    print("ERROR:", str_error)
    sys.exit(-1)


def main():
    some_option = True  # For now
    file_path = ""
    write_to_csv = ""
    expected_mean = 1000000
    process_num_packets = 0
    define_num_packets = False
    test_scenario = "etf"
    tai_format = False
    window_size = 0
    delta_offset = 100
    directory = "/srv/testbed/vehiclenet/experiments/2020-12-11D-22:34:47T_basic-rtt"
    rtt_filename = "RTT_values"
    num_hops = 2
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hs:wm:p:t:oW:d:D:n:h:")
    except getopt.GetoptError as err:
        error("-h for help")

    for o, a in opts:
        if o == "-h":
            help()
            some_option = True
        if o == "-s":
            file_path = a
            some_option = True
        if o == "-w":
            write_to_csv = True
        if o == "-m":
            expected_mean = float(a)
        if o == "-p":
            process_num_packets = int(a)
            define_num_packets = True
        if o == "-t":
            test_scenario = str(a)
        if o == "-o":
            tai_format = True
        if o == "-D":
            directory = str(a)
        if o == "-W":
            window_size = int(a)
        if o == "-d":
            delta_offset = int(a)
        if o == "-n":
            rtt_filename = str(a)
        if o == "-h":
            num_hops = int(a)

    if not some_option:
        print("Please provide some option!")
        print(" -h for help")
        sys.exit(0)

    # In case timestamp not in TAI format we have to take into account - currently both times in same forma
    # Scenario I - ETF
    if test_scenario == "etf":
        # ETF group
        print("Test etf")
        # Currently only focus on ETF values, but already reading all

        # handling single file
        if len(file_path) > 1:
            process_etf(file_path, write_to_csv, file_path)

        # Handling directory
        else:
            # Look for rtt_client_recv
            pattern = "tcpdump_etf_*"
            files = []
            # returns three fields; dirpath, dirnames, filenames
            for dirpath, dirnames, filenames in os.walk(directory):
                files.extend(glob(os.path.join(dirpath, pattern)))

            print("Files path", files, len(files))

            # Read PCAP with scapy
            for file_path in files:
                name = file_path.split("/")[-1]
                process_etf(file_path, write_to_csv, name)
    
    elif test_scenario == "cbs":
        print('Test scenario CBS')

    elif test_scenario == "taprio":
        if window_size == 0:
            error("Window size cant be 0")
        print('Test scenario taprio')

        packets = read_pcap(file_path, process_num_packets, define_num_packets)

        if define_num_packets is False:
            process_num_packets = len(packets)
        arrival_tstamp, send_tstamp, arrival_delta, send_delta, jitter = compute_basic_metrics(
            packets, process_num_packets, define_num_packets, tai_format)

        # Check how many hit the window or missed it
        # base_time_tick = 1000000 # 1ms
        check_arrival_within_window(
            arrival_tstamp, send_tstamp, window_size, delta_offset, process_num_packets)

        jitter_stddev = statistics.stdev(jitter)

        # Compute standard deviation sigma w/ fixed mean

        sigma_standard_deviation = compute_deviation_fix_mean(
            arrival_delta, expected_mean)

        print("min of jitter:%e" % min(jitter))
        print("max of jitter:%e" % max(jitter))
        print("jitter (pk-pk):%e" % (jitter_stddev))
        print("jitter min_max difference (pk-pk):%e" %
              float(max(jitter) - min(jitter)))
        # print("avg of difference:\n%e" % statistics.mean(arrival_delta))
        print("std dev of difference using Expected Mean:%e" %
              sigma_standard_deviation)
        print("std dev of difference using difference Mean:%e" %
              statistics.stdev(arrival_delta))
        print("min of arrival_delta:%e" % min(arrival_delta))
        print("max of arrival_delta:%e" % max(arrival_delta))
        print("count number of packets:%d" % len(packets))
        if write_to_csv is True:
            store_to_file(file_path, arrival_tstamp, send_tstamp, arrival_delta,
                          send_delta, jitter, jitter_stddev, sigma_standard_deviation, len(packets))

    elif test_scenario == "best_effort":
        print("Test best effort")
        # Read epoch from packet
        arrival_tstamp = []
        # Compute delta of arrival (Rj-Ri)
        arrival_delta = []
        i = 0
        if define_num_packets is False:
            process_num_packets = len(packets)

        for frame in packets[:process_num_packets]:
            arrival_tstamp.append(int(str(frame.time).replace('.', '')))
            # Extraction of info from payload

            if i >= 1:
                # Compute Rj - Ri
                tmp_arrival_delta = float(
                    arrival_tstamp[i] - arrival_tstamp[i-1])
                arrival_delta.append(tmp_arrival_delta)
            i = i + 1

        # The jitter caused by traffic fluctuations tend to cancel out, for if
        # a packet is late, and produces positive jitter, the next packet will be early in relation to it, and
        # produce negative jitter.

        print("std dev of difference using difference Mean:%e" %
              statistics.stdev(arrival_delta))
        print("min of arrival_delta:%e" % min(arrival_delta))
        print("max of arrival_delta:%e" % max(arrival_delta))
        print("count number of packets:%d" % len(packets))

        if write_to_csv is True:
            file_name = file_path.split('/')[-1].split('.')[0]
            write_data_csv(["params", "arrival_tstamp",
                            "arrival_delta"], file_name)
            write_data_csv(
                [statistics.stdev(arrival_delta), len(packets)], file_name)
            write_data_csv(arrival_tstamp, file_name)
            write_data_csv(arrival_delta, file_name)

    elif test_scenario == "rtt":
        print("Test rtt")
        # Currently only focus on RTT values, but already reading all
        files = []
        # Look for rtt_client_recv
        pattern = "rtt_client_recv_*"

        # returns three fields; dirpath, dirnames, filenames
        for dirpath, dirnames, filenames in os.walk(directory):
            files.extend(glob(os.path.join(dirpath, pattern)))
        print("Files path", files)

        # Need to organize by hops
        # Start to read after the 10th line, avoids messy values
        start = 1
        for i in range(0, num_hops + 1):
            condition = str(i)+"-hop"
            file_name = "rtt_all_experiments_" + condition
            for item in files:
                if condition in item:
                    data = read_csv_simple(item)
                    experiment_name = [
                        "rtt_" + str(item.split("/")[-3].split("_")[-1].replace("-", "_"))]
                    num_packets = int(data[0][-1].split(":")[1])
                    # RTT_values = [data[num_packets + 2],data[num_packets + 4]]
                    print(experiment_name)
                    write_data_csv_rtt(experiment_name, file_name)
                    write_data_csv_rtt(data[num_packets + 2], file_name)
                    write_data_csv_rtt(data[num_packets + 4], file_name)
                    write_data_csv_rtt(data[start:num_packets], file_name)
    else:
        print('test scenario does not exist')


if __name__ == '__main__':
    main()
