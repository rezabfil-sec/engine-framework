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

package engine.networks.nodes;

import inet.node.ethernet.EthernetLink;

import engine.networks.base.EngineNetworkBase;
import engine.node.EngineNode;

//
// Provides the nodes that are available in the testbed. Network nodes are
// realized via the EngineNode module. Defines a submodule for each node based
// on a respective bool variable has<hostname> (default is false). Sets node 
// specific variables, like type (VCC or ZGW) and individual interface mac
// addresses according to the respective host_vars file.
//   
// This network does not specify connections. Networks that specify connections
// should extend this class. Connections shoud be conditional based on the
// has<hostname> variables or existence of the respective submodules, or the
// has<hostname> variables should be set to true for the network. 
//
network EngineNetworkNodes extends EngineNetworkBase
{
    parameters:
        bool hasMilhouse = default(false);
        bool hasNed = default(false);
        bool hasMarge = default(false);
        bool hasHomer = default(false);
        bool hasOtto = default(false);
        bool hasRalph = default(false);
        bool hasAbe = default(false);
        bool hasTodd = default(false);
        bool hasMaggie = default(false);
        bool hasNelson = default(false);
        bool hasRod = default(false);
        bool hasBart = default(false);
    submodules:
        milhouse: EngineNode if hasMilhouse {
            @display("p=400,250");
            type = "ZGWI210";
            switch.eth[1].address = "6cb311525468";
            switch.eth[2].address = "6cb311525469";
            switch.eth[3].address = "6cb31152549a";
            switch.eth[4].address = "6cb31152549b";
        }
        ned: EngineNode if hasNed {
            @display("p=650,200");
            type = "VCC";
            switch.eth[1].address = "6cb3115253f8";
            switch.eth[2].address = "6cb3115253f9";
            switch.eth[3].address = "6cb3115253fa";
            switch.eth[4].address = "6cb3115253fb";
            switch.eth[5].address = "3cecef6a7ac4";
            switch.eth[6].address = "3cecef6a7ac5";
            //#switch.eth[7].address = "3cecef6a7ac6";
            switch.eth[7].address = "3cecef6a7ac7";
            switch.eth[8].address = "3cecef6a7ac8";
            switch.eth[9].address = "3cecef6a7ac9";
            switch.eth[10].address = "3cecef6a7aca";
            switch.eth[11].address = "3cecef6a7acb";
        }
        marge: EngineNode if hasMarge {
            @display("p=800,250");
            type = "ZGWI210";
            switch.eth[1].address = "6cb3115254c0";
            switch.eth[2].address = "6cb3115254c1";
            switch.eth[3].address = "6cb3115254c2";
            switch.eth[4].address = "6cb3115254c3";
        }
        homer: EngineNode if hasHomer {
            @display("p=900,250");
            type = "ZGWI210";
            switch.eth[1].address = "6cb31152554c";
            switch.eth[2].address = "6cb31152554d";
            switch.eth[3].address = "6cb31152554e";
            switch.eth[4].address = "6cb31152554f";
        }
        otto: EngineNode if hasOtto {
            type = "ZGWI210";
            @display("p=500,250");
            switch.eth[1].address = "6cb311525474";
            switch.eth[2].address = "6cb311525475";
            switch.eth[3].address = "6cb311525476";
            switch.eth[4].address = "6cb311525477";
        }
        ralph: EngineNode if hasRalph {
            @display("p=350,300");
            type = "ZGWI210";
            switch.eth[1].address = "6cb311525434";
            switch.eth[2].address = "6cb311525435";
            switch.eth[3].address = "6cb311525436";
            switch.eth[4].address = "6cb311525437";
        }
        abe: EngineNode if hasAbe {
            @display("p=550,300");
            type = "ZGWI210";
            switch.eth[1].address = "6cb3115253fc";
            switch.eth[2].address = "6cb3115253fd";
            switch.eth[3].address = "6cb3115253fe";
            switch.eth[4].address = "6cb3115253ff";
        }
        todd: EngineNode if hasTodd {
            @display("p=650,300");
            type = "VCC";
            switch.eth[1].address = "6cb311525490";
            switch.eth[2].address = "6cb311525491";
            switch.eth[3].address = "6cb311525492";
            switch.eth[4].address = "6cb311525493";
            switch.eth[5].address = "3cecef6a6d58";
            switch.eth[6].address = "3cecef6a6d59";
            //#switch.eth[7].address = "3cecef6a6d5a";
            switch.eth[7].address = "3cecef6a6d5b";
            switch.eth[8].address = "3cecef6a6d5c";
            switch.eth[9].address = "3cecef6a6d5d";
            switch.eth[10].address = "3cecef6a755a";
            switch.eth[11].address = "3cecef6a755d";
        }
        maggie: EngineNode if hasMaggie {
            @display("p=500,350");
            type = "ZGWI210";
            switch.eth[1].address = "6cb311525470";
            switch.eth[2].address = "6cb311525471";
            switch.eth[3].address = "6cb311525472";
            switch.eth[4].address = "6cb311525473";
        }
        nelson: EngineNode if hasNelson {
            @display("p=400,350");
            type = "ZGWI210";
            switch.eth[1].address = "6cb31152545c";
            switch.eth[2].address = "6cb31152545d";
            switch.eth[3].address = "6cb31152545e";
            switch.eth[4].address = "6cb31152545f";
        }
        rod: EngineNode if hasRod {
            @display("p=650,400");
            type = "VCC";
            switch.eth[1].address = "6cb311525498";
            switch.eth[2].address = "6cb311525499";
            switch.eth[3].address = "6cb31152549a";
            switch.eth[4].address = "6cb31152549b";
            switch.eth[5].address = "3cecef466170";
            switch.eth[6].address = "3cecef466171";
            //#switch.eth[7].address = "3cecef466172";
            switch.eth[7].address = "3cecef466173";
            switch.eth[8].address = "3cecef466174";
            switch.eth[9].address = "3cecef466175";
            switch.eth[10].address = "3cecef4669b6";
            switch.eth[11].address = "3cecef4669b7";
        }
        bart: EngineNode if hasBart {
            @display("p=900,350");
            type = "ZGWI210";
            switch.eth[1].address = "6cb311525500";
            switch.eth[2].address = "6cb311525501";
            switch.eth[3].address = "6cb311525502";
            switch.eth[4].address = "6cb311525503";
        }
}
