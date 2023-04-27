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

#ifndef __ENGINE_RECVSENDUDPPACKETS_H_
#define __ENGINE_RECVSENDUDPPACKETS_H_

#include <omnetpp.h>

#include "inet/queueing/sink/PassivePacketSink.h"
#include "inet/queueing/contract/IActivePacketSource.h"

using namespace omnetpp;
using namespace inet;

class RecvSendUdpPacketS : public inet::queueing::PassivePacketSink, public virtual inet::queueing::IActivePacketSource
{
  protected:
    int num_packets; // see numPackets parameter; number of packets to be processed
    double delay; // see delay parameter; delay between wakeup and txtime/ deadline
    bool tsnd; // usage of tsnd mode
    bool tsn; // usage of tsn mode

    bool attachCreationTimeTag = false;
    bool attachIdentityTag = false;
    bool attachDirectionTag = false;

    cGate *outputGate = nullptr;
    IPassivePacketSink *consumer = nullptr;

  protected:
    virtual void initialize(int stage) override;
    virtual void handleMessage(cMessage *msg) override;

    void scheduleConsumptionTimer() override;
    virtual void consumePacket(Packet *packet) override;
    virtual void producePacket(const char* packetName, uint8_t* buf);
    Packet *createPacket(const char* packetName, uint8_t* buf);
    Ptr<Chunk> createPacketContent(uint8_t* buf);
    void delayP(Packet *packet);
    void produceP(Packet *packet);

  public:
    virtual void handleCanPushPacketChanged(cGate *gate) override;
    virtual void handlePushPacketProcessed(Packet *packet, cGate *gate, bool successful) override;

    virtual IPassivePacketSink *getConsumer(cGate *gate) override { return consumer; }
    virtual bool supportsPacketPushing(cGate *gate) const override { return PassivePacketSink::supportsPacketPushing(gate) || outputGate == gate; }
};

#endif
