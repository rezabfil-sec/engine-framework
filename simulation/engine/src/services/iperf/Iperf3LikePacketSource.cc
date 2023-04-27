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

#include <arpa/inet.h>

#include "Iperf3LikePacketSource.h"

Define_Module(Iperf3LikePacketSource);

void Iperf3LikePacketSource::initialize(int stage)
{
    ActivePacketSource::initialize(stage);
    if (stage == INITSTAGE_LOCAL)
        stopTime = par("productionStopTime");
}

void Iperf3LikePacketSource::handleMessage(cMessage *message)
{
    if(stopTime <= 0 || getClockTime() <= stopTime)
        ActivePacketSource::handleMessage(message);
    else
        delete message;
}

Ptr<Chunk> Iperf3LikePacketSource::createPacketContent() const
{
    // code adapted from inet/queueing/base/PacketSourceBase.cc, PacketSourceBase::createPacketContent
    auto packetLength = b(packetLengthParameter->intValue());

    clocktime_t time = getClockTime(); // or use (simtime_t) simTime()
    uint64_t time_in_seconds = time.inUnit(SIMTIME_S);
    uint32_t timestamp_seconds = htonl((int32_t)time_in_seconds);
    uint64_t time_in_microseconds = time.inUnit(SIMTIME_US);
    uint32_t timestamp_microseconds = htonl((uint32_t)time_in_microseconds - (uint32_t)1000000 * timestamp_seconds);
    uint32_t seq_num = htonl((uint32_t)numProcessedPackets);
    static unsigned char tx_buffer[12];
    memcpy(tx_buffer, &timestamp_seconds, sizeof(uint32_t));
    memcpy(tx_buffer + 4, &timestamp_microseconds, sizeof(uint32_t));
    memcpy(tx_buffer + 8, &seq_num, sizeof(int));

    static int total = 0;
    const auto& packetContent = makeShared<BytesChunk>();
    std::vector<uint8_t> bytes;
    bytes.resize(B(packetLength).get());
    for (int i = 0; i < (int)bytes.size(); i++) {
        if (i < (sizeof(tx_buffer)/sizeof(tx_buffer[0]))) {
            bytes[i] = tx_buffer[i];
        } else {
            int packetData = packetDataParameter->intValue();
            bytes[i] = packetData == -1 ? (total + i) % 256 : packetData;
        }
    }
    total += bytes.size();
    packetContent->setBytes(bytes);
    return packetContent;
}
