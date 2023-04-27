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

package engine.services.recv_send_udp;

import inet.queueing.contract.IActivePacketSource;
import inet.queueing.sink.PassivePacketSink;

//
// Extends PassivePacketSink with functionality for replying to received
// packets. Processes a specified number of packets. Responses are created
// based on the contents of received packets, and new timestamps are added, 
// and, based on the used mode, packets get sent immediately or they are
// delayed.
//
// Since the linux tsn features, i.e. socket options and the ETF qdisc, aren't
// available, this module does only realize the programs to a certain extent.
// For mode tsn, packets get delayed by the specified time and the delay is
// added to the timestamp representing the intended txtime. For mode tsnd,
// packets do not get delayed but the delay is added to the timestamp
// representing the intended deadline.
//
// Takes signals, statistics and some parameters from PacketSourceBase.ned,
// ActivePacketSourceBase.ned and ActivePacketSource.ned
//
simple RecvSendUdpPacketS extends PassivePacketSink like IActivePacketSource
{
    parameters:
        string mode @enum("tsn", "tsnd", "none") = default("none"); // mode of operation (tsn mode, tsnd mode, none)
        int numPackets = default(60000); // indicates the number of packets to be replied
        double delay @unit(s) = default(200us); // delay between pushing a packet and its intended txtime / deadline
        clockModule = default("^.^.^.switch.clock");
        consumptionInterval = 0s;
        scheduleForAbsoluteTime = true;
        bool attachCreationTimeTag = default(true);
        bool attachIdentityTag = default(true);
        bool attachDirectionTag = default(true);
        displayStringTextFormat = default("processed %p pk (%l)");
        @display("i=block/star");
        @class(RecvSendUdpPacketS);
        @signal[packetPushed](type=inet::Packet);
        @signal[packetCreated](type=inet::Packet);
        @statistic[packets](title="packets"; source=packetPushed; record=count; unit=pk);
        @statistic[packetLengths](title="packet lengths"; source=packetLength(packetPushed); record=sum,histogram,vector; unit=b; interpolationmode=none);
        @statistic[dataRate](title="data rate"; source=throughput(packetPushed); record=vector; unit=bps; interpolationmode=linear);
    gates:
        output out @labels(push);
}
