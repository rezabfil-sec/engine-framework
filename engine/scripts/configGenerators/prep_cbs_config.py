#!/usr/bin/env python3
import sys
import math

# Calculate idle slope based on IEEE Std 802.1Q-2018 8.6.8.2 d)
def calculateIdleSlope(bwFrac, portTransmitRate):
    return math.ceil(bwFrac * portTransmitRate)

# Calculate send slope based on IEEE Std 802.1Q-2018 8.6.8.2 g)
def calculateSendSlope(bwFrac, portTransmitRate):
    return math.floor(calculateIdleSlope(bwFrac, portTransmitRate) - portTransmitRate)

# Calculate hi credit based on IEEE Std 802.1Q-2018 Annex-L, equation L-3
def calculateHiCredit(entry, srInfoDict, genInfoDict, cbsConfigs):
    hiCredit = 0
    temp = list(cbsConfigs)
    tempEntry = entry
    while True:
        prevEntryIndex = temp.index(tempEntry) - 1
        if prevEntryIndex < 0:
            break
        prevEntry = temp[prevEntryIndex]
        # print(temp.index(tempEntry) - 1, tempEntry, prevEntry)
        hiCredit += (cbsConfigs[prevEntry]['hiCredit']/(-cbsConfigs[prevEntry]['sendSlope'])) + (srInfoDict[prevEntry]['maxFrameSize']/genInfoDict['portTransmitRate'])
        tempEntry = prevEntry
    hiCredit += genInfoDict['maxFrameSize']/genInfoDict['portTransmitRate']
    hiCredit *= cbsConfigs[entry]['idleSlope']
    return math.ceil(hiCredit)
    # cbsConfigs[entry]['idleSlope'] * (genInfoDict['maxFrameSize']/genInfoDict['portTransmitRate'])    

# Calculate low credit based on IEEE Std 802.1Q-2018 Annex-L, equation L-2
def calculateLoCredit(maxFrameSize, bwFrac, portTransmitRate):
    return math.floor(maxFrameSize * (calculateSendSlope(bwFrac, portTransmitRate) / portTransmitRate))

def prepConfig(devName, parentQdisc, assignedBitrate, portTransmitRate, maxFrameSize):
    bwFrac = assignedBitrate / portTransmitRate # Needed for all calculations -> Basically determines the values

    # Calculate all 4 parameters
    idleSlope = calculateIdleSlope(bwFrac, portTransmitRate)
    sendSlope = calculateSendSlope(bwFrac, portTransmitRate)
    hiCredit = calculateHiCredit(maxFrameSize, bwFrac)
    loCredit = calculateLoCredit(maxFrameSize, bwFrac, portTransmitRate)
    
    # Prepare a configuration string. May not be strictly necessary...
    configString = 'tc qdisc replace dev ' + devName + ' parent ' + parentQdisc + ' cbs \t\t\t\t\t\\ \n'
    configString += '\tidleslope ' + str(idleSlope) 
    configString += ' sendslope ' + str(sendSlope)
    configString += ' hicredit ' + str(hiCredit)
    configString += ' locredit ' + str(loCredit) + ' \t\\ \n'
    configString += '\toffload 1'
    return idleSlope, sendSlope, hiCredit, loCredit, configString

