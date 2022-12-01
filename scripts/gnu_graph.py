#!/usr/bin/python3

# Create a gnuplot graph
# Single place to modify the look of generated graphs
# (key position, output file format and size, line styles, etc.)

import os

# outfile: path to output file must end with png
# title: words at the top of the graph
# parameters: dictionary with the lines to draw e.g.
# parameters = { "x": "rx Timestamps [s]", "y1": "Throughput [mbit/s]",
#     "y2": "Packets [num]", "vars":
#         [{'file': '/data/iperf.csv', 'title': 'throughput', 'values': '2:3', 'axes': 'x1y1', 'style': '1' },
#         { 'file': '/data/iperf.csv', 'title': 'sent-packets', 'values': '2:4', 'axes': 'x1y2', 'style': '2' },
#         { 'file': '/data/iperf.csv', 'title': 'lost-packets', 'values': '2:5', 'axes': 'x1y2', 'style': '3' }]
# }

def create(outfile, title, parameters):
    # file paths
    plotfile = outfile.replace(".png", ".plot")

    # Write gnuplot file
    with open(plotfile, "w") as gfile:
        cmd = ('set title "%s"\n'
            'set key outside below right vertical height 3\n'
            'set terminal png size 1920, 1080 font ",15"\n'
            'set xlabel "%s"\n'
            'set ylabel "%s"\n'
            'set grid ytics\n'
            'set ytics nomirror\n'
            'set y2label "%s"\n'
            'set y2tics nomirror\n'
            'set output "%s"\n'
            'set style line 1 lc rgb "#9e2915" pt 7 ps 0.8\n'
            'set style line 2 lc rgb "#10800a" pt 2 ps 0.8\n'
            'set style line 3 lc rgb "#1321bd" pt 4 ps 0.8\n'
            'set style line 4 lc rgb "#d1ad0f" pt 3 ps 0.8\n'
            'set style line 5 lc rgb "#13bda0" pt 5 ps 0.8\n'
            'plot ' % (title, parameters['x'], parameters['y1'], parameters['y2'], outfile))

        for param in parameters['vars']:
            cmd += '"%s" using %s with linespoints ls %s title "%s" axes %s, ' % (param['file'],
                param['values'], param['style'], param['title'], param['axes'])
        cmd += '\n'
        gfile.write(cmd)
    os.system("gnuplot %s" % plotfile)

    # return the generated files
    return [plotfile, outfile]
