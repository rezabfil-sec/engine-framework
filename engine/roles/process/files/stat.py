#!/usr/bin/python3

import json
import sys
import argparse

def parse_cli(args):
    """Parse command line arguments """
    parser = argparse.ArgumentParser(prog='pm', description='Process statistics')
    parser.add_argument('-p', '--pss', help='Json file with per_submodules_statistics')
    parser.add_argument('-i', '--indexes', default='', help='comma separated list of indexes')
    parser.add_argument('-d', '--default', action='store_true', help='list default statistics joined with submodules')
    parser.add_argument('-q', '--queue_types', default="be,cbs,etf,mqprio,taprio", help="relevant queue types")
    return parser.parse_args(args)

def list_statistic_submodules_names(per_submodules_statistics, indexes, default_only=False, queue_types=['be', 'cbs', 'etf', 'mqprio', 'taprio']):
    submodules_names_list = []
    for submodules_statistics in per_submodules_statistics:
        submodules = []
        names = []
        submodules_and_submodule_arrays = []
        for submodule in submodules_statistics['submodules']:
            indexes_list = indexes
            if not 'array' in submodule.keys() or not submodule['array']:
                indexes_list = ['*']
            if 'queue_types' not in submodule.keys() or set(submodule['queue_types']).intersection(queue_types):
                for index in indexes_list:
                    submodules.append(submodule['name'] + ( ( '[' + index + ']' ) if 'array' in submodule.keys() and submodule['array'] else "" ))
        for statistic in submodules_statistics['statistics']:
            if not default_only or ('default' in statistic.keys() and statistic['default']):
                result_recording_modes = []
                if 'result_recording_modes' in statistic.keys():
                    result_recording_modes = statistic['result_recording_modes']
                elif 'vector_recording' in statistic.keys() and statistic['vector_recording'] :
                    result_recording_modes += ['vector']
                for mode in result_recording_modes:
                    names.append(statistic['name'] + ':' + mode)
        if len(submodules)>0 and len(names)>0:
            submodules_names_list.append((submodules, names))
    return submodules_names_list

def list_default_statistics(per_submodules_statistics, indexes, queue_types):
    submodules_names_list = list_statistic_submodules_names(per_submodules_statistics, indexes, True, queue_types)
    return [ (submodule, name) for submodules, names in submodules_names_list for submodule in submodules for name in names ]

def main():
    parser_args = parse_cli(sys.argv[1:])
    per_submodules_statistics_file = parser_args.pss
    if parser_args.indexes == "":
        indexes = []
    else:
        indexes = parser_args.indexes.split(',')
    default = parser_args.default
    queue_types = parser_args.queue_types.split(',')

    with open(per_submodules_statistics_file, 'r') as f:
        per_submodules_statistics = json.load(f)

    if default:
        default_statistics_list = list_default_statistics(per_submodules_statistics, indexes, queue_types)
        print(default_statistics_list)
    else:
        submodules_names_list = list_statistic_submodules_names(per_submodules_statistics, indexes, False, queue_types)
        print(submodules_names_list)

if __name__ == "__main__":
    main()
