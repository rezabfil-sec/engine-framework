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

package engine.services.recv_udp;

import inet.queueing.sink.PassivePacketSink;

//
// This module extends PassivePacketSink by the facility to stop consuming
// after a specific number of packets. It reads the timestamps from the packet
// contents (but currently takes no further steps).
//
simple RecvUdpPacketSink extends PassivePacketSink
{
    parameters:
        int numPackets = default(60000); // Indicates the number of packets to be received
        clockModule = default("^.^.^.switch.clock");
        consumptionInterval = 0s;
        scheduleForAbsoluteTime = true;
        @class(RecvUdpPacketSink);
}
