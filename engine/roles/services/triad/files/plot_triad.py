import sys
import re
import os
from argparse import ArgumentParser

try:
    import seaborn as sns
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    import pandas as pd
except ImportError:
    print('Failed to load dependencies. Please ensure that seaborn, matplotlib, and pandas can be loaded.', file=sys.stderr)
    exit(-1)

def exportToPdf(fig, filename):
    """
    Exports the current plot to file. Both in the 10:6 and 8:6 format     """

    # Saving to 8:6 format (no name change)
    fig.set_figwidth(8)
    fig.set_figheight(6)

    fig.savefig(filename, bbox_inches='tight', format='pdf')
    print(f"Wrote output to {filename}")


    # Saving plot to slide format 10:6 (with changed name to sld_)
    fig.set_figwidth(10)
    fig.set_figheight(6)
    
    path, file = os.path.split(filename)
    file = "sld_" + file
    filename = os.path.join(path, file)
    fig.savefig(filename, bbox_inches='tight', format='pdf')
    print(f"Wrote output to {filename}")

def fileToDf(file, filename, normalization):
    data = { "Data size": [], "MFLOPS": [], "Duration" : [], "Mode": [], "EPC" : []}

    epc = re.findall("_(\d+)g", filename)
    if len(epc) > 0:
        epc = epc[0]
    else:
        epc = 0
    mode = "Baseline"
    direct = re.findall("_e", filename)
    # print(filename)
    # print(direct)
    if len(direct) > 0:
        mode = "Enclave"

    if filename == "Baseline" or filename == "Enclave":
        mode = filename

    for line in file:
        # print("Line: ", line)
        matchData = re.match("MFLOPs \(N=\s*(\d+)\): (\d+\.\d+)", line)
        if matchData == None:
            matchDur = re.match("Duration: (\d+\.\d+)s", line)
            if matchDur == None:
                continue
            else:
                dur = float(matchDur.group(1))
                data["Duration"].append(dur)
                continue
        # print(matchData)
        size = matchData.group(1)
        if normalization is not None:
            reps = normalization[size]
            data["Duration"][len(data["Duration"]) - 1] /= reps
        data["Data size"].append(int(size))
        data["MFLOPS"].append(float(matchData.group(2)))
        data["Mode"].append(mode)
        data["EPC"].append(epc)

def plotTriad(args):
    """
    Plot the triad mflops values.
    Testing with 2^26 as value.
    """

    files = args.triad_data
    benchmark = None
    size = "2"
    for file in files:
        direct = re.findall("_e", file)
        mode = "Baseline"
        if len(direct) > 0:
            mode = "Enclave"
        csv = pd.read_csv(file)
        csv["Mode"] = mode
        
        size = re.findall("_(\d+)g", file)
        if len(size) > 0:
            size = size[0]
            csv["Size"] = size
        # print(csv)
        if benchmark is None:
            benchmark = pd.DataFrame(csv)
        else:
            benchmark = pd.concat([benchmark, csv], ignore_index=True)

    # data = pd.DataFrame(benchmark)
    data = benchmark

    fig,ax = plt.subplots()
    ax2 = ax.twinx()

    sns.lineplot(data=data, x="Dataset size", y="MFLOPS", ax=ax, marker='o', hue="Mode", palette="tab10")

    custom_pal = {"Enclave":"tab:green", "Baseline":"tab:red"}
    sns.lineplot(data=data, x="Dataset size", y="Execute Duration", ax=ax2, marker='o', hue="Mode", palette=custom_pal)

    plt.title(f"Triad performance")
    ax.grid("both")
    # Start with 0 at y-axis
    ax.set_ylim(ymin=0)
    ax2.set_ylim(ymin=0)
    ax.set_xscale("log")
    ax.set_xlabel("Vector size")
    ax2.set_ylabel("Execution Duration (s)")
    ax.legend(title="MFLOPs", loc="lower left", bbox_to_anchor=(0, 0.2))
    ax2.legend(title="Duration", loc="lower left", bbox_to_anchor=(0, 0.05))

    xticks = data["Dataset size"].unique()
    ax.set_xticks(xticks)
    plt.minorticks_off()

    def log2_base(y, pos):
        return r'2$^{{ {:d} }}$'.format(int(np.log2(y)))
    ax.xaxis.set_major_formatter(FuncFormatter(log2_base))

    exportToPdf(fig, args.output)

