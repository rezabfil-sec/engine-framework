#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import glob
import re
import numpy as np
import pandas as pd
from pandas import DataFrame
import matplotlib as mpl
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.pyplot import cycler # plot styling
import argparse
import math
import json
import datetime
import matplotlib.colors
import colorsys
import matplotlib.lines as mlines
import matplotlib.patches as patches

from typing import Dict, List, Tuple, Callable, Any, Iterable, TypeVar, Generic
from colorama import init, Fore, Style
init()

import shutil
np.set_printoptions(linewidth=shutil.get_terminal_size((80, 20)).columns) # auto-detect terminal width (with fallback)


import sys, os
sys.path.append(os.path.dirname(os.path.realpath(__file__))) # this works regardless of the cwd
#import patched_backend_pgf

import sys
from typing import Dict
def mergeDicts(a : Dict, b : Dict) -> Dict:
    temp = a.copy()
    temp.update(b)
    return temp
def debug():
    """!Only for debugging!: Open interactive python interpreter with the caller's environment"""
    import code
    import inspect
    if "pandas" in sys.modules:
        # to make sure name "pandas" is present
        import pandas
        pandas.set_option('display.width', None) # auto-detect terminal width
    if "numpy" in sys.modules:
        import numpy
        import shutil
        numpy.set_printoptions(linewidth=shutil.get_terminal_size((80, 20)).columns)

    code.interact(local=mergeDicts(inspect.currentframe().f_back.f_globals, inspect.currentframe().f_back.f_locals))

def print_warn(msg):
    if "colorama" in sys.modules:
        from colorama import Fore
        print(f"{Fore.MAGENTA}{msg}{Fore.RESET}", file=sys.stderr)
    else:
        print(msg, file=sys.stderr)

_darkYellow = "#fab20b" # XXX dark yellow
_orange = "#ff7f0e" # the less beautiful XXX orange: #E37222
_red = "#d62728"
_green = "#A2AD00"
_green = "#A2AD00"
_darkGreen= "#008940" #XXXDarkGreen
_lighterBlue = "#5aa3d8"
_pantone300 = "#3070b3" # XXX blue
_turquois = "#017a8c" # XXXTurquois
# non-XXX:
_purple = "#75005f"
_bluepurple = "#681edf"


def rc_setting(mode):

    if mode == "pgf":
        matplotlib.use("pgf")
    elif mode == "pdf":
        matplotlib.use("pdf")

    #Direct input

    linestyle_cycler = (cycler("color", plt.cm.viridis(np.linspace(0,1,5))) + cycler('linestyle',['-','--',':','-.', '-']))
    #Options
    return {
        # Use LaTeX to write all text
        # "pgf.texsystem": "pdflatex",
        "text.usetex": False,
        "font.family": "serif",
        # Use 10pt font in plots, to match 10pt font in document
        "axes.labelsize": 10,
        "font.size": 12,
        # Make the legend/label fonts a little smaller
        "legend.fontsize": 10,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        #"axes.prop_cycle":linestyle_cycler,
        "axes.grid": False,
        "grid.linestyle": "--",
        "grid.linewidth": 0.5,  # default 0.8
        "grid.color": "c0c0c0c0", # default #b0b0b0
        "axes.axisbelow": True,
        "legend.framealpha": 1,
        "patch.linewidth": 0.8, # default 1.0
        "legend.handlelength": 1.0, # default 2.0
        "legend.handletextpad": 0.5, # default 0.8
        "legend.columnspacing": 0.8, # default 2
    }

colors = [_green, _pantone300, _orange, _darkGreen, _lighterBlue, _darkYellow, _red, _purple, _turquois, _bluepurple]
colors_five_two_one = [_darkYellow,_orange, _red, _purple, _bluepurple, _lighterBlue, _pantone300, _darkGreen]

