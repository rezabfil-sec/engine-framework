#!/usr/bin/env python3

# functions for plotting

import glob
import matplotlib.pyplot as plt
import os
import pandas as pd
import time

figSize = (24,12)

stream_to_color = {
    1 : 'tab:blue',
    2 : 'tab:orange',
    3 : 'tab:green',
    4 : 'tab:red',
    5 : 'tab:purple',
    6 : 'tab:brown',
    7 : 'tab:pink',
    8 : 'tab:gray',
    9 : 'tab:olive',
    10 : 'tab:cyan',
    11 : 'black'} # magenta, yellow

def read_csv(prePath):
    ''' read csv, return pandas data frame '''
    fileName = glob.glob(prePath)
    df = pd.read_csv(fileName[0])
    return df

def prepare(topic, processing_descriptor):
    ''' do common tasks at the start of all functions '''
    fl = processing_descriptor.log_file()
    with open(fl, "a") as myFile:
        print('Plotting ' + topic + ' for', processing_descriptor.experiment + ' for node ' + processing_descriptor.node, end='...\t', file=myFile)
    start_time = time.time()

    fig, ax = plt.subplots(1, figsize=figSize)

    return fl, start_time, fig, ax

def follow_up(plot_name, processing_descriptor, topic_short, fl, start_time, fig):
    ''' do common tasks at the end of all plotting functions '''
    paths = ['/plots/' + processing_descriptor.experiment + '/' + topic_short + '/' + processing_descriptor.node + '/']

    for path in paths:
        pre_out_path = processing_descriptor.folder + path
        if not os.path.exists(pre_out_path):
            os.makedirs(pre_out_path, exist_ok=True)
        fig.savefig(pre_out_path + '/' + plot_name, dpi=100, bbox_inches='tight', format='png')
    plt.close('all')

    with open(fl, "a") as myFile:
        print('It took', time.time() - start_time, 's for', processing_descriptor.node, 'ports', processing_descriptor.dst_ports, '\n', file=myFile)

def plots_exist(plot_name, processing_descriptor, topic_short):
    ''' check if plots already exists, to not compute them again '''
    paths = ['/plots/' + processing_descriptor.experiment + '/' + topic_short + '/' + processing_descriptor.node + '/']

    for path in paths:
        plot_path = processing_descriptor.folder + path + plot_name
        if not os.path.isfile(plot_path):
            return False

    return True
