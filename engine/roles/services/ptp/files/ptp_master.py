#!/usr/bin/python3
# This files is meant to check followinng:
# One time:
# PTP runs - e.g. ptp4l, phc2sys setup - OK!
# Check clocks done well - OK!
# PTP configuration by using PMC get messages - OK
# From syslog find which interface is chosen as a master/slave
# Helps define PTP topology
# Continiou:
# PTP runs properly - check tail -f /var/log/syslog - OK
# PTP statitistics - ok
# PTP phc2sys modify statistics
# More TODO
# Identify interfaces my their clock ID - add new field to the variables
# Possibly central node defines later on the PTP topology

import subprocess
import psutil
import os
import sys
import time
import os.path
import getopt
import threading
import csv
import math
import statistics


def check_running(process_name):
    if process_name in (p.name() for p in psutil.process_iter()):
        print('{process_name} is running'.format(process_name=process_name))


def check_clocks(interfaces):
    for interface in interfaces:
        command = './check_clocks -d {interface} -v'.format(
            interface=interface)
        process = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
        output, error = process.communicate()
        if ":)" in str(output):
            print("Clocks synchronized")
        print(output.decode("utf-8"))


def compute_avg(data):
    data_len = len(data)
    return sum(data) / data_len


def continious_read_log(file_name, sleep):
    log_file = open(file_name, "r")
    log_file.seek(0, os.SEEK_END)
    while True:
        line = log_file.readline()
        if not line:
            time.sleep(sleep)
            continue
        yield line


def read_log(file_name, sleep):
    time.sleep(sleep)
    log_file = open(file_name, "r")
    log_file.seek(0, os.SEEK_END)
    while True:
        line = log_file.readline()
        if not line:
            time.sleep(sleep)
            continue
        yield line


#['Dec', '3', '15:39:35', 'bart', 'phc2sys:', '[186865.395]', '/dev/ptp0', 'sys', 'offset', '-9', 's2', 'freq', '-82', 'delay', '2102']
#['Dec', '3', '16:17:00', 'otto', 'ptp4l:', '[189168.926]', 'rms', '18', 'max', 24, 'freq', '-11684', '+/-' ,  '9', 'delay', '-18', '+/-','0']


def store_to_csv(file_name, data, analysis=False):
    # print(data)
    with open(str(file_name)+'.csv', 'a+') as datafile:
        datafile.write(str(data))
        if analysis is True:
            datafile.write("avg")
            datafile.write(compute_avg(data))
            datafile.write("stdev")
            datafile.write(statistics.stdev(data))


def read_logs(lines):
    # should be known through ansible
    #given_interfaces = ["enp3s0", "enp4s0"]
    given_interfaces = ["enp8s0", "enp9s0",
                        "enp10s0", "enp11s0", "eno1", "eno2"]
    num_interfaces = 6

    # extract from lines
    interfaces = {}
    rms = []
    value = 0
    for interface in given_interfaces:
        interfaces[interface] = list([0])
    # Go through each line in a log file, stay here forever unless break
    for line in lines:
        # print(type(line))
        value = value + 1
        line_split = line.split()
        # On master is no ptp4l, only phc2sys
        # Look for phc2sys in line an extract info for a given interface
        if str(line_split[4]) == "phc2sys:" and str(line_split[6]) in given_interfaces:
            print("phc2sys of interface", line_split[6])
            offset_phc2sys = line_split[9]
            interfaces[line_split[6]].append(int(offset_phc2sys))
            print("interface values", line_split[6], interfaces[line_split[6]])
            # Check status
            if int(offset_phc2sys) > abs(150):
                print("Offset value increased to: ", offset_phc2sys)
                store_to_csv("offset_phc2sys", line)
                # Taking last 10% of data
                data_len = math.ceil(len(interfaces[line_split[6]])*0.8)
                avg = compute_avg(interfaces[line_split[6]][-data_len:])
                if avg > 300:
                    print("Avg too high", avg)
                    # Before closing
                    for item in interfaces.keys():
                        store_to_csv("offset_phc2sys", interfaces[item], True)
                    store_to_csv("rms_ptp4l", rms, True)
                    return "Too large offset"
        # ptp4l
        elif str(line_split[4]) == "ptp4l:":
            print("ptp4l")
            if "rms" == line_split[6]:
                offset_ptp4l = line_split[7]
                rms.append(int(offset_ptp4l))
                if int(offset_ptp4l) > abs(150):
                    print("Offset value increased to: ", offset_ptp4l)
                    store_to_csv("rms_ptp4l", line)
                    avg = compute_avg(rms)
                    if avg > 250:
                        for item in interfaces.keys():
                            store_to_csv("offset_phc2sys",
                                         interfaces[item], True)
                        store_to_csv("rms_ptp4l", rms, True)
                        print("Avg too high", avg)
                        return "Too large offset"


