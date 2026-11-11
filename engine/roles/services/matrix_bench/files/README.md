# Computation Benchmark
This benchmark benchmarks the computation performance of the system. 
It is based on matrix multiplication.

## Setup
This benchmark requires `g++` and `make` to be installed.
Run `make` to build the benchmark.

## Running
The benchmark can be executed in the following way; N is the matrix dimension 
and REP is the number of repetitions.

```bash
# ./matrix_mul N REP [output_file]
./matrix_mul 100 3200 matrix_mul.csv

# Result (default in matrix_mul.csv)
N,Rep,MFLOPS
100,3200,2015.353
```
