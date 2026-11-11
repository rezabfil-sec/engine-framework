# fio I/O Benchmarking Service
This service runs the fio benchmarking tool. It comes with many configuration options to
configure the pre-packaged fio configuration files. 

Please contribute your configuration files or options to make this service more useful!

Currently, the following configuration files are provided:
- `fio-seq-read': Sequential read benchmark, 1 file
- `fio-seq-write': Sequential write benchmark, 1 file
- `fio-rand-read': Random read benchmark, 1 file
- `fio-rand-write': Random write benchmark, 1 file
- `fio-rw-seq': Sequential read/write benchmark (50/50 split), 1 file

## Manual
Usage in stack:
```yaml
- { name: 'fio', fio_config: 'config-name', fio_size?: '10G', fio_location?: '/tmp/fio', fio_direct?: 0, fio_engine?: 'libaio', fio_io_depth?: 1, fio_block_size?: 1M, fio_runtime?: undefined, fio_end_fsync?: 1, drop_caches?: yes }
```

Notes:
- `fio_config` is the name of the configuration file to use. The configuration file must be present in the `templates` directory of the service
- `fio_size` is the size of the file(s) to use for the benchmark (optional, default: `10G`)
- `fio_location` is the directory to run the benchmark in; make sure to use a directory for a mount point if you want to benchmark a disk (optional, default: `/tmp/fio`)
- `fio_direct` is a boolean value that indicates whether to use direct I/O or not (optional, default: 0)
    - Note: nodes *usually* run on a RAM disk, so direct I/O is not supported unless you mount a disk on the node and run the benchmarks there
- `fio_engine` is the I/O engine to use (optional, default: `libaio`)
- `fio_io_depth` is the I/O depth to use (optional, default: 1)
- `fio_block_size` is the block size to use (optional, default: 1M)
- `fio_runtime` is the runtime of the benchmark in seconds (optional, default: undefined, which means to run the benchmark until it is killed)
- `fio_end_fsync` indicates whether all buffered data should be flushed to disk before the benchmark ends (optional, default: 1)
- `drop_caches` indicates whether to drop caches before running the benchmark (optional, default: yes)