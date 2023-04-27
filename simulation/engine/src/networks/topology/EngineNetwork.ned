package engine.networks.topology;

import engine.networks.nodes.EngineNetworkNodes;
import engine.node.EngineLink*;

network EngineNetwork extends EngineNetworkNodes
{
    connections allowunconnected:
        milhouse.ethg[1] <--> EngineLink1_0G <--> nelson.ethg[4] if exists(milhouse) && exists(nelson);
        otto.ethg[1] <--> EngineLink1_0G <--> milhouse.ethg[4] if exists(otto) && exists(milhouse);
        otto.ethg[2] <--> EngineLink1_0G <--> maggie.ethg[4] if exists(otto) && exists(maggie);
        ralph.ethg[1] <--> EngineLink1_0G <--> milhouse.ethg[3] if exists(ralph) && exists(milhouse);
        ralph.ethg[3] <--> EngineLink1_0G <--> nelson.ethg[3] if exists(ralph) && exists(nelson);
        abe.ethg[1] <--> EngineLink1_0G <--> maggie.ethg[3] if exists(abe) && exists(maggie);
        abe.ethg[2] <--> EngineLink1_0G <--> otto.ethg[3] if exists(abe) && exists(otto);
        nelson.ethg[1] <--> EngineLink1_0G <--> maggie.ethg[2] if exists(nelson) && exists(maggie);
        bart.ethg[1] <--> EngineLink1_0G <--> abe.ethg[4] if exists(bart) && exists(abe);
        marge.ethg[2] <--> EngineLink1_0G <--> bart.ethg[3] if exists(marge) && exists(bart);
        homer.ethg[1] <--> EngineLink1_0G <--> marge.ethg[4] if exists(homer) && exists(marge);
        homer.ethg[2] <--> EngineLink1_0G <--> bart.ethg[2] if exists(homer) && exists(bart);
        ned.ethg[1] <--> EngineLink1_0G <--> marge.ethg[1] if exists(ned) && exists(marge);
        ned.ethg[2] <--> EngineLink1_0G <--> homer.ethg[4] if exists(ned) && exists(homer);
        ned.ethg[3] <--> EngineLink1_0G <--> otto.ethg[4] if exists(ned) && exists(otto);
        ned.ethg[4] <--> EngineLink1_0G <--> abe.ethg[3] if exists(ned) && exists(abe);
        ned.ethg[5] <--> EngineLink1_0G <--> ralph.ethg[2] if exists(ned) && exists(ralph);
        ned.ethg[6] <--> EngineLink1_0G <--> nelson.ethg[2] if exists(ned) && exists(nelson);
        ned.ethg[7] <--> EngineLink1_0G <--> milhouse.ethg[2] if exists(ned) && exists(milhouse);
        ned.ethg[10] <--> EngineLink10_0G <--> todd.ethg[10] if exists(ned) && exists(todd);
        ned.ethg[11] <--> EngineLink10_0G <--> rod.ethg[10] if exists(ned) && exists(rod);
        rod.ethg[1] <--> EngineLink1_0G <--> todd.ethg[9] if exists(rod) && exists(todd);
        todd.ethg[1] <--> EngineLink1_0G <--> rod.ethg[9] if exists(todd) && exists(rod);
        rod.ethg[4] <--> EngineLink1_0G <--> todd.ethg[8] if exists(rod) && exists(todd);
        todd.ethg[4] <--> EngineLink1_0G <--> rod.ethg[8] if exists(todd) && exists(rod);
        rod.ethg[6] <--> EngineLink1_0G <--> marge.ethg[3] if exists(rod) && exists(marge);
        todd.ethg[6] <--> EngineLink1_0G <--> homer.ethg[3] if exists(todd) && exists(homer);
        rod.ethg[2] <--> EngineLink1_0G <--> todd.ethg[2] if exists(rod) && exists(todd);
        rod.ethg[3] <--> EngineLink1_0G <--> todd.ethg[3] if exists(rod) && exists(todd);
        rod.ethg[5] <--> EngineLink1_0G <--> todd.ethg[5] if exists(rod) && exists(todd);
        rod.ethg[7] <--> EngineLink1_0G <--> todd.ethg[7] if exists(rod) && exists(todd);
        rod.ethg[11] <--> EngineLink10_0G <--> todd.ethg[11] if exists(rod) && exists(todd);
}