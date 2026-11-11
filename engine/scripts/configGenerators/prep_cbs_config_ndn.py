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

def prepareCBSqdiscInfo(srInfoDict, genInfoDict):
    cbsConfigs = {}
    for entry in srInfoDict:
        cbsConfigs[entry] = {}
        srInfoDict[entry]['assignedBitrate'] = srInfoDict[entry]['maxFrameSize']*8/(srInfoDict[entry]['interval']*1e-3)
        bwFrac = srInfoDict[entry]['assignedBitrate'] / genInfoDict['portTransmitRate']
        cbsConfigs[entry]['idleSlope'] = calculateIdleSlope(bwFrac, genInfoDict['portTransmitRate'])
        cbsConfigs[entry]['sendSlope'] = calculateSendSlope(bwFrac, genInfoDict['portTransmitRate'])
        cbsConfigs[entry]['loCredit'] = calculateLoCredit(srInfoDict[entry]['maxFrameSize'], bwFrac, genInfoDict['portTransmitRate'])
        cbsConfigs[entry]['hiCredit'] = calculateHiCredit(entry, srInfoDict, genInfoDict, cbsConfigs)
    # print(cbsConfigs)
    return cbsConfigs

def convertToEnGINESettings(cbsConfigs):
    readyConfigs = {}
    for cbsConf in cbsConfigs:
        config = cbsConfigs[cbsConf]
        newConfig = {}
        newConfig['idle'] = config.pop('idleSlope')
        newConfig['send'] = config.pop('sendSlope')
        newConfig['high'] = config.pop('hiCredit')
        newConfig['low'] = config.pop('loCredit')
        readyConfigs[cbsConf] = newConfig
    return readyConfigs

def printConfig(readyConfigs):
    readyDict = {}
    for conf in readyConfigs:
        config = readyConfigs[conf]
        printStr = ""
        for elem in config:
            printStr += elem + ': \'' + str(config[elem]) + '\', '
        readyDict[conf] = printStr
    return readyDict


# NDN Interests
srInfoDict = {1 : {'maxFrameSize' : 64+24+100,   # frame size in bytes (padded interest size including MAC header and 802.1QTag + PHY/CRC)
                     'interval' : 250,       # interval in us
                     'priorities' : [3]},    # priority
              2 : {'maxFrameSize' : 64+24+100,   # frame size in bytes
                     'interval' : 250,       # interval in us
                     'priorities' : [2]}
             }
genInfoDict = {'maxFrameSize' : 1542,             # best effort frame size in bytes
               'portTransmitRate' : 1000000}      # link capacity in kbps

print('Interests:\n', printConfig(convertToEnGINESettings(prepareCBSqdiscInfo(srInfoDict, genInfoDict))))

# NDN Data
srInfoDict = {1 : {'maxFrameSize' : 1250+14+4+80+24+100,    # frame size in bytes (data size + ETH header + 802.1Q Tag + NDN header (presumed name length included) + PHY/CRC)
                     'interval' : 250,                # interval in us
                     'priorities' : [3]},             # priority
              2 : {'maxFrameSize' : 1250+18+80+24+100,    # frame size in bytes
                     'interval' : 250,                # interval in us
                     'priorities' : [2]}
             }
genInfoDict = {'maxFrameSize' : 1542,             # best effort frame size in bytes
               'portTransmitRate' : 1000000}      # link capacity in kbps

print('Data:\n', printConfig(convertToEnGINESettings(prepareCBSqdiscInfo(srInfoDict, genInfoDict))))