//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Lesser General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
// 
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Lesser General Public License for more details.
// 
// You should have received a copy of the GNU Lesser General Public License
// along with this program.  If not, see http://www.gnu.org/licenses/.
// 

#include "SendUdpPacketSource.h"

#include <string.h>

Define_Module(SendUdpPacketSource);

void SendUdpPacketSource::initialize(int stage)
{
    ActivePacketSource::initialize(stage);
    if (stage == INITSTAGE_LOCAL) {
        num_packets = par("numPackets");
        delay = par("delay");
        tsnd = strcmp("tsnd", par("mode"));
    }
}

void SendUdpPacketSource::handleMessage(cMessage *message)
{
    if(numProcessedPackets < num_packets)
        ActivePacketSource::handleMessage(message);
    else
        delete message;
}

Ptr<Chunk> SendUdpPacketSource::createPacketContent() const
{
    // code adapted from inet/queueing/base/PacketSourceBase.cc, PacketSourceBase::createPacketContent
    auto packetLength = b(packetLengthParameter->intValue());

    clocktime_t actual_ts = getClockTime();
    uint64_t actual_time = (uint64_t) actual_ts.inUnit(SIMTIME_NS);
    clocktime_t txts = actual_ts + (tsnd ? delay : 0);
    uint64_t txtime = (uint64_t) txts.inUnit(SIMTIME_NS);
    static unsigned char tx_buffer[256];
    memset(tx_buffer, 'a', sizeof(tx_buffer));
    memcpy(tx_buffer, &txtime, sizeof(uint64_t));
    memcpy(tx_buffer + 8, &numProcessedPackets, sizeof(int));
    memcpy(tx_buffer + 12, &actual_time, sizeof(uint64_t));

    static int total = 0;
    const auto& packetContent = makeShared<BytesChunk>();
    std::vector<uint8_t> bytes;
    bytes.resize(B(packetLength).get());
    for (int i = 0; i < (int)bytes.size(); i++) {
        bytes[i] = tx_buffer[i];
    }
    total += bytes.size();
    packetContent->setBytes(bytes);
    return packetContent;
}
