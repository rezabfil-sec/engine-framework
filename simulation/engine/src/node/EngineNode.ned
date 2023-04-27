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

import inet.common.packet.recorder.PcapRecorder;
import inet.node.contract.IEthernetNetworkNode;
import inet.node.tsn.TsnDevice;
import inet.node.tsn.TsnSwitch;

//
// Realizes a testbed node of a specific type. The type (VCC, ZGWIxyz)
// indicates the capabilities of a testbed node, like the number and bitrate of
// its interfaces. A node encapsulates a device and a switch. This separation
// is to the capabilities of TsnDevice, to which application layer support is
// limited to, and TsnSwitch, to which layer two forwarding capabilities are
// limited to. There is a separate connection between device and switch for
// each flow that this node is an endpoint of. This allows to specify flow
// specific MAC address and IP address on the cooresponding interfaces of the
// device. The channels used between device and switch add no delay. The gates
// of this encapsulating module connect to the gates of the switch, which
// represent a node's NICs, while the device is purely internal without outside
// connections.

// The switch can be used for realizing the desired flows by installing
// appropriate mac address tables, and for deploying TSN configuration at its
// external interfaces. The TsnDevice can be used to host applications and map
//  application traffic to the respective priority.
//
module EngineNode
{
    parameters:
        string type @enum("VCC","ZGWI210") = default("ZGWI210"); // the type of device this node represents; determines the number and bitrate of ethernet interfaces
        int numEthInterfaces = 1 + (type == "ZGWI210" ? 4 : 11 ); // total number of ethernet interfaces for this node plus one (additional interface is for convenience only, to have interface numbers matching those in config files and graphs)
        int numFlows = default(0); // number of flows for which this node is an endpoint
    gates:
        inout ethg[numEthInterfaces]; // gates for connections to other engine nodes; connect internally to the switch's gates; gate 0 remains unused 
    types:
        //
        // Sets parameters to fixed values required for running experiments.
        //
        module EngineDevice extends TsnDevice
        {
            parameters:
                hasOutgoingStreams = true; //# enable ieee802.1q protocol encapsulation decapsulation via Ieee8021qProtocol module (required for both, senders and receivers); enables streamCoder and streamIdentifier to be used for mapping packets to streams and use appropriate pcp values

                bridging.streamIdentifier.identifier.mapping = default([{packetFilter: "*", stream: "all"}]);
                bridging.streamCoder.encoder.mapping = default([{stream: "all", pcp: 0, vlan: 2}]); //# use deafult priority 0

                eth[*].bitrate = inf bps; //# the connections between device and switch should add no delay, thus change to infinite bitrate

                ipv4.arp.typename = "GlobalArp"; //# disables the sending of ARP messages and uses automatically configured address resolution instead

                tcp.advertisedWindow = 65535; //# choose default
                tcp.mss = 1460; //# choose default
                //# tcp.tcpAlgorithmClass = "TcpReno"; //# is default
        }
        //
        // Base type for deriving switches with specifc NIC capabilities. Sets parameters to fixed values required for running experiments.
        //
        module EngineSwitch extends TsnSwitch
        {
            parameters:
                hasEgressTrafficShaping = true; //# use approprate queue (Ieee8021qTimeAwareShaper) in the maclayer
                hasTimeSynchronization = default(true); //# enable gptp

                gptp.gptpNodeType = default("SLAVE_NODE"); //# avoid 'Parameter error: Missing any master port for BRIDGE_NODE' error
                gptp.slavePort = default(""); //# avoid 'Parameter inconsistency: MASTER_NODE with slave port' error

                clock.oscillator.driftRate = default(uniform(-500ppm, 500ppm)); //# FIXME

                eth[*].bitrate = default(inf bps); //# the connections between device and switch should add no delay, thus change to infinite bitrate
                eth[*].macLayer.typename = "EthernetMacLayerWithPcapRecorder"; //# use custom mac layer for recording packets; realizes default tcpdump services
				eth[*].macLayer.queue.transmissionSelection.reverseOrder = false; //# the default setting for Ieee8021qTimeAwareShaper is 'true', thus prioritizing queues with higher index; we want to have it simple and use the unreversed order, priortizing queues with lower index, as this is what the i210 NICs do.
				eth[*].macLayer.queue.queue[*].packetCapacity = 10240;
				eth[*].macLayer.queue.transmissionGate[*].typename = default("");
				eth[*].macLayer.queue.transmissionGate[*].clockModule = "^.^.^.^.clock";
				eth[*].macLayer.queue.classifier.defaultGateIndex = default(0); //# FIXME: this would be applied to gPTP messages, I guess, thus choose preferred queue
        		eth[*].macLayer.queue.classifier.mapping = default([ //# use pcp as row and numTrafficClasses as column; in combination with the unreversed order for PriorityScheduler (submodule transmissionSelection), this should lead to the same behavior as the Linux default pfifo_fast qdisc
                    [0, 1, 1, 1, 1, 1, 1, 1],
                    [0, 0, 2, 2, 2, 2, 2, 2],
                    [0, 0, 2, 2, 2, 2, 2, 2],
                    [0, 0, 2, 2, 2, 2, 2, 2],
                    [0, 1, 1, 1, 1, 1, 1, 1],
                    [0, 0, 2, 2, 2, 2, 2, 2],
                    [0, 0, 0, 0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0, 0, 0, 0]]); 

