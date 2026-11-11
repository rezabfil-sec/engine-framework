#!/usr/bin/env python3
import sys

headerOverhead = 20 + 4 + 14 + 4 + 20 + 8 + 32 # Overhead: physical + CRC + Linklayer + VLAN Tag + Network + Transport

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
    stackStringClient = '- { name: iperf, role: client, flow: ' + str(flow) + ', port: ' + str(port) + ', prio: ' + str(priority) + ', limit: ' + str(bitrate) + ', size: ' + str(payloadSize) + ', level: 1, signal: yes, udp: yes}'
    # print(' ', stackStringClient)
    # print('Service for server:')
    stackStringServer = '- { name: iperf, role: server, flow: ' + str(flow) + ', port: ' + str(port) + ', level: 0, signal: yes }'
    # print(' ', stackStringServer)
    # print('Tcpdump service for client and server:')
    stackStringClientServerTcpdump = '- { name: tcpdump, flow: [' + str(flow) + '], size: 64, filter: \"udp dst port ' + str(port) + '\", file: \"p' + str(port) + '\", level: 0, signal: no}'
    # print(' ', stackStringClientServerTcpdump)
    return stackStringClient, stackStringServer, stackStringClientServerTcpdump, payloadSize, bitrate


print(prepareIperfStack(1250+32, 100, 1, 1004, 3))
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