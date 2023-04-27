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

#ifndef __ENGINE_IPERF3LIKEPACKETSOURCE_H_
#define __ENGINE_IPERF3LIKEPACKETSOURCE_H_

#include <omnetpp.h>

#include "inet/queueing/source/ActivePacketSource.h"

using namespace omnetpp;
using namespace inet;

class Iperf3LikePacketSource : public inet::queueing::ActivePacketSource
{
protected:
    double stopTime = 0; // read from productionStopTime parameter; time when production should stop

  protected:
    virtual void initialize(int stage) override;
    virtual void handleMessage(cMessage *msg) override;
    virtual Ptr<Chunk> createPacketContent() const override;
};

#endif
