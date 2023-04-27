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

#include "RecvUdpPacketSink.h"

Define_Module(RecvUdpPacketSink);

void RecvUdpPacketSink::initialize(int stage)
{
    PassivePacketSink::initialize(stage);
    if (stage == INITSTAGE_LOCAL) {
        num_packets = par("numPackets");
    }
}

void RecvUdpPacketSink::handleMessage(cMessage *message)
{
    if(numProcessedPackets < num_packets)
        PassivePacketSink::handleMessage(message);
    else
        delete message;
}

void RecvUdpPacketSink::consumePacket(Packet *packet)
{
    packet->clearTags();
    packet->trim();
    auto data = packet->peekDataAsBytes();
    auto bufLength = 256;//B(data->getChunkLength()).get();
    auto buf = new uint8_t[bufLength];
    data->copyToBuffer(buf, bufLength);

    clocktime_t HW_ts = getClockTime();
    uint64_t HW_time = (uint64_t) HW_ts.inUnit(SIMTIME_NS);
    //FIXME: other HW_timestamps
    uint64_t RX_time = (unsigned long long int)(&buf[0]);
    uint64_t TX_sys = (unsigned long long int)(&buf[8]);
    uint64_t TX_srv_sys = (unsigned long long int)(&buf[16]);
    uint64_t TX_srv_hw = (unsigned long long int)(&buf[32]);
    uint64_t RX_srv = (unsigned long long int)(&buf[48]);

    PassivePacketSink::consumePacket(packet);
}