color_cycles = { # maps number of needed styles to the according color schemes
    2: [_green, _pantone300],
    3: [_green, _pantone300, _orange],
    4: [_green, _pantone300, _red, _orange],
    5: [_green, _darkGreen, _pantone300, _darkYellow, _red],
    6: [_green, _darkGreen, _lighterBlue, _pantone300, _darkYellow, _orange],
    7: [_darkYellow, _orange, _red, _green, _darkGreen, _lighterBlue, _pantone300],
    8: [_green, _darkGreen, _lighterBlue, _pantone300, _red, _darkYellow, _orange, _purple],
    10: colors,
    11: [_green, _darkGreen, _lighterBlue, _pantone300, _red, _darkYellow, _orange, _purple, _green, _darkGreen, _lighterBlue ],
    16: [_green, _darkGreen, _lighterBlue, _pantone300, _red, _darkYellow, _orange, _purple, _green, _darkGreen, _lighterBlue, _pantone300, _red, _darkYellow, _orange, _purple],
}
def color_handles(handles: Iterable):
    """ applies an appropriate color cycle/scheme to the given mathplotlib artist handles """
    handles = list(handles)
    colors = color_cycles.get(len(handles), None)
    if colors is None:
        print_warn(f"No color cycle for {len(handles)}!")
    else:
        for (handle, color) in zip(handles, colors):
            plt.setp(handle, color=color)

def color_violinplot_handle(handle, color):
    for pc in handle["bodies"]:
        pc.set_facecolor(color)
        pc.set_alpha(0.4) # 0.2 seemed to be a little too weak in print
    for item, handle in handle.items(): # set color for all components, e.g. "cmaxes", "cmins", "cbars"
        if item != "bodies":
            handle.set_color(color)

def nsToUs(x):
    return x / math.pow(10, 3)

def nsToMs(x):
    return x / math.pow(10, 6)

def findCsvSubdirHeuristic(path: str):
    dirpaths = []
    for dirpath, dirs, files in os.walk(path, followlinks=True):
        for filename in files:
            if re.match("n.*.csv", filename) is not None:
                dirpaths.append(dirpath)
    return dirpaths

def findFrostDalekBenchmarkResultJsonHeuristic(path: str):
    for dirpath, dirs, files in os.walk(path, followlinks=True):
        for filename in files:
            filename = "kata_algofi.json"
            # filename = "tdx_cloud.json"
            if filename == filename:
                return os.path.join(dirpath, filename)
    return None

def findConfigJsonHeuristic(path: str):
    """ finds the path to allocation.json containing metadata such as the date"""
    pos_alloc_file = ["config", "allocation.json"]
    temp = os.path.join(path, *pos_alloc_file)
    if os.path.exists(temp):
        return temp

    temp = os.path.join(path, "..", *pos_alloc_file)
    if os.path.exists(temp):
        return temp

    return None

def parseTestcaseDesc(desc: str) -> (str, Dict):
    """ The result csv files contain the test case and its parameters, which we parse here
    returns: (testcase_name, argdict) """
    print(desc)
    if "dkg" in desc.split("_"):
        desc = desc.split("_")[1]
    elif "sign" in desc.split("_"):
        desc = desc.split("_")[1] + "_" + desc.split("_")[2]
    else:
        desc = desc.split("_")[1] + "_" + desc.split("_")[2]
    if desc == "dkg":
        return ("dkg", {})

    matches = re.search('^prep(rocess)?_nn(?P<%s>[0-9]+)$' % "num_noncepairsGroup", desc)
    if matches is not None:
        num_noncepairs = int(matches.group("num_noncepairsGroup"))
        return ("preprocess", {"num_noncepairs": num_noncepairs})

    matches = re.search('^sign?_l(?P<%s>[0-9]+)$' % "msg_lenGroup", desc)
    print(matches)
    if matches is not None:
        msg_len = int(matches.group("msg_lenGroup"))
        return ("sign", {"msg_len": msg_len})

    print(f"Unknown testcase description '{desc}'", file=sys.stderr)
    assert(False)

def get_range_params(values: List) -> str:
    """ return concise description for start;end;stepsize in given array or range (suitable as filename) """
    if len(values) == 1:
        return str(values[0])
    values = sorted(values)
    start = values[0]
    stop = values[-1]
    stepwidth = values[1] - values[0]
    reconstructed = range(start, stop+1, stepwidth)
    if np.array_equal(reconstructed, values):
        if stepwidth == 1:
            return f"{start}-{stop}"
        else:
            return f"{start}-{stop}s{stepwidth}"
    else:
        return f"{','.join(map(lambda x: str(x), values))}"