# The following MUST be in decreasing priority!!!!
# srInfoDict = {'A' : {'maxFrameSize' : 1024,       # frame size in bytes
#                      'assignedBitrate' : 7968,    # bitrate in kbps
#                      'priority' : 3},             # priority
#               'B' : {'maxFrameSize' : 1024,       # frame size in bytes
#                      'assignedBitrate' : 7968,    # bitrate in kbps
#                      'priority' : 2},             # priority
#               'C' : {'maxFrameSize' : 1024,       # frame size in bytes
#                      'assignedBitrate' : 7968,    # bitrate in kbps
#                      'priority' : 1},             # priority
#               'D' : {'maxFrameSize' : 1024,       # frame size in bytes
#                      'assignedBitrate' : 7968,    # bitrate in kbps
#                      'priority' : 0}}             # priority
# genInfoDict = {'maxFrameSize' : 1542,             # best effort frame size in bytes
#                'portTransmitRate' : 1000000,      # link capacity in kbps
#                'maxPriority' : 3}
def prepareCBSqdiscInfo(srInfoDict, genInfoDict):
    cbsConfigs = {}
    for entry in srInfoDict:
        cbsConfigs[entry] = {}
        bwFrac = srInfoDict[entry]['assignedBitrate'] / genInfoDict['portTransmitRate']
        cbsConfigs[entry]['idleSlope'] = calculateIdleSlope(bwFrac, genInfoDict['portTransmitRate'])
        cbsConfigs[entry]['sendSlope'] = calculateSendSlope(bwFrac, genInfoDict['portTransmitRate'])
        cbsConfigs[entry]['loCredit'] = calculateLoCredit(srInfoDict[entry]['maxFrameSize'], bwFrac, genInfoDict['portTransmitRate'])
        cbsConfigs[entry]['hiCredit'] = calculateHiCredit(entry, srInfoDict, genInfoDict, cbsConfigs)
    # print(cbsConfigs)
    return cbsConfigs
        
# https://github.com/torvalds/linux/blob/master/net/sched/sch_cbs.c -> hi/lo credit are in bytes on linux. 
# Thus, frame size in bytes makes sense. Then lo- amd hi-credit are in kbps, so assigned bitrate/port rate in kbps also makes sense.
# srInfoDict = {1 : {'maxFrameSize' : 1388,       # frame size in bytes
#                      'assignedBitrate' : 50000,    # bitrate in kbps
#                      'priorities' : [3]},             # priority
# srInfoDict = {1 : {'maxFrameSize' : 1250,       # frame size in bytes (1345 for 10gig?)
#                      'assignedBitrate' : 100000,    # bitrate in kbps (107600 for 10gig?)
#                      'priorities' : [3]},             # priority
#               2 : {'maxFrameSize' : 1250,       # frame size in bytes
#                      'assignedBitrate' : 100000,    # bitrate in kbps
#                      'priorities' : [2]},             # priority
#               3 : {'maxFrameSize' : 1250,       # frame size in bytes
#                      'assignedBitrate' : 100000,    # bitrate in kbps
#                      'priorities' : [1]},             # priority
#               4 : {'maxFrameSize' : 1250,       # frame size in bytes
#                      'assignedBitrate' : 100000,    # bitrate in kbps
#                      'priorities' : [0]}              # priority
#              }

# srInfoDict = {1 : {'maxFrameSize' : 1542,       # frame size in bytes (1345 for 10gig?)
#                      'assignedBitrate' : 10000,    # bitrate in kbps (107600 for 10gig?)
#                      'priorities' : [3]}#,             # priority
#             #   2 : {'maxFrameSize' : 1250,       # frame size in bytes
#             #          'assignedBitrate' : 100000,    # bitrate in kbps
#             #          'priorities' : [2]},             # priority
#             #   3 : {'maxFrameSize' : 1250,       # frame size in bytes
#             #          'assignedBitrate' : 100000,    # bitrate in kbps
#             #          'priorities' : [1]},             # priority
#             #   4 : {'maxFrameSize' : 1250,       # frame size in bytes
#             #          'assignedBitrate' : 100000,    # bitrate in kbps
#             #          'priorities' : [0]}              # priority
#              }

# genInfoDict = {'maxFrameSize' : 1542,             # best effort frame size in bytes (normally 1542) # 1610 for 10gig???
#                'portTransmitRate' : 1000000}      # link capacity in kbps # 9294196 for 10gig





# print(prepareCBSqdiscInfo(srInfoDict, genInfoDict))

def prepareTsnConfig(srInfoDict, genInfoDict):
    cbsConfigs = prepareCBSqdiscInfo(srInfoDict, genInfoDict)
    configStrings = {}
    for entry in cbsConfigs:
        cbsString = '{ mode: cbs, prio: ' + str(srInfoDict[entry]['priorities']) + ', idle: \'' + str(cbsConfigs[entry]['idleSlope']) + '\', send: \'' + str(cbsConfigs[entry]['sendSlope']) + '\', high: \'' + str(cbsConfigs[entry]['hiCredit']) + '\', low: \'' + str(cbsConfigs[entry]['loCredit']) + '\' }'
        # print(entry, ':', cbsString)
        configStrings[entry] = cbsString
    configStrings[entry+1] = '{ mode: be, prio: [\'*\'] }'
    return configStrings


