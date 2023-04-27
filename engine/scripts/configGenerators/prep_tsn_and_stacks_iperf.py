#!/usr/bin/env python3
import sys

import prep_iperf_interval_packetsize as piip
import prep_cbs_config as pcc

# print(piip.prepareIperfStack(1024, 1000, 1, 1001, 3))

def prepareStacksAndTSN(desStreams, genInfoDict, flow, sourceNode, destNode):
    iperfPort = 1001
    srInfoDict = {}
    stacksSource = []
    stacksDestination = []
    for stream in desStreams:
        srInfoDict[stream] = {}
        srInfoDict[stream]['maxFrameSize'] = desStreams[stream]['frameSize']
        srInfoDict[stream]['assignedBitrate'] = 0
        srInfoDict[stream]['priorities'] = [desStreams[stream]['priority']]
        for _ in range(desStreams[stream]['numberOfStreams']):
            iperfInfo = piip.prepareIperfStack(desStreams[stream]['frameSize'], desStreams[stream]['period'], flow, iperfPort, desStreams[stream]['priority'])
            srInfoDict[stream]['assignedBitrate'] += desStreams[stream]['frameSize']*8000/desStreams[stream]['period']
            # print(srInfoDict[stream]['assignedBitrate'])
            stacksSource.append(iperfInfo[0])
            stacksSource.append(iperfInfo[2])
            stacksDestination.append(iperfInfo[1])
            stacksDestination.append(iperfInfo[2])
            iperfPort += 1
    tsnConfig = pcc.prepareTsnConfig(srInfoDict, genInfoDict)

    print('Config for', sourceNode + ':')
    for row in stacksSource:
        print('',row)
    
    print('Config for', destNode + ':')
    for row in stacksDestination:
        print('',row)
    
    print('TSN Config :')
    print('  tsn-x:')
    print('    taprio: {}')
    print('    queues:')
    for queue in tsnConfig:
        print('     ', str(queue)+':', tsnConfig[queue])



# Should be ordered in descending priority!!!
# desStreams = {1 : {'frameSize' : 1024,
#                      'period' : 1000,
#                      'priority' : 8,
#                      'numberOfStreams' : 5},
#               2 : {'frameSize' : 1024,
#                      'period' : 6000,
#                      'priority' : 7,
#                      'numberOfStreams' : 6},
#               3 : {'frameSize' : 1500,
#                      'period' : 600,
#                      'priority' : 6,
#                      'numberOfStreams' : 2},
#               4 : {'frameSize' : 1500,
#                      'period' : 400,
#                      'priority' : 5,
#                      'numberOfStreams' : 6},
#               5 : {'frameSize' : 256,
#                      'period' : 10000,
#                      'priority' : 4,
#                      'numberOfStreams' : 8},
#               6 : {'frameSize' : 64,
#                      'period' : 200,
#                      'priority' : 3,
#                      'numberOfStreams' : 4},
#               7 : {'frameSize' : 64,
#                      'period' : 200,
#                      'priority' : 2,
#                      'numberOfStreams' : 5},
#               8 : {'frameSize' : 64,
#                      'period' : 200,
#                      'priority' : 1,
#                      'numberOfStreams' : 5}}
desStreams = {1 : {'frameSize' : 1250,          # frame size in Bytes
                     'period' : 100,            # period in microseconds
                     'priority' : 3,            # The priority for the given traffic pattern
                     'numberOfStreams' : 1},    # Number of streams for the given traffic pattern
              2 : {'frameSize' : 1250,          # frame size in Bytes
                     'period' : 100,            # period in microseconds
                     'priority' : 2,            # The priority for the given traffic pattern
                     'numberOfStreams' : 1},    # Number of streams for the given traffic pattern
              3 : {'frameSize' : 1250,          # frame size in Bytes
                     'period' : 100,            # period in microseconds
                     'priority' : 1,            # The priority for the given traffic pattern
                     'numberOfStreams' : 1}}    # Number of streams for the given traffic pattern
            #   4 : {'frameSize' : 1250,          # frame size in Bytes
            #          'period' : 200,            # period in microseconds
            #          'priority' : 0,            # The priority for the given traffic pattern
            #          'numberOfStreams' : 1}}    # Number of streams for the given traffic pattern
genInfoDict = {'maxFrameSize' : 1542,           # best effort frame size in bytes
               'portTransmitRate' : 1000000}    # link capacity in kbps

prepareStacksAndTSN(desStreams, genInfoDict, 1, 'node-1', 'node-3')