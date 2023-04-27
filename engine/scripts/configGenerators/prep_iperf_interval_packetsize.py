#!/usr/bin/env python3
import sys
# Header overhead = 70
headerOverhead = 20 + 4 + 14 + 4 + 20 + 8 # Overhead: physical + CRC + Linklayer + VLAN Tag + Network + Transport

def calcIperfSettings(packetSize, period):
    desiredPayloadSize = packetSize - headerOverhead
    pps = int(1e6/period)
    bitrate = desiredPayloadSize * 8 * pps

    # print('For packets to be sent with frameSize of', packetSize, 'and a period of', period, 'the following Iperf settings are required:')
    # print('\tPayload size:', desiredPayloadSize, 'Bytes')
    # print('\tBitrate:', bitrate, 'bits/s')
    # print('Iperf client flags (excluding IP & port): -u -l', desiredPayloadSize, '-b', bitrate)
    # print('')
    return desiredPayloadSize, bitrate

def prepareIperfStack(packetSize, period, flow, port, priority):
    # print('Service for client:')
    payloadSize, bitrate = calcIperfSettings(packetSize, period)
    stackStringClient = '- { name: iperf, role: client, flow: ' + str(flow) + ', port: ' + str(port) + ', prio: ' + str(priority) + ', limit: ' + str(bitrate) + ', size: ' + str(payloadSize) + ', level: 1, signal: yes, udp: yes, use_core: 2 }'
    # print(' ', stackStringClient)
    # print('Service for server:')
    stackStringServer = '- { name: iperf, role: server, flow: ' + str(flow) + ', port: ' + str(port) + ', level: 0, signal: yes, use_core: 2 }'
    # print(' ', stackStringServer)
    # print('Tcpdump service for client and server:')
    stackStringClientServerTcpdump = '- { name: tcpdump, flow: [' + str(flow) + '], size: 64, filter: \"udp dst port ' + str(port) + '\", file: \"p' + str(port) + '\", level: 0, signal: no }'
    # print(' ', stackStringClientServerTcpdump)
    return stackStringClient, stackStringServer, stackStringClientServerTcpdump, payloadSize, bitrate

# packetSize, period, flow, port, priority
#!!! packetSize includes header size
# print(prepareIperfStack(326, 100, 1, 6001, 3))

#### Journal - use-case

# name = 'Flow 1 SR-A 6x 1024B @ 1ms -> 1024B @ 1000um/6'
# res = prepareIperfStack(1024, 1000/6, 1, 2101, 3)

# name = 'Flow 1 SR-A 2x 1500B @ 0.6ms -> 1500B @ 300us'
# res = prepareIperfStack(1500, 300, 1, 2102, 3)

# name = 'Flow 1 BE 1x 1250B @ 100us'
# res = prepareIperfStack(1250, 100, 1, 2103, 1)

# name = 'Flow 2 SR-A 3x 1500B @ 2500us'
# res = prepareIperfStack(1500, 2500/3, 2, 2201, 3)

# name = 'Flow 2 SR-A 3x 1250B @ 2500us'
# res = prepareIperfStack(1250, 2500/3, 2, 2202, 3)

# name = 'Flow 2 BE 1x 1250B @ 100us'
# res = prepareIperfStack(1250, 100, 2, 2203, 1)

# name = 'Flow 3 SR-B 3x 1250B @ 2500us'
# res = prepareIperfStack(1250, 2500/3, 3, 2301, 2)

# name = 'Flow 3 SR-B 3x 512B @ 20000us'
# res = prepareIperfStack(512, 20000/3, 3, 2302, 2)

# name = 'Flow 3 SR-B 1x 256B @ 10000us'
# res = prepareIperfStack(256, 10000, 3, 2303, 2)

# name = 'Flow 3 BE 1x 1250B @ 100us'
# res = prepareIperfStack(1250, 100, 3, 2304, 1)

# name = 'Flow 4 BE 1x 1250B @ 100us'
# res = prepareIperfStack(1250, 100, 4, 2401, 0)

# name = 'Flow 5 BE 1x 1250B @ 100us'
# res = prepareIperfStack(1250, 100, 5, 2501, 0)

name = 'Flow 5 BE 1x 1250B @ 1000us'
res = prepareIperfStack(1250, 1000, 1, 1001, 3)

print(name)
print('       ', res[0])
print('       ', res[2], '\n')
print('       ', res[1])
print('       ', res[2])
# for x in res[0:3]:
#     print('\t',x)

# print(prepareIperfStack(1250, 100, 1, 1004, 3))
# print(prepareIperfStack(1250, 100, 1, 1003, 3))
# print(prepareIperfStack(1250, 101, 1, 1004, 3))
# print(prepareIperfStack(1250, 102, 1, 1003, 3))
# print(prepareIperfStack(1250, 103, 1, 1003, 3))
# print(prepareIperfStack(1250, 100, 1, 1003, 4))

# if __name__ == '__main__':
    # print('Called:', ' '.join(sys.argv))
    # print('----------')
    # if len(sys.argv) < 6:
    #     print('Not enough positional arguments! See code for explanation (A nice help function is WIP ;) )')
    #     exit()
    # packetSize = int(sys.argv[1]) # Size of the frame including headers in bytes
    # period = int(sys.argv[2]) # period in microseconds
    # flow = int(sys.argv[3])
    # port = int(sys.argv[4])
    # priority = int(sys.argv[5])

    # prepareIperfStack(packetSize, period, flow, port, priority)

    # calcIperfSettings(packetSize, period)