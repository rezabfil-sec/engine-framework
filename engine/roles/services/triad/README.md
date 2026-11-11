# Triad Benchmark Service
Benchmark authored by Justus von der Beek.
Adapted to EnGINE by Tizian Leonhardt.


## Manual
Usage in stack:
```yaml
- { name: 'triad', vector_size?: 65536, repetitions?: 4096, plot?: true }
```

Notes:
- `vector_size` is the size of the vector in bytes (optional, default: 65536)
- `repetitions` is the number of repetitions (optional, default: 4096)
- `plot` enables or disables plotting (optional, default: true)