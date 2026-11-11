# TLS Traffic Benchmark Service
Benchmark authored by Justus von der Beek.
Adapted to EnGINE by Tizian Leonhardt.

## Manual
Usage in stack for the **server**:
```yaml
- { name: 'tls_traffic_bench', mode: 'server', port?: 12341, packet_size?: 1500 }
```

Usage in stack for the **client**:
```yaml
- { name: 'tls_traffic_bench', mode: 'client', dest_name: 'node-x', port?: 12341, packet_size?: 1500,
    data_size_mb?: 2000, speed_mbps?: 10000 }
```

Notes:
- `mode` is either `server` or `client` (required)
- `dest_name` is the name of the server node (required)
- `port` is the port on which the server listens and the client connects to (optional, default: 12341)
- `packet_size` is the size of the packets in bytes (optional, default: 1500)
- `data_size_mb` is the *total* amount of data to send in MB (optional, default: 2000)
- `speed_mbps` is the network speed in Mbps (optional, default: 10000)