def plotTriadComp(args):
    """
    Plotting the comparison of the different enclave sizes.
    """

    files = args.triad_data
    files.extend(args.triad_comp)
    benchmark = None
    epc = "2"
    for file in files:
        direct = re.findall("_e", file)
        mode = "Baseline"
        if len(direct) > 0:
            mode = "Enclave"
        csv = pd.read_csv(file)
        csv["Mode"] = mode
        
        epc = re.findall("_(\d+)g", file)
        if len(epc) > 0:
            epc = epc[0]
            csv["EPC"] = epc
        # print(csv)
        if benchmark is None:
            benchmark = pd.DataFrame(csv)
        else:
            benchmark = pd.concat([benchmark, csv], ignore_index=True)

    data = benchmark

    fig,ax = plt.subplots()

    enclave = data[data["Mode"] == "Enclave"].reset_index()
    baseline = data[data["Mode"] == "Baseline"].reset_index()
    data = pd.concat([baseline, enclave], ignore_index=True)
    data["Scaling"] = (enclave["MFLOPS"] / baseline["MFLOPS"]) * 100

    
    custom_pal = {"2":"indigo", "4":"gold", "8":"green", "16":"maroon"}
    sizes = [2,4,8,16]
    for i in range(4):
        sns.lineplot(data=enclave[enclave["EPC"] == f"{sizes[i]}"], x="Dataset size", y="MFLOPS", ax=ax, marker="o", palette="tab10", label=f"{sizes[i]}")
    
    # for i in range(4):
    #     sns.lineplot(data=baseline[baseline["Size"] == f"{sizes[i]}" ], x="Dataset size", y="MFLOPS", ax=ax, marker="s", linestyle="--", palette=custom_pal, legend=None, label=f"{sizes[i]} Baseline")

    plt.title(f"Triad EPC comparison (SGX2)")
    ax.grid("both")
    ax.set_ylim(ymin=0)
    ax.set_xscale("log")
    ax.set_ylabel("MFLOPS")
    ax.set_xlabel("Vector size")
    ax.legend(title="EPC (in GB)", loc="best")

    xticks = enclave["Dataset size"].unique()
    ax.set_xticks(xticks)
    plt.minorticks_off()

    def log2_base(y, pos):
        return r'2$^{{ {:d} }}$'.format(int(np.log2(y)))
    ax.xaxis.set_major_formatter(FuncFormatter(log2_base))

    # Saving
    exportToPdf(fig, args.output)

    # ---------------------------
    # Scaling
    # ---------------------------
    fig,ax = plt.subplots()

    sns.lineplot(data=data, x="Dataset size", y="Scaling", ax=ax, marker='o', hue="EPC", palette="tab10")

    plt.title(f"Triad Scaling of Performance")
    ax.grid("both")
    ax.set_ylim(ymin=0)
    ax.set_xscale("log")
    ax.set_xlabel("Vector size")
    ax.set_ylabel("Enclave / Baseline Performance [%]")
    ax.legend(title="EPC (in GB)", loc="best")

    xticks = enclave["Dataset size"].unique()
    ax.set_xticks(xticks)
    plt.minorticks_off()
    ax.xaxis.set_major_formatter(FuncFormatter(log2_base))

    # Saving
    dirPath, fileName = os.path.split(args.output)
    fileName = fileName[:-4] + "_scale.pdf"
    filePath = os.path.join(dirPath, fileName)

    exportToPdf(fig, filePath)

    fig,ax = plt.subplots()

    data = data[data["Dataset size"] > 4194304]

    sns.lineplot(data=data, x="Dataset size", y="Scaling", ax=ax, marker='o', hue="EPC", palette="tab10")

    plt.title(f"Triad scaling of enclave vs. baseline (zoomed)")
    ax.grid("both")
    ax.set_ylim(ymin=0)
    # ax.set_xscale("log")
    ax.set_ylabel("Enclave MFLOPs / Baseline MFLOPs")
    ax.legend(title="EPC (in GB)", loc="best")

    # Saving
    dirPath, fileName = os.path.split(args.output)
    fileName = fileName[:-4] + "_zoomed.pdf"
    filePath = os.path.join(dirPath, fileName)
    exportToPdf(fig, filePath)

if __name__ == '__main__':

    parser = ArgumentParser(description='Generate Triad MFLOPs charts')
    parser.add_argument('--triad-data', action="append", default=[], help="The triad benchmark data")
    parser.add_argument("--triad-comp", action="append", default=[], help="The baseline triad data for comparison")
    parser.add_argument('--output', type=str, default="triad.pdf")


    args = parser.parse_args()

    if len(args.triad_comp) > 0:
        plotTriadComp(args)
        exit(0)

    if len(args.triad_data) > 0:
        plotTriad(args)