###### Journal use-case -> version 1

flow1 = {'maxFrameSize' : 1500,       # frame size in bytes (1345 for 10gig?)
         'assignedBitrate' : 89152,    # bitrate in kbps (107600 for 10gig?)
         'priorities' : [3]}

flow2 = {'maxFrameSize' : 1500,       # frame size in bytes (1345 for 10gig?)
         'assignedBitrate' : 26400,    # bitrate in kbps (107600 for 10gig?)
         'priorities' : [3]}

flow3 = {'maxFrameSize' : 1250,       # frame size in bytes (1345 for 10gig?)
         'assignedBitrate' : 12820,    # bitrate in kbps (107600 for 10gig?)
         'priorities' : [2]}

genInfoDict = {'maxFrameSize' : 1542,             # best effort frame size in bytes (normally 1542)
               'portTransmitRate' : 1000000}      # link capacity in kbps

print('node-1:1 -> tsn-1')
# srInfoDict = {1 : flow3}
# print(prepareTsnConfig(srInfoDict, genInfoDict))

print('\nnode-1:3 -> tsn-2')
# srInfoDict = {1 : flow2}
# print(prepareTsnConfig(srInfoDict, genInfoDict))

print('\nnode-2:4 -> tsn-1')
# srInfoDict = {1 : flow3}
# print(prepareTsnConfig(srInfoDict, genInfoDict))

print('\nnode-3:4 -> tsn-3')
# srInfoDict = {1 : flow1,
#               2 : flow3}
# print(prepareTsnConfig(srInfoDict, genInfoDict))

print('\nnode-3:3 -> tsn-10')

print('\nnode-4:3 -> tsn-2')
# srInfoDict = {1 : flow2}
# print(prepareTsnConfig(srInfoDict, genInfoDict))

print('\nnode-5:3 -> tsn-2')
# srInfoDict = {1 : flow2}
# print(prepareTsnConfig(srInfoDict, genInfoDict))

print('\nnode-5:4 -> tsn-4')
# srInfoDict = {1 : flow1}
# print(prepareTsnConfig(srInfoDict, genInfoDict))

print('\nnode-6:1 -> tsn-2')
# srInfoDict = {1 : flow2}
# print(prepareTsnConfig(srInfoDict, genInfoDict))

print('\nnode-6:4 -> tsn-10')
#
# print(prepConfig('enp1s0', '100:1', 1e8, 1e9, 1542)[4])

# def main():
#     print('----------')
#     if len(sys.argv) < 6:
#         print('Not enough positional arguments! See code for explanation (A nice help function is WIP ;) )')
#         exit()
#     devName = sys.argv[1] # Name of the device
#     parentQdisc = sys.argv[2] # Parent qdisc for CBS
#     assignedBitrate = int(sys.argv[3]) # What bitrate to asssign in bit/s
#     portTransmitRate = int(sys.argv[4]) # The bitrate available on the port in bit/s
#     maxFrameSize = int(sys.argv[5]) # Maximal Frame Size
#     print('For device', devName, 'with parent Qdisc', parentQdisc, 'a bitrate of', str(int(assignedBitrate/1e6)) + 'Mbps out of', str(int(portTransmitRate/1e6)) + 'Mbps is to be assigned.')
#     print('Max Frame Size is', maxFrameSize)
#     retVals = prepConfig(devName, parentQdisc, assignedBitrate, portTransmitRate, maxFrameSize)
#     print('\tThe result: idleSlope', retVals[0],'sendSlope', retVals[1],'hiCredit', retVals[2],'loCredit', retVals[3])
#     print('----------\nCBS Qdisc config command for these settings:')
#     print(retVals[4])

# if __name__ == '__main__':
#     print('Called:', ' '.join(sys.argv))
#     main()