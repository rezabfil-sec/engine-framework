#!/usr/bin/env python3

''' Handles result processing information: result folder, experiment, node, interface and co to which result processing should be applied, with cli '''

import argparse
import glob
import sys

class ProcessingDescriptor:
    def __init__(self, folder, experiment, node, iface, sim, dst_ports=[], qdisc_types=['mqprio','taprio','be','cbs','etf'], warmup=0, info=None):
        """
            Store information about what and how to parse or plot

            Simplifies retrieval of the concrete artefacts that the parsing or plotting functions will use, together with additional (optional) parameters specifying what and how to plot or parse.

            Parameters
            ----------
            warmup : int
                time in ns, for plotting scripts: initial time to exclude from plots
            info: dict
                info to be used for plotting (dict mapping port to config of (source) service instance)
        """
        self.folder = folder
        self.experiment = experiment
        self.node = node
        self.iface = iface
        self.sim = sim
        self.dst_ports = dst_ports
        self.qdisc_types = qdisc_types
        self.warmup = warmup
        self.info = info

    def print_info(self, ports=False):
        print('Evaluating experiment', self.experiment, 'on', self.node, 'and interface', self.iface + (('for UDP Iperf flows with target ports ' + str(self.dst_ports)) if ports else ""))

    def log_file(self):
        return self.folder + '/pythonLog.txt'

    def node_num(self):
        return self.node.split('-')[1]

    def node_path(self):
        return self.folder + '/' + self.experiment + '/' + self.node + '/'

    def pre_path(self):
        return self.folder + '/*' + self.experiment + '/' + self.node + '*/'

    def png_string(self):
        return '_e-' + self.experiment + '_d-' + self.node + '_i-' + self.iface + '_p-' + str(self.dst_ports) + '.png'

    def find_file_name(self, name, single=True):
        pre_path = self.pre_path() + name
        file_name = glob.glob(pre_path)
        if single:
            return file_name[0]
        else:
            return file_name

    def service_name(self, port):
        return self.info[port]['name']

def add_arguments(parser):
    parser.add_argument('-f', '--folder', required=True, help='Folder with scenario results')
    parser.add_argument('-e', '--experiment', required=True, help='The name of the experiment that matches the one from 04-experiments.yml')
    parser.add_argument('-n', '--node', '--node_end', required=True, help='A single node identifier in format \'node-6\' of the (stream end) node from which to get the data')
    parser.add_argument('-i', '--iface', '--iface_end', required=True, help='The (stream end) interface for which to parse the data')
    parser.add_argument('-s', '--sim', action='store_true', help='Do simulation specific processing.')
    parser.add_argument('-w', '--warmup', type=int, default=0, help='Initial time (ns) to exclude from plots')

# relevant for *iperf*
def add_arguments_iperf(parser):
    parser.add_argument('-d', '--dst_ports', nargs='*', default=[], type=int, help='List of iperf destination ports. We are only interested in the traffic from sender to receiver at the moment.')

# relevant for plot_QM
def add_arguments_qm(parser):
    parser.add_argument('-q', '--qdisc_types', nargs='*', default=["mqprio","taprio","be","cbs","etf"], help='List of qdisc types to plot')

# relevant for csv_parser_iperf_flows
def add_arguments_start(parser):
    parser.add_argument('--node_start', default="", help='A single node identifier in format \'node-6\' of the node where iperf flow originates')
    parser.add_argument('--iface_start', default="", help='The interface for the node where iperf flow originates')

def parse_cli(prog, description, args):
    """ Parse command line arguments """
    parser = argparse.ArgumentParser(prog=prog, description=description)
    add_arguments(parser)
    add_arguments_start(parser)
    add_arguments_iperf(parser)
    add_arguments_qm(parser)
    return parser.parse_args(args)

def create_processing_descriptor_cli(prog, description):
    parser_args = parse_cli(prog, description, sys.argv[1:])
    streams_end = ProcessingDescriptor(parser_args.folder, parser_args.experiment, parser_args.node, parser_args.iface, parser_args.sim, parser_args.dst_ports, qdisc_types=parser_args.qdisc_types, warmup=parser_args.warmup)
    return streams_end

def create_processing_descriptors_cli(prog, description):
    parser_args = parse_cli(prog, description, sys.argv[1:])
    streams_end = ProcessingDescriptor(parser_args.folder, parser_args.experiment, parser_args.node, parser_args.iface, parser_args.sim, parser_args.dst_ports, qdisc_types=parser_args.qdisc_types, warmup=parser_args.warmup)
    streams_start = ProcessingDescriptor(parser_args.folder, parser_args.experiment, parser_args.node_start, parser_args.iface_start, parser_args.sim, parser_args.dst_ports, qdisc_types=parser_args.qdisc_types, warmup=parser_args.warmup)
    return streams_end, streams_start