                bridging.streamCoder.typename = "StreamCoderLayer"; //# facilitates switching with pcp and vlan tag
                bridging.streamCoder.decoder.mapping = [{interface: "eth*", stream: "all"}]; //# use trivial encoding to keep pcp and vlan values
                bridging.streamCoder.encoder.mapping = [{stream: "all"}]; //# use trivial decoding to keep pcp and vlan values
        
                macTable.agingTime=9223372s; //# otherwise values will date out; FIXME: inf doesn't work; thus choose the value from the error message when trying too large values
        }
        //
        // Realizes the interfaces for a vehicle control computer with six Intel i210 NICs, four Intel i350 NICs (of which one is not used) and two Intel x552 NICs.
        //
        module EngineSwitchLarge extends EngineSwitch
        {
            parameters:
                eth[1..6].bitrate = 1000Mbps;
                eth[7..9].bitrate = 1000Mbps;
                eth[10..11].bitrate = 10000Mbps;
				eth[1..6].macLayer.queue.numTrafficClasses = default(4);
				eth[7..11].macLayer.queue.numTrafficClasses = default(8);
		        eth[1..11].macLayer.pcapRecorder[0].snaplen = default(96); //# keep 96 bytes only
            gates:
                ethg[12];
        }
        //
        // Realizes the interfaces for a zonal gateway with four Intel i210 network cards.
        //
        module EngineSwitchI210 extends EngineSwitch
        {
            parameters:
                eth[1..4].bitrate = 1000Mbps;
				eth[1..4].macLayer.queue.numTrafficClasses = default(4);
		        eth[1..4].macLayer.pcapRecorder[0].snaplen = default(96); //# keep 96 bytes only
		    gates:
                ethg[5];
        }
		//
		// Should add no delay and unlimited datarate.
		//
        channel None extends ned.DatarateChannel
        {
            @display("ls=purple,1,dotted");
            delay = 0s;
            datarate = 0bps;
            ber = 0;
            per = 0;
        }
        //
        // EthernetMacLayer with additional submodule for recording packets.
        //
        module EthernetMacLayerWithPcapRecorder extends inet.linklayer.ethernet.modular.EthernetMacLayer
        {
            parameters:
                bool recordPcap = default(false);
                int numPcapRecorders = default(recordPcap ? 1 : 0);
            submodules:
                //
                // The default pcapRecorder submodules in NetworkInterface (extended by LayeredEthernetInterface) and EngineSwitch (extended by TsnSwitch) can both be used for capturing traffic for an individual interface. For Engine switch, the respective interface can be specified via the moduleNamePatterns parameter. With the default settings, however, the pcap files contain duplicate packets.
                // Per default, the PcapRecorder module listens for the signals 'packetSentToLower' and 'packetReceivedFromLower' emitted by the outboundEmitter and inboundEmitter submodules of EthernetMacLayer, both of class PacketEmitter (the respective signal names were set in the EthernetMacLayer module). The outboundEmitter seems to emit the 'packetSentToLower' signal twice, which leads to the redundant packets.
                // Thus a different, unique signal ahs to be found that is emitted exactly once per outgoing packet. Most modules have common ancestor modules or common signal names, which are also emitted by other submodules of EthernetMacLayer. Thus, having the pcap recorder module as submodle of the macLayer is useful, since this allows to specify (sibling) submodules via the 'moduleNamePatterns' parameter, to which the listening for signals is limited to.
                //
                pcapRecorder[numPcapRecorders]: PcapRecorder {
                    fileFormat = "pcap"; //# PcapngWriter doesn't write the per packet timestamps correctly (uses seconds | microseconds for high | low timestamp, but should actually split the 64bit value), thus use PcapWriter
                    pcapFile = default("results/" + expand("${inifile}") + "/" + expand("${configname}") + "/" + fullPath() + ".pcap"); //# stores file in scenario and experiment specific subdirectory 
                    moduleNamePatterns = "queue inboundEmitter"; //#  limit listening to queue and inboundEmitter submodules; perviously used outboundEmitter, but this will capture packets after queueing and miss the queing delay for pcap analysis
                    sendingSignalNames = "packetPushed"; //# emitted by PcpTrafficClassClassifier (classifier submodule for Ieee8021qTimeAwareShaper as queue, Ieee8021qTimeAwareShaper is used for all relevant interfaces where pcaps might be captured); is unique in our context, but there are other modules emitting this signal which don't appear as queue's submodules; previously use "packetPushedIn" for outboundEmitter; old comment: //# could also use 'packetPushedOut'; a signal of module PacketFlowBase (extended by PacketEmitter); both, inboundEmitter and outboundEmitter emit this signal
                    receivingSignalNames = "packetPushedIn"; //# use the same as for sendingSignalNames; using a different signal would lead to redundant packet captures
					//# alwaysFlush = true; //# immediately write to file
                }
        }
    submodules:
        //
        // Device for hosting applications and setting appropriate pcp values.
        //
        device: EngineDevice {
            @display("p=200,100");
        }
        //
        // Switch for realizing flows and deploying TSN configurations.
        //
        switch: <(type == "ZGWI210" ? "EngineSwitchI210" : "EngineSwitchLarge" )> like IEthernetNetworkNode {
            @display("p=100,100");
        }
    connections allowunconnected:
        //# reserve ethg[0] of switch/ this module to have gate index number match those in configuration files 
        for i=1..sizeof(switch.ethg)-1 {
            switch.ethg[i] <--> ethg[i];
        }
        for i=1..numFlows {
            switch.ethg++ <--> None <--> device.ethg++;
        }
}
