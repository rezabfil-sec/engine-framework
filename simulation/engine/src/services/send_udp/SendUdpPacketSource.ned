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

package engine.services.send_udp;

import inet.queueing.source.ActivePacketSource;

//
// This module realizes the send_udp_tai.c program. It extends
// ActivePacketSource by the facility to send a specific number of packets.
// Supports similar parameters the ansible service. These determine the
// initialProductionOffset and productionInterval of ActivePacketSource.
// Packets have the same structure and similar contents, i.e. available
// timestamp, as the ones produced by the programs.
//
// Since the linux tsn features, i.e. socket options and the ETF qdisc, aren't
// available, this module does only realize the programs to a certain extent.
// For mode tsn, packets get produced in the given interval after baseTime+2s
// (their intended txtime). This mode is only reasonable if there is no
// interfering traffic on the same interface, because then packets get sent
// (on the intended interface) immediately when they are produced. For mode
// tsnd, packets get produced in the given interval after baseTime+2s-delay
// (at the beginning of the delay before their intended deadline). This mode
// is only reasonable if the queueing delay cause by interfering traffic is
// smaller than the intended delay.
//
simple SendUdpPacketSource extends ActivePacketSource
{
    parameters:
        string mode @enum("tsn", "tsnd", "none") = default("none"); // operation mode (txtime mode, deadline mode, none)
        int numPackets = default(60000); // number of packets to produce
        double delay @unit(s) = default(500us); // delay between pushing a packet and its intended txtime / deadline
        double interval @unit(s) = default(1ms); // interval for packet production (ignored for mode "none")
        double baseTime @unit(s) = default(5s); // base starting time 
        clockModule = default("^.^.^.switch.clock");
        initialProductionOffset = baseTime + (mode == "tsnd" ? 2s - delay : 2s);
        productionInterval = (mode == "none" ? 1ms : interval);
        scheduleForAbsoluteTime = true;
        packetLength = 256B;
        @class(SendUdpPacketSource);
}
