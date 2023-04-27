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

package engine.node;

import inet.node.ethernet.EthernetLink;

//
// Ethernet link with a length of 1.5m (for delay).
//
channel EngineLink extends EthernetLink {
    length = 1.5m;
}

//
// 1 Gbps datarate link.
//
channel EngineLink1_0G extends EngineLink
{
    @display("ls=black");
    datarate = 1000Mbps;
}

//
// 10 Gbps datarate link.
//
channel EngineLink10_0G extends EngineLink
{
    @display("ls=orange");
    datarate = 10000Mbps;
}
