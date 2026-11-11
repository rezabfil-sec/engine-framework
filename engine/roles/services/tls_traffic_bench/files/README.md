# TLS Traffic Benchmark
This benchmark is written in Go, as it ships with great networking capabilities and performance.

## Setup
This benchmark requires the installation of `golang`.
The instructions can be found on the [official website](https://go.dev/doc/install).

## Usage

```bash
go run client.go
-addr string
    The address to which we try to connect (default "10.20.114.4")
-b int
    Buffer size in byte (default 1420)
-d int
    The overall data size to send in MB (default 2000)
-debug
    Disables the TLS encryption to debug what is actually send
-l string
    The file in which key informations are stored (default "keys.log")
-m	If set the client expects the server to mirror the packages back
-n	If set the client will send an increasing packet number to the server
-nodelay
    If set it disables TCP_NODELAY and writes data immediately
-p int
    The number of packets to send. If set to "-1" the buffer size has precedence. Otherwise the packet flag has higher priority. (default -1)
-port string
    The port to which we try to connect (default "12341")
-s float
    Network speed in Mbps (default 10000)
```

For debugging and testing purposes we also include a server endpoint. 
This endpoint supports features like mirroring packets or certain polling packet sizes. 
Refer to the manual below for more information.

```bash
go run server.go
-addr string
    The address on which the servers listens (default "0.0.0.0")
-b int
    Size of buffer we receive per iteration (default 1500)
-c string
    The location of the server certificate used in the TLS connection (default "server.crt")
-debug
    If set the TLS encryption is disabled to debug the send content
-k string
    The location of the server key file used in the TLS connection (default "server.key")
-l string
    The location where the keylog of the server is stored (default "s_keys.log")
-m	If set the packages are mirrored back to the client
-port string
    The port the application listens on (default "12341")
```

## Limitations
The tool is currently not as sophisticated and therefore lacking certain features. Below is a list of features we found lacking during testing.

- Single core sending. Does only achieve ~3.5 Gbit/s on a 10 Gbit/s link.
- No traffic shaping. For latency testing this might result in artifacts as the send rate limitation might lead to only half a second of traffic on the wire followed by half a second of "silence".
- Found issues with aggregation of multiple TLS frames in a single TCP packet. However further evaluation and usage of the older socket API did not help getting rid of this problem. In cases where a 1:1 ratio of TLS frame to TCP packet is needed this might impact testing.