def sample_in_list(len_sample_set: int, num_samples: int): # -> list-like
    """ samples with equal distance and returns indices """
    if num_samples == 1:
        return [math.floor(len_sample_set/2)] # use value in the middle if only one is requested
    def to_int(x):
        if x < len_sample_set/2:
            return math.floor(x)
        else:
            return math.ceil(x)
    num_samples = min(num_samples, len_sample_set)
    return map(to_int, np.linspace(0, len_sample_set-1, num=num_samples))

def sample_t_values(values: List, num_samples: int) -> Iterable:
    """ samples with equal distance and returns values. Ensures that t=2 is returned when within/near range """
    def to_int(x):
        if x < len(values)/2:
            return math.floor(x)
        else:
            return math.ceil(x)

    if num_samples == 1:
        indices = [math.floor(len(values)/2)] # use value in the middle if only one is requested
    else:
        num_samples = min(num_samples, len(values))
        indices = list(map(to_int, np.linspace(0, len(values)-1, num=num_samples)))

    # nudge towards t=2
    if 2 in values and 2 not in map(lambda i: values[i], indices):
        for index, i in enumerate(indices):
            if i > 0 and values[i-1] == 2:
                indices = indices[:i-1] + [i-1] + indices[i:]
                break
            if values[i] == 1:
                assert(values[i+1] == 2)
                indices = indices[:i] + [i+1] + indices[i+1:]
                break
    return map(lambda i: values[i], indices)

def filterlist(bottom, top, iterable):
    """ removes all list elements not within the given bounds """
    below = lambda y: y < top
    above = lambda y: y > bottom
    return list(filter(above, filter(below, iterable)))

def violin_settings(t_values: List[int]) -> Dict:
    """ common settings for all violin plots
    :t_values: list of values on the x axis
    """
    if len(t_values) >= 2:
        dist = t_values[1] - t_values[0]
    else:
        dist = 1
    # dirty hack to make the violins fit into the plot area horizontally
    dist = 1 if dist==2 else dist
    return {"widths": 0.7 * dist}

