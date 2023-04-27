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

#include "RecvSendUdpPacketS.h"

#include "inet/common/DirectionTag_m.h"
#include "inet/common/IdentityTag_m.h"
#include "inet/common/PacketEventTag.h"
#include "inet/common/TimeTag.h"

Define_Module(RecvSendUdpPacketS);

void RecvSendUdpPacketS::initialize(int stage)
{
    PassivePacketSink::initialize(stage);
    if (stage == INITSTAGE_LOCAL) {
        num_packets = par("numPackets");
        delay = par("delay");
        tsnd = strcmp("tsnd", par("mode"));
        tsnd = strcmp("tsn", par("mode"));
        attachCreationTimeTag = par("attachCreationTimeTag");
        attachIdentityTag = par("attachIdentityTag");
        attachDirectionTag = par("attachDirectionTag");
        outputGate = gate("out");
        consumer = findConnectedModule<IPassivePacketSink>(outputGate);
    }
    else if (stage == INITSTAGE_QUEUEING)
        checkPacketOperationSupport(outputGate);
}

void RecvSendUdpPacketS::handleMessage(cMessage *message)
{
    if (message->isSelfMessage()) {
        if (consumer == nullptr || consumer->canPushSomePacket(outputGate->getPathEndGate())) {
            auto packet = message->isPacket() ? check_and_cast<Packet *>(message) : static_cast<Packet *>(message->getContextPointer());
            if (!message->isPacket())
                delete message;
            simtime_t delay = simTime() - message->getSendingTime();
            insertPacketEvent(this, packet, PEK_DELAYED, delay / packet->getBitLength());
            increaseTimeTag<DelayingTimeTag>(packet, delay / packet->getBitLength(), delay);
            produceP(packet);
        }
    }
    else if (numProcessedPackets < num_packets)
        PassivePacketSink::handleMessage(message);
    else
        delete message;
}

void RecvSendUdpPacketS::scheduleConsumptionTimer()
{
    // do nothing; overrides method from PassivePacketSink which would
    // otherwise have the consumption timer scheduled when the first message
    // gets received (consumptionTimer->getArrivalModule() != nullptr)

}

void RecvSendUdpPacketS::consumePacket(Packet *packet)
{
    packet->clearTags();
    packet->trim();
    auto data = packet->peekDataAsBytes();
    auto bufLength = 256;
    auto buf = new uint8_t[bufLength];
    data->copyToBuffer(buf, bufLength);

    std::string name = std::string(packet->getName());
    auto packetName = name.c_str();
    PassivePacketSink::consumePacket(packet);
    producePacket(packetName, buf);
}

void RecvSendUdpPacketS::producePacket(const char* packetName, uint8_t* buf)
{
    auto packet = createPacket(packetName, buf);
    if (tsn)
        delayP(packet);
    else
        produceP(packet);
}

Packet *RecvSendUdpPacketS::createPacket(const char* packetName, uint8_t* buf)
{
    // code adapted from inet/queueing/base/PacketSourceBase.cc, PacketSourceBase::createPacket
    auto packetContent = createPacketContent(buf);
    if (attachCreationTimeTag)
        packetContent->addTag<CreationTimeTag>()->setCreationTime(simTime());
    if (attachIdentityTag) {
        auto identityStart = IdentityTag::getNextIdentityStart(packetContent->getChunkLength());
        packetContent->addTag<IdentityTag>()->setIdentityStart(identityStart);
    }
    auto packet = new Packet(packetName, packetContent);
    if (attachDirectionTag)
        packet->addTagIfAbsent<DirectionTag>()->setDirection(DIRECTION_OUTBOUND);
    emit(packetCreatedSignal, packet);
    return packet;
}

Ptr<Chunk> RecvSendUdpPacketS::createPacketContent(uint8_t* buf)
{
    clocktime_t sys_ts = getClockTime();
    uint64_t sys_time = (uint64_t) sys_ts.inUnit(SIMTIME_NS);
    clocktime_t HW_ts = getClockTime();
    uint64_t HW_time = (uint64_t) HW_ts.inUnit(SIMTIME_NS);
    clocktime_t tx_ts = getClockTime() + ((tsnd || tsn) ? delay : 0);
    uint64_t tx_time = (uint64_t) tx_ts.inUnit(SIMTIME_NS);

    static unsigned char buf_response[256];
    memset(buf_response, 'a', sizeof(buf_response));
    memcpy(buf_response, buf, 20);
    memcpy(buf_response + 20, &sys_time, sizeof(uint64_t));
    memset(buf_response + 28, 'b', sizeof(uint64_t));
    memcpy(buf_response + 36, &HW_time, sizeof(uint64_t));
    memset(buf_response + 44, 'c', sizeof(uint64_t));
    memcpy(buf_response + 52, &tx_time, sizeof(uint64_t));

    // code adapted from inet/queueing/base/PacketSourceBase.cc, PacketSourceBase::createPacketContent
    const auto& packetContent = makeShared<BytesChunk>();
    std::vector<uint8_t> bytes;
    bytes.resize(B(256).get());
    for (int i = 0; i < (int)bytes.size(); i++) {
        bytes[i] = buf_response[i];
    }
    packetContent->setBytes(bytes);
    return packetContent;
}

void RecvSendUdpPacketS::delayP(Packet *packet)
{
    // code adapted from inet/queueing/common/PacketDelayer.cc, PacketDelayer::pushPacket
#ifdef INET_WITH_CLOCK
    if (clock != nullptr) {
        //clocktime_t delay = par("delay");
        EV_INFO << "Delaying packet" << EV_FIELD(delay) << EV_FIELD(packet) << EV_ENDL;
        auto clockEvent = new ClockEvent("DelayTimer");
        clockEvent->setContextPointer(packet);
        scheduleClockEventAfter(delay, clockEvent);
    }
    else {
#else
    {
#endif
        //simtime_t delay = par("delay");
        EV_INFO << "Delaying packet" << EV_FIELD(delay) << EV_FIELD(packet) << EV_ENDL;
        scheduleAfter(delay, packet);
    }
}

void RecvSendUdpPacketS::produceP(Packet *packet)
{
    // code adapted from inet/queueing/source/ActivePacketSource.cc, ActivePacketSource::producePacket
    EV_INFO << "Producing packet" << EV_FIELD(packet) << EV_ENDL;
    emit(packetPushedSignal, packet);
    pushOrSendPacket(packet, outputGate, consumer);
    updateDisplayString();
}

void RecvSendUdpPacketS::handleCanPushPacketChanged(cGate *gate)
{
    // code taken from inet/queueing/common/PacketDelayer.cc, PacketDelayer::handleCanPushPacketChanged
    Enter_Method("handleCanPushPacketChanged");
    if (producer != nullptr)
        producer->handleCanPushPacketChanged(inputGate->getPathStartGate());
}

void RecvSendUdpPacketS::handlePushPacketProcessed(Packet *packet, cGate *gate, bool successful)
{
    // code taken from inet/queueing/common/PacketDelayer.cc, PacketDelayer::handlePushPacketProcessed
    Enter_Method("handlePushPacketProcessed");
    if (producer != nullptr)
        producer->handlePushPacketProcessed(packet, gate, successful);
}
