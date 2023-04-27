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

package engine.services.udpapp;

import inet.applications.udpapp.UdpApp;
import inet.queueing.contract.IActivePacketSource;
import inet.queueing.contract.IPassivePacketSink;

import engine.services.recv_send_udp.RecvSendUdpPacketS;

//
// Modifies UdpApp by using a single module (RecvSendUdpPacketS) as both, sink
// and source. Defines the submodule and reconnects gates.
//
module RecvSendUdpApp extends UdpApp
{
    parameters:
        sink.typename = "";
        source.typename = "";
    submodules:
        //
        // RecvSendUdpPacketS for producing a (delayed) response per received
        // request. Implements IActivePacketSource and IPassivePacketSink.
        //
        s: RecvSendUdpPacketS {
            parameters:
                @display("p=350,150");
        }
    connections:
        s.out --> {@reconnect;} --> tagger.in;
        measurementRecorder.out --> {@reconnect;} --> s.in;
}