class Plotter():
    import matplotlib.pyplot as plt # this sets self.plt

    def __init__(self, output_dir, pos_alloc_file: str = None, write = False):
        """ :write: write graphs to file
        :pos_alloc_file: path to pos' allocation.json
        """
        self.num_threads_dut = None
        self.pos_alloc_info = None
        if pos_alloc_file is None: # ugly:
            print_warn("Missing infos on allocation!")
        else:
            with open(pos_alloc_file, 'r') as f:
                self.pos_alloc_info = json.load(f)
            alloc_dir = os.path.join(os.path.dirname(pos_alloc_file), "..")
            dut_node = None
            for node in self.pos_alloc_info["nodes"]:
                with os.scandir(os.path.join(alloc_dir, node)) as it:
                    is_dut_node = True
                    for entry in it:
                        if entry.name.endswith(".csv"): # DuT node running the peers hasn't CSV files
                            is_dut_node = False
                            break
                    if not is_dut_node:
                        continue
                    dut_node = node
                    break

            lshw_path = os.path.join(alloc_dir, dut_node, "json+lshw.stdout")
            if not os.path.exists(lshw_path):
                print_warn("lshw missing, no num_threads shown!")
            else:
                with open(lshw_path, 'r') as f:
                    # fix broken JSON
                    data = f.read()
                    # fix first & last bytes
                    data = re.sub("^\[\n", '', data)
                    data = re.sub("\]\n\n$", '}', data)
                    # other broken stuff
                    data = re.sub("\n\s*}\s*{\s*\n", '\n }, "children" : [ {\n', data)
                    data = re.sub('"        {', '", "children" : [        {', data)
                    data = re.sub('0            {', ', "children" : [        {', data)
                    data = re.sub("\n\n", '\n ] \n', data)
                    data = re.sub("},\s*\n\s*]", '}\n]', data)

                    lshw = json.loads(data)

                    for item in lshw["children"][0]["children"]:
                        if item["class"] == "processor":
                            if re.match("cpu(:\d+)?", item["id"]) is None:
                                print_warn(f"Processor id has unknown format {item['id']}")
                            if self.num_threads_dut is None:
                                self.num_threads_dut = int(item["configuration"]["threads"])
                            else:
                                self.num_threads_dut += int(item["configuration"]["threads"])
            print(f"DuT {dut_node} has {self.num_threads_dut} threads")
        # values in inch
        # marging between figure and edge
        self.marginleft = 0.001

        self.output_dir = None
        if write:
            self.output_dir = output_dir
            # mpl.use("pgf") # comment out for debugging and development
            # # Need to patch backend because sketched lines not shown in pdf
            # #mpl.use("module://patched_backend_pgf.backend_pgf")
            # mpl.rcParams.update(self.pgf_with_custom_preamble)
        # self.filetypes = [".pgf", ".pdf"]
        self.filetypes = [".pdf"]
        self.grid_minor_color = "0.93"

    def config_x_axis_as_number_of_nodes(self, n_values: List[int]):
        if len(n_values) <= 90:
            self.ax.set_xticks(n_values)
            self.ax.set_xlim(min(n_values)-0.5, max(n_values)+0.5)
        else:
            print_warn("too many xticks, TODO")
        if self.num_threads_dut is not None:
            self.ax.axvline(self.num_threads_dut, ls='--', in_layout=False, color='#4a4a4a', zorder=2.00001)
        self.ax.set_xlabel("Number of Nodes $n$")

    def config_x_axis_as_threshold(self, t_values: List[int]):
        if len(t_values) <= 90:
            self.ax.set_xticks(t_values)
            self.ax.set_xlim(min(t_values)-0.4, max(t_values)+0.4)
        else:
            print_warn("too many xticks, TODO")
        self.ax.set_xlabel("Threshold $t$")

    def config_y_axis_as_time_in_ms(self):
        self.ax.set_ylabel("E2E Latency [ms]")
        self.ax.yaxis.grid(True, which='major')
        self.ax.yaxis.grid(True, which='minor', color="0.8", alpha=0.45)

        y_values = self.ax.yaxis.get_majorticklocs()
        if len(y_values) > 1:
            # use crude heuristic to add subgrid lines for each second
            if int(y_values[1] - y_values[0]) == 2000:
                self.ax.yaxis.set_minor_locator(matplotlib.ticker.AutoMinorLocator(n=2))
            else:
                self.ax.yaxis.set_minor_locator(matplotlib.ticker.AutoMinorLocator())

    def plot_sign_inc_n_t_violinplot(self, dfraw: DataFrame) -> (str, str):
        """ returns (diagram label/caption, filename_root)"""
        # cloud bls
        n_filter = [5,9,12,16,20,24,32]
        # local all, cloud schnorr
        n_filter = [5,9,12,16,20,24,32,40]
        if n_filter:
            # Filter the DataFrame to only include rows with n in n_filter
            dfraw = dfraw[dfraw.index.get_level_values('n').isin(n_filter)]
        exclude_n_equals_t = True
        if exclude_n_equals_t:
            # Remove rows where n == t
            dfraw = dfraw[dfraw.index.get_level_values('n') != dfraw.index.get_level_values('t')]

        dfa = dfraw.groupby(level=["n", "t"]).apply(lambda x: x)

        handles = {}
        n_t_values = dfa.index.droplevel("run_id").unique()

        # Sort by n first and then by t
        n_t_values_sorted = sorted(n_t_values, key=lambda x: (x[0], x[1]))  # Sort by n first, then by t

        # Extract just the (n, t) pairs for the xticks
        unique_n_t_pairs = list({(n, t) for n, t, _ in n_t_values_sorted})
        unique_n_t_pairs.sort(key=lambda x: (x[0], x[1]))  # Sort by t first, then n
        # Create alternating patch colors
        patch_colors = ['lightgray', 'lightblue']
        # Create a mapping from (n, t) pairs to unique x positions based on the sorted values
        unique_positions = {}
        current_x_pos = 0
        last_n = None
        spacing = 1  # Space between n groups
        for n, t in unique_n_t_pairs:
            if n != last_n and last_n is not None:
                # If n changes, increase x_pos to add space
                current_x_pos += spacing
            unique_positions[(n, t)] = current_x_pos
            current_x_pos += 1  # Increment x_pos for the next (n, t)
            last_n = n

        # Define color map for each unique msg_len value
        unique_msg_len_values = sorted(set([msg_len for _, _, msg_len in n_t_values_sorted]))  # Extract unique msg_len values
        color_map = plt.get_cmap('tab10')  # Use a colormap for msg_len colors
        msg_len_color_map = {msg_len: color_map(i / len(unique_msg_len_values)) for i, msg_len in enumerate(unique_msg_len_values)}  # Map msg_len to color


        # Define marker map for each unique msg_len value
        marker_map = {256: 'o', 512: 's', 700: 'v', 701: 'v', 705: '^', 706: '^',
                    750: 'D', 755: 'p', 756: 'p', 777: '*'}
        legend_elements = {}  # Store legend elements, keyed by msg_len
            # Track start and end positions for each `n`
        labels_type = "cloud"
        for n, t, msg_len in n_t_values_sorted:
            # Use the unique x position for the (n, t) pair
            x_pos = unique_positions.get((n, t))
            if n > 32:
                labels_type = "local"

            # Access the data for the given (n, t, msg_len) from the index levels
            df = dfraw.loc[(dfraw.index.get_level_values('n') == n) &
                        (dfraw.index.get_level_values('t') == t) &
                        (dfraw.index.get_level_values('msg_len') == msg_len), "duration_ms"]

            # Plot violin plot with the same color for each n, same x position for all msg_len
            handle_violin = self.ax.violinplot([df.values.flatten()], positions=[x_pos], **violin_settings([n]))

            # Set the color for the violin plot components
            for pc in handle_violin["bodies"]:
                pc.set_facecolor(msg_len_color_map[msg_len])  # Set the color of the violin body
                pc.set_edgecolor(msg_len_color_map[msg_len])  # Set the edge color
                pc.set_alpha(0.4)
                pc.set_zorder(2.4)

            # Set the color for other violin plot components (cmins, cmaxes, cbars)
            for item in ["cmaxes", "cmins", "cbars"]:
                handle_violin[item].set_color(msg_len_color_map[msg_len])  # Set color to match n
                handle_violin[item].set_zorder(2.5)

            # Scatter plot with mean at the same x position, using different markers for msg_len
            handle_mean = self.ax.scatter(x_pos, df.agg(np.mean),
                                        marker=marker_map.get(msg_len, 'o'),  # Default to 'o' if msg_len not in marker_map
                                        color=msg_len_color_map[msg_len], s=8,  # s controls marker size
                                        zorder=3)

            # Determine label based on msg_len and add to legend
            if msg_len == 256:
                label_provided = "LXC Local"
            elif msg_len == 512:
                label_provided = "Kata SEV-SNP"
            elif msg_len == 700 or msg_len == 701:
                label_provided = "N2D Base"
            elif msg_len == 705 or msg_len == 706:
                label_provided = "N2D SEV-SNP"
            elif msg_len == 750:
                label_provided = "C3 Base"
            elif msg_len == 755 or msg_len == 756:
                label_provided = "C3 TDX"
            elif msg_len == 777:
                label_provided = "Multi-N2D SEV-SNP"

            if msg_len not in legend_elements:
                legend_element = mlines.Line2D([], [], color=msg_len_color_map[msg_len], marker=marker_map.get(msg_len, 'o'),
                                            linestyle='None', markersize=8, label=f"{label_provided}")
                legend_elements[msg_len] = legend_element

        # Apply colors to handles
        color_handles(handles.values())

        # Add the custom legend for msg_len markers
        self.ax.legend(handles=legend_elements.values(), loc='center left',fontsize=8)
        self.ax.set_ylim(bottom=0, top=160)

       #Apply alternating patches and red n labels for n groups
        patch_index = 0  # For alternating between two colors
        last_x_pos = None

        # Track start and end positions for each `n`
        n_start_pos = 0
        n_end_pos = None

        for (n, t), x_pos in unique_positions.items():
            if last_n is None:
                last_n = n
                n_start_pos = x_pos

            # Handle patch and text after encountering each new `n`
            if last_x_pos is not None and n != last_n:
                 # Apply the green line between groups
                self.ax.axvline(x=n_start_pos - 0.5, color='green', linestyle='--', lw=0.5)

                # Apply the patch color for the last `n` group
                n_end_pos = last_x_pos  # Last position for this `n`
                # print(type(n_start_pos))
                self.ax.add_patch(patches.Rectangle(
                    (n_start_pos - 0.5, self.ax.get_ylim()[0]),  # Lowerleft corner of the box
                    n_end_pos - n_start_pos + 2,                 # Width of the box (covers range of t values)
                    self.ax.get_ylim()[1] - self.ax.get_ylim()[0],  # Height of the box (full y-range)
                    edgecolor='none', facecolor=patch_colors[patch_index % 2], alpha=0.2  # Alternating background colors
                ))

                # Add red label in the center of the patch
                midpoint = (n_start_pos + n_end_pos) / 2
                ylim = self.ax.get_ylim()
                vertical_midpoint = (ylim[0] + ylim[1]) / 2
                self.ax.text(midpoint+0.5, vertical_midpoint+50, f"n={last_n}",
                            ha='center', va='center', color='red', rotation=0, fontsize=8, fontweight='bold')

                # Move to the next patch color for the next group
                patch_index += 1
                n_start_pos = x_pos  # New starting position for the next `n`

            last_x_pos = x_pos
            last_n = n

        # Handle the final patch and label for the last `n`
        n_end_pos = last_x_pos
        self.ax.add_patch(patches.Rectangle(
            (n_start_pos - 0.5, self.ax.get_ylim()[0]),  # Lowerleft corner of the box
            n_end_pos - n_start_pos + 1,                 # Width of the box (covers range of t values)
            self.ax.get_ylim()[1] - self.ax.get_ylim()[0],  # Height of the box (full y-range)
            edgecolor='none', facecolor=patch_colors[patch_index % 2], alpha=0.2  # Alternating background colors
        ))
        # Add the final green line between the last group
        self.ax.axvline(x=n_start_pos-0.5, color='green', linestyle='--', lw=0.5)

        # Add the final red label for the last `n`
        midpoint = (n_start_pos + n_end_pos) / 2
        vertical_midpoint = (ylim[0] + ylim[1]) / 2
        self.ax.text(midpoint, vertical_midpoint+50, f"n={last_n}",
                    ha='center', va='center', color='red', rotation=0, fontsize=8, fontweight='bold')

        if labels_type == "cloud":
            # 3,5,9,12,16,20,24,32
            labels = ["2", "4", "2","4","8", "2", "4", "8", "11", "2", "4", "8", "15", "2", "4","8","16","19", "2","4","8","16","23", "2","4","8","16","31"]
            xtick_sizes = [9,9, 9,6,9, 9,6,6,9, 9,6,6,9, 9,6,6,6,9, 9,6,6,6,9, 9,6,6,6,9]
        else:
            # labels local - BLS
            labels = [ "2", "4", "2","4","8", "2", "4", "8", "11", "2", "4", "8", "15", "2", "4","8","16","19", "2","4","8","16", "23", "2", "4","8","16","31", "2", "4","8","16","32","39"]
            xtick_sizes = [9,9, 9,6,9, 9,6,6,9, 9,6,6,9, 9,6,6,6,9, 9,6,6,6,9, 9,6,6,6,9, 9,6,6,6,6,9]


        if len(labels) != len(unique_positions):
            raise ValueError(f"The number of labels ({len(labels)}) does not match the number of x-tick positions ({len(unique_positions)})")

        self.ax.set_xticks([unique_positions[(n, t)] for (n, t) in unique_n_t_pairs])  # Set x-ticks at the correct positions
        self.ax.set_xticklabels(labels, rotation=0)

        print(len(xtick_sizes), len(labels))
        if xtick_sizes:
            xticklabels = self.ax.get_xticklabels()
            for label, size in zip(xticklabels, xtick_sizes):
                label.set_fontsize(size)  # Set each label with its corresponding size

        # Adjust x-limits to remove extra space
        self.ax.set_xlim(min(unique_positions.values()) - 0.5, max(unique_positions.values()) + 0.5)
        self.ax.set_xlabel("Threshold $t$")
        # Configure the y-axis
        self.config_y_axis_as_time_in_ms()

        # Caption creation
        if self.num_threads_dut is None:
            caption = ""
        else:
            caption = f"Signing; max. parallel threads: ${self.num_threads_dut}$"

        return (caption, "inc_n_t_sign_violin")


    def __new_plot(self, break_y_axis = None, figsize = None):
        """
            figsize: (width, height)
        """
        self.plt.rcParams.update(rc_setting("pdf"))
        if break_y_axis is None:
            print("Here")
            # Sign & preprocess
            self.fig, self.ax = self.plt.subplots(figsize=[6.5,2.5])
            # DKG
            # self.fig, self.ax = self.plt.subplots(figsize=[7,4.5])
            self.ax.grid(color="0.8")
        else:
            assert(break_y_axis > 1)
            # see https://matplotlib.org/stable/gallery/subplots_axes_and_figures/broken_axis.html
            self.fig, axes = self.plt.subplots(break_y_axis, 1, sharex=True, figsize=figsize)
            self.axs = list(reversed(axes)) # self.axs contains axes from bottom to top
            self.fig.subplots_adjust(hspace=0.05)  # adjust space between axes

            # joint X grid
            self.ax_grid = self.fig.add_subplot(111, zorder=-1)
            for _, spine in self.ax_grid.spines.items():
                spine.set_visible(False)
            self.ax_grid.tick_params(labelleft=False, labelbottom=False, left=False, right=False)
            self.ax_grid.get_shared_x_axes().join(self.ax_grid, *self.axs) #self.axs[-1])
            self.ax_grid.grid(axis="x", color="0.8")

            for i in range(0, break_y_axis-1):
                prevax = i
                nextax = i+1
                # draw wiggled line
                for spine in [self.axs[nextax].spines["bottom"], self.axs[prevax].spines["top"]]:
                    spine.set_edgecolor("0.5")
                    spine.set_zorder(1.9)
                    spine.set_sketch_params(scale=5, length=10, randomness=42)
                self.axs[nextax].xaxis.tick_top()
                self.axs[nextax].tick_params(labeltop=False, length=0) # no tick labels at the top

                # cut-out indicator
                d = .6  # proportion of vertical to horizontal extent of the slanted line
                kwargs = dict(marker=[(-1, -d), (1, d)], markersize=12, linestyle="none", color='k', mec='k', mew=1,
                              clip_on=False)
                self.axs[prevax].plot([0, 1], [1, 1], transform=self.axs[prevax].transAxes, **kwargs)
                self.axs[nextax].plot([0, 1], [0, 0], transform=self.axs[nextax].transAxes, **kwargs)

            for ax in self.axs:
                ax.grid(color="0.8")

    def __save_plot(self, filename_root: str):
        if self.output_dir is None:
            self.plt.show()
        else:
            for fileEnding in self.filetypes:
                filepath = os.path.join(self.output_dir, f"{filename_root}{fileEnding}")
                self.plt.savefig(filepath, transparent=True,bbox_inches='tight')
                print(f"Wrote {filepath}")

    def plot(self, resultDirs: str):
        """
        :resultDir: the folder with the csv files
        """
        nmap = {}
        testcase_desc = None
        testcase = None
        for resultDir in resultDirs:
            for resultFile in glob.iglob(os.path.join(os.path.abspath(resultDir), "n*_t*_*.csv")):
                if os.path.isfile(resultFile):
                    fileName = os.path.basename(resultFile)

                    nGroup = "n"
                    tGroup = "t"
                    testcaseGroup = "testcase"

                    fileNameMatches = re.search('^n(?P<%s>[0-9]+)_t(?P<%s>[0-9]+)_(?P<%s>\S+)(\.csv)$' % (nGroup, tGroup, testcaseGroup), fileName)
                    print(fileNameMatches)
                    if fileNameMatches is None:
                        raise ValueError("Unknown file {} present".format(fileName))

                    n = int(fileNameMatches.group(nGroup))
                    t = int(fileNameMatches.group(tGroup))
                    testcase_desc_parsed = fileNameMatches.group(testcaseGroup)
                    testcase_parsed, _ = parseTestcaseDesc(testcase_desc_parsed)

                    if testcase is None:
                        testcase = testcase_parsed
                    else:
                        assert(testcase == testcase_parsed)
                    #print(f"parsed n={n}, t={t}, testcase={testcase_desc_parsed}")
                    df = pd.read_csv(resultFile, index_col="run_id", dtype={"is_ok": bool, "duration_ns": int }) # usecols=["is_ok", "run_id", "duration_ns"]

                    if "is_ok" in df.columns:
                        err = len(df.loc[df["is_ok"] == False])
                        if err != 0:
                            print_warn(f"{fileName}: Dropping {err} useless measurements")
                            df.drop(df[df["is_ok"] == False].index, inplace=True)
                        df.drop(["is_ok"], axis=1, inplace=True)
                    # convert nanoseconds to milliseconds
                    df['duration_ms'] = df['duration_ns'].apply(nsToMs)
                    df.drop(["duration_ns"], axis=1, inplace=True)

                    mytmap = nmap.setdefault(n, {})
                    testcasemap = mytmap.setdefault(t, {})
                    testcasemap[testcase_desc_parsed] = df
        dfs = []
        ns = []

        for n, tmap in nmap.items():
            tmapresults = {}
            for t, testcasemap in tmap.items(): # this could be a map() call
                dataframes = []
                for testcase_desc, dataframe in testcasemap.items():
                    testcase, testcase_args = parseTestcaseDesc(testcase_desc)
                    if testcase == "dkg":
                        pass  # nothing to be done
                    elif testcase == "preprocess": # add num_noncepairs as index level
                        dataframe = pd.concat([dataframe], keys=[testcase_args["num_noncepairs"]], names=["num_noncepairs"])
                    elif testcase == "sign": # add msg_len is index level
                        dataframe = pd.concat([dataframe], keys=[testcase_args["msg_len"]], names=["msg_len"])
                    else:
                        assert(False)
                    dataframes.append(dataframe)

                tmapresults[t] = pd.concat(dataframes)

            dfs.append(pd.concat(tmapresults, names=["t"])) # keys (t values) are automatically used as keys in the DF
            ns.append(n)

        dfraw = pd.concat(dfs, keys=ns, names=["n"])
        dfraw.sort_index(inplace=True)

        print(f"Parsed CSV for n={get_range_params(dfraw.index.get_level_values('n').unique())}, t={get_range_params(dfraw.index.get_level_values('t').unique())}, ", end='')
        if testcase == "dkg":
            print("dkg\n")
        elif testcase == "preprocess":
            print(f"preprocess num_noncepairs={get_range_params(dfraw.index.get_level_values('num_noncepairs').unique())}\n")
        elif testcase == "sign":
            print(f"sign msg_len={get_range_params(dfraw.index.get_level_values('msg_len').unique())}\n")

        plotting_funcs = []

        if testcase == "dkg":
            plotting_funcs.append(self.plot_dkg)
            plotting_funcs.append(self.plot_dkg_violinplot)
            plotting_funcs.append(self.plot_dkg_inc_t_violinplot)
        elif testcase == "preprocess":
            plotting_funcs.append(self.plot_preprocess_inc_n_violinplot)
        elif testcase == "sign":
            plotting_funcs.append(self.plot_sign_inc_n_t_violinplot)
        else:
            assert(False)

        n_info = get_range_params(dfraw.index.get_level_values('n').unique())

        for func in plotting_funcs:
            self.__new_plot(figsize=[7, 3.5])
            bottomlabel, filename_root = func(dfraw)
            self.__save_plot(f"n{n_info}_{filename_root}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot results of benchmarks")
    parser.add_argument('-f', '--folder_scene', dest='folder_scene', help='Scene folder where the results directory is.', required=True)
    parser.add_argument("-d", "--dir", dest='dir', help='Playbook directory.', required=False)
    parser.add_argument("-s", "--scene", dest='scene', help='Scenario name.', required=False)

    if "argcomplete" in sys.modules:
        argcomplete.autocomplete(parser)
    args = parser.parse_args()
    resultDir = args.folder_scene
    path = os.path.realpath(resultDir)
    if not os.path.exists(path):
        print("Dir does not exist", file=sys.stderr)
        exit(1)
    pos_alloc_file = findConfigJsonHeuristic(path)
    if pos_alloc_file is None:
        print_warn("Could not find pos metadata json")
    output = resultDir
    p = Plotter(output, pos_alloc_file, write=(output is not None))

    dirpaths = findCsvSubdirHeuristic(path)

    if dirpaths is None:
        print_warn("Did not find result CSV files")
    else:
        p.plot(dirpaths)
