#!/usr/bin/env python3

import os
import argparse

parser = argparse.ArgumentParser(description='Extract IO stats from tcpdump output')
parser.add_argument('-i', '--input', help='Input file', required=True)
parser.add_argument('-o', '--output', help='Output file', required=True)
parser.add_argument('-t', '--interval', help='Interval in seconds', default=1)
args = parser.parse_args()

if not os.path.exists('/usr/bin/tshark'):
    print("tshark not found")
    exit(1)

if not os.path.exists(args.input):
    print("Input file not found")
    exit(1)

if os.path.exists(args.output):
    os.remove(args.output)

# output to tempfile
tmpfile = args.output + '.tmp'
os.system("tshark -r {} -q -z io,stat,{} -Q > {}".format(args.input, args.interval, tmpfile))

def get_interval(line):
    return line.split('<>')[0].replace('|', '').strip()

def get_frames(line):
    return line.split('|')[2].strip()

def get_bytes(line):
    return line.split('|')[3].strip()

# parse to CSV -- this is an example of the output 
# ====================================
# | IO Statistics                    |
# |                                  |
# | Duration: 41.6 secs              |
# | Interval:  0.1 secs              |
# |                                  |
# | Col 1: Frames and bytes          |
# |----------------------------------|
# |              |1                  |
# | Interval     | Frames |   Bytes  |
# |----------------------------------|
# |  0.0 <>  0.1 |     16 |     1800 |
# |  0.1 <>  0.2 |     14 |     1440 |
# |  0.2 <>  0.3 |     52 |    90968 |
# |  0.3 <>  0.4 |     11 |     1378 |
# |  0.4 <>  0.5 |      1 |       66 |
# |  0.5 <>  0.6 |      0 |        0 |
# |  0.6 <>  0.7 |      0 |        0 |
# |  0.7 <>  0.8 |      0 |        0 |
# |  0.8 <>  0.9 |      0 |        0 |
# |  0.9 <>  1.0 |      0 |        0 |
# |  1.0 <>  1.1 |      0 |        0 |
# |  1.1 <>  1.2 |      0 |        0 |
# |  1.2 <>  1.3 |      0 |        0 |
# |  1.3 <>  1.4 |      0 |        0 |

with open(tmpfile, 'r') as f:
    lines = f.readlines()
    with open(args.output, 'w') as o:
        o.write("time,frames,bytes\n")
        for line in lines[12:-1]:
            interval = get_interval(line)
            frames = get_frames(line)
            bytes = get_bytes(line)
            o.write("{},{},{}\n".format(interval, frames, bytes))