def read_logs_once(lines, given_interfaces, num_interfaces):
    #given_interfaces = []
    #{% for item in node_ifaces | dict2items %}
    #given_interfaces.append("{{ item.value.name}} ")
    #{ % endfor % }
    #given_interfaces = ["enp8s0", "enp9s0", "enp10s0", "enp11s0", "eno1", "eno2"]
    #num_interfaces = {{ num_interfaces }}

    # Extract from lines
    interfaces = []
    value = 0
    # Go through each line in a log file, stay here forever unless break
    for line in lines:
        # print(type(line))
        value = value + 1
        line_split = line.split()
        # On master is no ptp4l, only phc2sys
        # If single iface and node is master nothing to be found in logs
        if num_interfaces == 1:
            print("Single iface and node is GM")
            phc = "/dev/ptp{}".format(execute_cmd("ethtool -T {} | grep PTP".format(given_interfaces[0])).split(":")[1].replace(" ", "").replace("\n",""))
            print("Given interface {} is a local master, with given phc {}".format(given_interfaces[0], phc))
            return [given_interfaces, phc]  
        # Look for phc2sys in line an extract info for a given interface
        current_iface = str(line_split[6])
        if str(line_split[4]) == "phc2sys:" and "en" in current_iface:
            print("phc2sys of interface", current_iface)
            if current_iface not in interfaces:
                interfaces.append(current_iface)
            if len(interfaces) >= (num_interfaces - 1):
                print("All interfaces found")
                for interface in given_interfaces:
                    if interface not in interfaces:
                        print(interface)
                        phc = "/dev/ptp{}".format(execute_cmd(
                            "ethtool -T {} | grep PTP".format(interface)).split(":")[1].replace(" ", "").replace("\n",""))
                        print(
                            "Given interface {} is a local master, with given phc {}".format(interface, phc))
                        return [interface, phc]


def execute_cmd(command):
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    output, error = process.communicate()
    return output.decode('utf-8')

# Find group local master
def search_local_master(log_path, num_ifaces):
    # pmc returns a number of responses within 1 hop, as long as other devices chose themselves as GM, we wait
    # Takes around 60s for network to stabilize
    counter = 2
    # Just in case verify it is like that multiple times - PTP sometimes resets
    repeats = 0
    while counter > 1:
      time.sleep(5)
      # in case ptp not running on other machines, this will return empty field and condition than holds
      counter = 0
      cmd = 'pmc -u -b 1 -t 1 "GET CURRENT_DATA_SET"'
      response = execute_cmd(cmd)
      response = response.split('\n')
      for line in response:
          if "offsetFromMaster" in line:
             offsetValue = int(line.split(" ")[1].split(".")[0])
             if offsetValue == 0 or abs(offsetValue) > 150:
                counter = counter + 1
      # We want to achieve the same results few times in a row
      # pmc response is equal to # interfaces locally and num_ifaces
      if counter <= 1 and repeats < 3:
         print("This is run {}".format(repeats))
         counter = 2
         repeats = repeats + 1
    # After making sure the PTP is stable, we proceed with the choice of GM interface
    # Calls PMC get requests
    cmd = 'pmc -u -b 0 -t 1 "GET PARENT_DATA_SET"'
    response = execute_cmd(cmd)
    response = response.split('\n')

    # Returns MAC of device it is connected to
    master_interface = response[2].split()[1]
    grand_master = response[11].split()[1]

    print("Master interface locally is\n  {}\nGrand Master is \n  {}".format(
        master_interface, grand_master))
    if master_interface.split('-')[0] == grand_master and master_interface.split('-')[1] == '0':
        print("This node is the GM")
        return "GM found"
    else:
        print("This node is not the GM")
        return 0


def help():
    print("(C) 2020, IVNRI PTP analysis tool")
    print("")
    print("Options: ")
    print("   -h              this help")
    print("   -m              find a master node")
    print("   -n              number of interfaces")
    print("   -i              list of interfaces")

    print("Example:\n")
    print("python ptp_master -m")


def error(str_error):
    print("ERROR:", str_error)
    sys.exit(-1)


def main():
    print("Starting program")
    some_option = False
    find_master = False
    log_path = "/var/log/syslog"
    given_interfaces = ["enp3s0", "enp4s0"]
    used_ifaces = ["1","3"]
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hmn:i:")
    except getopt.GetoptError as err:
        error("-h for help")

    for o, a in opts:
        if o == "-h":
            help()
            some_option = True
        if o == "-m":
            find_master = True
            some_option = True
        if o == "-n":
            used_ifaces = str(a).split(",")
        if o == "-i":
            given_interfaces = str(a).split(",")

    num_interfaces = len(used_ifaces)
    if not some_option:
        print("Please provide some option!")
        print(" -h for help")
        sys.exit(0)
    if find_master:
        given_interfaces = given_interfaces[:num_interfaces]
        print(given_interfaces)
        gm_found = search_local_master(log_path, num_interfaces)
        if gm_found == "GM found":
           loglines = read_log(log_path, 5)
           values = read_logs_once(loglines, given_interfaces, num_interfaces)
           time.sleep(10)
           print(values[1])
           return values[1]
        else:
           return "1"

if __name__ == '__main__':
    main()