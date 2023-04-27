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

package engine.services.iperf;

import inet.queueing.source.ActivePacketSource;

//
// This module extends ActivePacketSource by a stop time parameter and adds
// iPerf3 like packet contents.
//
simple Iperf3LikePacketSource extends ActivePacketSource
{
    parameters:
        double productionStopTime @unit(s) = default(86400s); // Indicates when production should stop. Zero or negative means no stop.
        packetRepresentation = "byteCount";
        @class(Iperf3LikePacketSource);
}
