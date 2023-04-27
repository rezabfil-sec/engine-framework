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

package engine.networks.base;

//# import inet.common.scenario.ScenarioManager;
import inet.networks.base.TsnNetworkBase;

//
// Sets network specific parameters.
//
network EngineNetworkBase extends TsnNetworkBase
{
    parameters:
        configurator.addStaticRoutes = false;
        macAddressTableConfigurator.typename = "";
        macForwardingTableConfigurator.typename = ""; //# FIXME: not required for INET4.4 as is "" per default (if not hasGlobalArp)
        **.crcMode = "computed"; //# required for pcap recording
        **.fcsMode = "computed"; //# required for pcap recording
    //#submodules:
        //#scenarioManager: ScenarioManager {
        //#    @display("p=100,800;is=s");
        //#}
}
