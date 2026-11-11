# Triad Benchmark
This benchmark tests the memory bandwidth of the system.
It is based on the triad benchmark.

The following describes the manual steps to run the benchmark.

## Setup
This benchmark requires `g++` and `make` to be installed.
Run `make` to build the benchmark.

## Running
The benchmark can be executed in the following way; N is the vector size and REP is the number of repetitions.
In the example below we test with vector sizes of 32 up to 2^27 elements.

```bash
# ./triad N REP
./triad 32 134217728 triad.csv

# Result (default in triad.csv)
Dataset size,MFLOPS,Cycles,Duration,Execute Duration
32,2745.801534,4194304,0.097762,0.185388
64,3542.249483,2097152,0.075781,0.132819
128,3570.992361,1048576,0.075171,0.131740
[...]
```

## Processing
The results can be plotted with the plotting script as shown below.

```
python3 plot_triad.py --triad-data triad.csv --output triad.pdf
```