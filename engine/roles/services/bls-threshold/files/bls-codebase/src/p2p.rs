#![allow(non_snake_case)]

use std::process::exit;
use std::sync::{Arc, Mutex};
use std::net::{SocketAddr};
use std::time::Duration;
use std::{fs, io};
use std::io::{BufRead, BufReader, BufWriter, Write};

use anyhow::{Context, Result, anyhow};
use async_std::task;
use futures::{channel::mpsc, Sink, SinkExt, Stream, stream::FusedStream, channel::mpsc::{Sender, Receiver}, StreamExt};
use tracing::{error, info};
use serde::{de::DeserializeOwned, Serialize, Deserialize};

use tokio::runtime;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::tcp::{OwnedReadHalf, OwnedWriteHalf};
use tokio::net::{TcpListener, TcpStream, TcpSocket};
use tokio::fs::{File};

use snow::{params::NoiseParams, Builder, TransportState, HandshakeState, Keypair};

use round_based::{Msg};
use round_based::async_runtime::Error;
use tracing::span::Record;

static noise_params: &str = "Noise_KK_25519_AESGCM_SHA256";

#[derive(Serialize, Deserialize, Debug)]
pub struct peer_identity {
    pub ID: u16,
    pub listen_addr: SocketAddr,
    pub pubkey: Vec<u8>,
    pub privkey: Vec<u8>,
}

#[derive(Clone, Serialize, Deserialize, Debug)]
pub struct p2pNoisePeer {
    pub ID: u16,    //unnecessary ?
    pub addr: SocketAddr,
    pub pubkey: Vec<u8>,
}

struct p2pNoisePeerConnection {
    //need to keep TcpStream ?
    transportstate: TransportState,
}

pub struct p2p {
    local_ID: Arc<u16>,
    local_keypair: Arc<snow::Keypair>,
    peer_connections: Arc<Vec<Mutex<(Option<p2pNoisePeerConnection>, bool)>>>,
    known_peers: Arc<Vec<p2pNoisePeer>>,
    outgoing_spscs: Arc<Vec<(Mutex<Option<Sender<Vec<u8>>>>, Mutex<Option<Receiver<Vec<u8>>>>)>>,
}

#[derive(Deserialize, Debug)]
struct HostsCsvRecord {
    id: u16,
    ip: String,
}

impl p2p {
    //TODO: manual bool lock not reset if connection establishment aborted (both ends)

    pub async fn init_p2p<T>(
        listen_addr: String,
        known_peers_vec: Vec<p2pNoisePeer>,
        loc_ID: u16,
        loc_keypair: snow::Keypair
    ) -> anyhow::Result<(
        p2p,
        impl Stream<Item = std::result::Result<Msg<T>, anyhow::Error>> + FusedStream + Unpin,
        impl Sink<Msg<T>, Error = mpsc::SendError> + Unpin,
    )>
    where
        T: Serialize + DeserializeOwned + Send + 'static,
    { //static lifetime ?? (result of compiler hints, does not compile otherwise (possibly #61949))
        println!("init_p2p started: {}", loc_ID);

        let addr = listen_addr.parse::<SocketAddr>()?;
        let listener = TcpListener::bind(addr).await?;

        //initialize mpsc channel for incoming messages. Type is inferred from method return type
        let (mut incoming_tx, incoming_rx) = futures::channel::mpsc::channel(10);

        //initialize spsc channels for outgoing messages to peers
        let mut outgoings_per_peer: Vec<(Mutex<Option<Sender<Vec<u8>>>>, Mutex<Option<Receiver<Vec<u8>>>>)> = Vec::new();
        outgoings_per_peer.resize_with(
            known_peers_vec.len(),
            || {
                let (mut sng_out_tx, sng_out_rx) = futures::channel::mpsc::channel(5); //TODO: what buffer size is reasonable (5: max 4 rounds)
                (Mutex::new(Some(sng_out_tx)), Mutex::new(Some(sng_out_rx)))
            }
        );

        //initialize peer connection vector
        let mut p2p_conns: Vec<Mutex<(Option<p2pNoisePeerConnection>, bool)>> = Vec::new();
        p2p_conns.resize_with(known_peers_vec.len(), || Mutex::new((None, false)));

        //atomic rcs for data needed in spawned tasks
        let known_peers_arc = Arc::new(known_peers_vec);
        let loc_ID_arc = Arc::new(loc_ID);
        let loc_keypair_arc = Arc::new(loc_keypair);
        let p2p_conns_arc = Arc::new(p2p_conns);
        let outgoings_per_peer_arc = Arc::new(outgoings_per_peer);

        //start task that accepts incoming connections and starts tasks to establish noise on top of them
        let tcp_listener_kPeerlist = known_peers_arc.clone();
        let tcp_listener_locID = loc_ID_arc.clone();
        let tcp_listener_locKeyPair = loc_keypair_arc.clone();
        let tcp_listener_p2pConns = p2p_conns_arc.clone();
        let mut tcp_listener_incomingTx = incoming_tx.clone();
        let tcp_listener_OutgoingsPerPeer = outgoings_per_peer_arc.clone();

        println!("{}: starting spawner thread...", loc_ID_arc);

        tokio::spawn( async move {
            loop {
                println!("spawner {} waiting...", tcp_listener_locID);

                let (mut socket, _) = listener.accept().await.unwrap();

                println!("spawner {}: connection accepted!", tcp_listener_locID);

                //task to establish noise connection
                let noise_connector_kPeerlist = tcp_listener_kPeerlist.clone();
                let noise_connector_locID = tcp_listener_locID.clone();
                let noise_connector_locKeyPair = tcp_listener_locKeyPair.clone();
                let noise_connector_p2pConns = tcp_listener_p2pConns.clone();
                let mut noise_connector_incomingTx = tcp_listener_incomingTx.clone();
                let noise_connector_OutgoingsPerPeer = tcp_listener_OutgoingsPerPeer.clone();
                tokio::spawn(async move {
                    //read peer number
                    let mut buf: Vec<u8> = vec![0; 2];
                    let peer_number: u16;
                    match socket.read_exact(&mut buf).await {
                        Ok(2) => {
                            //read the peer ID from the (first) two bytes of the first tcp message.
                            //This is a "prelude" to the noise handshake
                            peer_number = (((buf[0] as u16) << 8) + (buf[1] as u16));
                        }
                        Ok(n) => {
                            //fail silently, socket dropped
                            error!("noise responder: received {} bytes from initiator instead of the expected 2!", n);
                            return;
                        }
                        Err(e) => {
                            //fail silently, socket dropped
                            error!("noise responder: error when receiving peer ID: {}", e);
                            return;
                        }
                    }

                    //check if peer number is plausible
                    if (peer_number as usize) >= noise_connector_kPeerlist.len() {
                        println!("noise responder: implausible peer ID: {}", peer_number);
                        return;
                    } else {
                        //DEBUG
                        println!("noise responder {}: incoming conn from p.: {}", noise_connector_locID, peer_number);
                    }

                    //check if connection to that peer already exists, drop socket if so
                    //acquire "lock" to prevent the "same" connection being established multiple times in parallel
                    {
                        let mut p2pconnlockguard = noise_connector_p2pConns[peer_number as usize].lock().unwrap();
                        match p2pconnlockguard.0 {
                            None => {
                                if p2pconnlockguard.1 {
                                    //this connection is already WIP! (?!?!?!?!)
                                    error!("noise responder: double connection opened!");
                                    return;
                                } else {
                                    p2pconnlockguard.1 = true;
                                }
                            }
                            Some(_) => {
                                println!("noise responder: connection already exists!");
                                return;
                            }
                        }
                    }

                    //establish noise KK as responder

                    //get remote pubkey from local store
                    let remote_pubkey = match noise_connector_kPeerlist.get(peer_number as usize) {
                        Some(key) => {
                            //check if id is our own, drop connection if so
                            if key.ID == *noise_connector_locID {
                                println!("noise responder: our own ID is trying to connect ?!?!");
                                return;
                            } else {
                                key
                            }
                        }
                        None => {
                            //index is out of bounds, peer not known.
                            //fail silently, socket dropped
                            println!("noise responder: connecting ID unknown / out of bounds");
                            return;
                        }
                    };

                    //build HandshakeState with given parameters
                    let mut noise = match snow::Builder::new(noise_params.parse().unwrap())
                        .local_private_key(&noise_connector_locKeyPair.private)
                        .remote_public_key(&remote_pubkey.pubkey)
                        .build_responder() {
                        Ok(handshakeState) => {
                            handshakeState
                        }
                        Err(e) => {
                            println!("noise responder: error building HandshakeState: {}", e);
                            return;
                        }
                    };

                    //65kb noise message buffer
                    let mut noise_buf: Vec<u8> = vec![0; 65535];

                    //split socket
                    let (mut tcp_rx, mut tcp_tx) = socket.into_split();

                    //we are responder. "<-" means "to initiator", "->" means "to responder
                    //-> e, es, ss
                    //TODO: receive payload here already for zero RTT
                    match noise.read_message(
                        &(match p2p::recv_16bL(&mut tcp_rx).await {
                            Ok(m) => { /*println!("into handshake: {:?}", m);*/ m }
                            Err(e) => {
                                //handshake message ill-received, fail and drop socket
                                println!("noise responder: handshake message recv_16bL failed: {}", e);
                                return;
                            }
                        }), &mut buf) {
                        Ok(m_len) => {
                            //TODO: put in queue
                            //println!("noise responder: handshake msg 1 received!");
                        }
                        Err(e) => {
                            println!("noise responder: handshake failed: {}", e);
                            return;
                        }
                    }

                    //<- e, ee, se
                    //TODO: transmit payload already?
                    let len = match noise.write_message(&[], &mut noise_buf) {
                        Ok(l) => { l }
                        Err(e) => {
                            println!("noise responder: handshake message construction failed: {}", e);
                            return;
                        }
                    };
                    match p2p::send_16bL(&mut tcp_tx, &noise_buf[..len]).await {
                        Ok(()) => {}
                        Err(e) => {
                            println!("noise responder: handshake message send failed: {}",e );
                            return;
                        }
                    }

                    //convert HandshakeState to TransportState
                    let mut noise = match noise.into_transport_mode() {
                        Ok(transportState) => { transportState }
                        Err(e) => {
                            println!("noise responder: error transitioning to TransportState: {}", e);
                            return;
                        }
                    };

                    //noise is fully established at this point

                    //save socket, writehalf, and TransportState to struct, move OwnedReadHalf to outside block
                    {
                        let mut p2pconnlockguard = noise_connector_p2pConns[peer_number as usize].lock().unwrap();
                        p2pconnlockguard.0 = Some(p2pNoisePeerConnection {transportstate: noise });

                        //"lock" from above is dropped here
                        p2pconnlockguard.1 = false;
                    }

                    //start sender task
                    let mut peer_sender_rx: Receiver<Vec<u8>>;
                    {
                        let mut peer_sender_receiver_guard = noise_connector_OutgoingsPerPeer[peer_number as usize].1.lock().unwrap();
                        peer_sender_rx = peer_sender_receiver_guard.take().unwrap();
                        //TODO: error handling
                    }
                    p2p::start_sender_task(peer_sender_rx, noise_connector_p2pConns.clone(), peer_number.clone(), tcp_tx).await;

                    p2p::recv_loop(tcp_rx, noise_connector_p2pConns.clone(), noise_connector_locID.clone(), peer_number.clone(), noise_connector_incomingTx).await;

                });
            }
        });



        //initiate connections for upper floor(n/2) nodes in ring
        let out_conn_n = {
            if (known_peers_arc.len() % 2) != 0 {
                known_peers_arc.len() / 2
            } else {
                if (*loc_ID_arc as usize) < (known_peers_arc.len() / 2) {
                    known_peers_arc.len() / 2
                } else {
                    (known_peers_arc.len() / 2) - 1
                }
            }
        };
        for conPeerOffset in 1..(out_conn_n + 1) {
            //connection strategy:
            // odd #n of nodes: connection to all floor(n/2) nodes with higher index
            // even #n of nodes:
            //      nodes < (n/2): connection to all (n/2) nodes w. higher index
            //      nodes >= (n/2): connection to all (n/2)-1 nodes w. higher index

            let tcp_initiator_kPeerlist = known_peers_arc.clone();
            let tcp_initiator_locID = loc_ID_arc.clone();
            let tcp_initiator_locKeyPair = loc_keypair_arc.clone();
            let tcp_initiator_p2pConns = p2p_conns_arc.clone();
            let mut tcp_initiator_incomingTx = incoming_tx.clone();
            let tcp_initiator_OutgoingsPerPeer = outgoings_per_peer_arc.clone();
            let tcp_initiator_conPeer = ((*loc_ID_arc) as usize + conPeerOffset) % known_peers_arc.len(); //TODO: type?
            tokio::spawn(async move {

                //check if connection to that peer already exists, immediately return if so
                //acquire "lock" to prevent the "same" connection being established multiple times in parallel
                {
                    let mut p2pconnlockguard = tcp_initiator_p2pConns[tcp_initiator_conPeer as usize].lock().unwrap();
                    match p2pconnlockguard.0 {
                        None => {
                            if p2pconnlockguard.1 {
                                //this connection is already WIP! (?!?!?!?!)
                                println!("noise responder: double connection opened!");
                                return;
                            } else {
                                p2pconnlockguard.1 = true;
                            }
                        }
                        Some(_) => {
                            println!("noise responder: connection already exists!");
                            return;
                        }
                    }
                }

                println!("tcp initiator {}: connecting to peer {}", tcp_initiator_locID, tcp_initiator_conPeer);

                //open tcp connection to peer
                let tcp_stream: TcpStream;
                let mut tcp_connection_retries = 5;
                loop {
                    let tcp_socket = TcpSocket::new_v4().unwrap();
                    match tcp_socket.connect(tcp_initiator_kPeerlist[tcp_initiator_conPeer].addr).await {
                        Ok(tcp_str) => {
                            tcp_stream = tcp_str;
                            break;
                        }
                        Err(e) => {
                            println!("tcp {}: error while trying to connect to to peer #{}: {}", tcp_initiator_locID, tcp_initiator_conPeer, e);
                            if tcp_connection_retries <= 0 { return; }
                            tcp_connection_retries -= 1;

                            //wait for 0.05s before next attempt
                            task::sleep(Duration::from_millis(50));
                        }
                    };
                }

                //establish noise KK as initiator

                //get remote pubkey from local store
                let remote_pubkey = tcp_initiator_kPeerlist.get(tcp_initiator_conPeer).unwrap();

                //build HandshakeState with given parameters
                let mut noise = match snow::Builder::new(noise_params.parse().unwrap())
                    .local_private_key(&tcp_initiator_locKeyPair.private)
                    .remote_public_key(&remote_pubkey.pubkey)
                    .build_initiator() {
                    Ok(handshakeState) => {
                        handshakeState
                    }
                    Err(e) => {
                        println!("noise initiator: error building HandshakeState: {}", e);
                        return;
                    }
                };

                //65kb noise message buffer
                let mut noise_buf: Vec<u8> = vec![0; 65535];

                //split socket
                let (mut tcp_rx, mut tcp_tx) = tcp_stream.into_split();

                //-> e, es, ss
                let len = match noise.write_message(&[0u8, 0], &mut noise_buf) {
                    Ok(l) => { /*println!("send from handshake: {:?}", &noise_buf[..l]);*/ l }
                    Err(e) => {
                        println!("noise initiator msg construction error: {}", e);
                        return;
                    }
                };
                //write peer ID in first two bytes of first handshake message
                let mut hm1vec = vec![((*tcp_initiator_locID & 0xFF00) >> 8) as u8,(*tcp_initiator_locID & 0xFF) as u8];

                //DEBUG
                println!("sender peer id: {:?}", hm1vec);

                match p2p::send_16bL_prelude(&mut tcp_tx, &noise_buf[..len], &hm1vec).await {    //TODO: length could exceed max noise length due to peer ID bytes
                    Ok(()) => {}
                    Err(e) => {
                        println!("noise responder: handshake message send failed: {}",e );
                        return;
                    }
                };


                //<- e, ee, se
                //TODO: receive payload here already for zero RTT
                match noise.read_message(
                    &(match p2p::recv_16bL(&mut tcp_rx).await {
                        Ok(m) => { m }
                        Err(e) => {
                            //handshake message ill-received, fail and drop socket
                            println!("noise initiator {}: handshake message recv_16bL failed: {}", tcp_initiator_locID, e);
                            return;
                        }
                    }), &mut noise_buf) {
                    Ok(m_len) => {
                        //TODO: put in queue
                    }
                    Err(e) => {
                        println!("noise responder: handshake failed: {}", e);
                        return;
                    }
                }

                //convert HandshakeState to TransportState
                let mut noise = match noise.into_transport_mode() {
                    Ok(transportState) => { transportState }
                    Err(e) => {
                        println!("noise initiator: error transitioning to TransportState: {}", e);
                        return;
                    }
                };

                //noise is fully established at this point

                //save socket, writehalf, and TransportState to struct, move OwnedReadHalf to outside block
                {
                    let mut p2pconnlockguard = tcp_initiator_p2pConns[tcp_initiator_conPeer as usize].lock().unwrap();
                    p2pconnlockguard.0 = Some(p2pNoisePeerConnection {transportstate: noise });

                    //"lock" from above is dropped here
                    p2pconnlockguard.1 = false;
                }

                //start sender task
                let mut peer_sender_rx: Receiver<Vec<u8>>;
                {
                    let mut peer_sender_receiver_guard = tcp_initiator_OutgoingsPerPeer[tcp_initiator_conPeer as usize].1.lock().unwrap();
                    peer_sender_rx = peer_sender_receiver_guard.take().unwrap();
                    //TODO: error handling
                }
                p2p::start_sender_task(peer_sender_rx, tcp_initiator_p2pConns.clone(), (tcp_initiator_conPeer as u16), tcp_tx).await;

                //start listening and queuing
                p2p::recv_loop(tcp_rx, tcp_initiator_p2pConns, tcp_initiator_locID, (tcp_initiator_conPeer as u16), tcp_initiator_incomingTx).await;

            });


        }


        //outgoing messages channel from bls library to dispatcher task
        let (outcoming_tx, mut outcoming_rx) = futures::channel::mpsc::channel::<Msg<T>>(10);

        //start outgoing message dispatcher task
        let dispatcher_OutgoingsPerPeer = outgoings_per_peer_arc.clone();
        tokio::spawn( async move {
            //collect all sender channel endpoints for each peer connection sender task -- necessary because can't call .await while holding lock
            let mut channel_senders: Vec<Sender<Vec<u8>>> = Vec::new();
            for i in 0..dispatcher_OutgoingsPerPeer.len() {
                //take sender from option
                let mut sender_guard = dispatcher_OutgoingsPerPeer[i].0.lock().unwrap();
                channel_senders.push(sender_guard.take().unwrap()); //TODO: error handling?
            }

            //accept messages and dispatch them
            while let Some(msg) = outcoming_rx.next().await {
                match msg.receiver {
                    None => {
                        //serialize
                        let msg_ser = p2p::serialize_protoMsg(msg).unwrap();

                        //DEBUG:
                        println!("dispatcher: msg: len: {}", msg_ser.len());

                        //broadcast, send to all sender tasks //TODO: send broadcast to self?
                        for i in 0..dispatcher_OutgoingsPerPeer.len() {
                            let msg_ser_i =  msg_ser.clone();
                            channel_senders[i].send(msg_ser_i).await.unwrap();
                        }
                    }
                    Some(peer) => {
                        //serialize
                        let msg_ser = p2p::serialize_protoMsg(msg).unwrap();

                        //send to recipient sender task  NOTE: one-based indexing in round_based !!!
                        channel_senders[(peer - 1) as usize].send(msg_ser).await.unwrap();    //TODO: error handling?
                    }
                }
            }
        });

        Ok((
            p2p { peer_connections: p2p_conns_arc, known_peers: known_peers_arc, local_ID: loc_ID_arc, local_keypair: loc_keypair_arc, outgoing_spscs: outgoings_per_peer_arc},
            incoming_rx,
            outcoming_tx
        ) )
    }

    async fn start_sender_task(
        mut peer_sender_rx: Receiver<Vec<u8>>,
        p2p_conns: Arc<Vec<Mutex<(Option<p2pNoisePeerConnection>, bool)>>>,
        peer_id: u16,
        mut tcp_tx: OwnedWriteHalf
    ) {
        //start sender task

        //let noise_sender_p2pConns = noise_connector_p2pConns.clone();
        //let sender_peer_ID = peer_number;
        tokio::spawn(async move {
            //noise output buffer
            let mut noise_buf_sender: Vec<u8> = vec![0; 65535];

            //continuously take messages from channel
            while let Some(out_msg) = peer_sender_rx.next().await {
                //message is already serialized by dispatcher

                /*
                let len: usize;
                //encrypt message
                {
                    let mut p2pConnGuard = p2p_conns[peer_id as usize].lock().unwrap();
                    len = p2pConnGuard.0.as_mut().unwrap().transportstate.write_message(&out_msg, &mut noise_buf_sender).unwrap(); //TODO: what happens if message is too long?
                }
                 */

                //send encrypted message to peer
                match p2p::send_16bL(&mut tcp_tx, &out_msg).await {
                    Ok(()) => {}
                    Err(e) => {println!("failed to send message to peer {}: {}, exiting sender Task!", peer_id, e); return;}
                }
            }
            info!("peer sender stream closed!");

        });
    }

    async fn recv_loop<U: DeserializeOwned>(
        mut tcp_rx: OwnedReadHalf,
        p2p_conns: Arc<Vec<Mutex<(Option<p2pNoisePeerConnection>, bool)>>>,
        loc_id: Arc<u16>,
        peer_id: u16,
        mut incoming_tx: Sender<Result<Msg<U>>>
    ) {
        //65kb noise message buffer
        let mut noise_buf: Vec<u8> = vec![0; 65535];

        //start listening and queuing
        while let Ok(msg) = p2p::recv_16bL(&mut tcp_rx).await { //TODO: better error handling, i.e. ignore malformed messages
            {
                let len: usize;

                /*
                {
                    //lock noise TransportState
                    let mut p2pconnlockguard = p2p_conns[peer_id as usize].lock().unwrap();
                    len = match p2pconnlockguard.0.as_mut().unwrap().transportstate.read_message(&msg, &mut noise_buf) {
                        Ok(l) => { l }
                        Err(e) => {
                            println!("noise responder incoming message error: {}", e);
                            continue;
                        } //ignore messages not decrypting & authenticating correctly
                    };
                }

                 */

                let msg = p2p::deserialize_protoMsg::<U>(&msg);

                //check if message is for us, and unwrap (what happens if unwrap unsuccessful?)
                if let Ok(msg) = msg.as_ref() {
                    if msg.receiver.is_some() && (msg.receiver != Some(*loc_id + 1)) {
                        println!("received message for other recipient!: for {:?} , while I am {:?} .", msg.receiver, Some(loc_id.to_string()))
                    }
                }

                //send msg into incoming message channel / queue
                if let Err(e) = incoming_tx.send(msg).await {
                    info!("incoming mpsc stream input closed with: {}", e);
                    return;
                }

                //TODO: when to send error to input mpsc channel? (channel type: Result<Msg<...>>)

            }
        }
    }

    async fn recv_16bL(rx: &mut OwnedReadHalf) -> anyhow::Result<Vec<u8>> {
        let mut len_field: Vec<u8> = vec![0; 2];    //buffer for 16b length field
        rx.read_exact(&mut len_field).await?;
        let len = (((len_field[0] as usize) << 8) + (len_field[1] as usize));
        if len > 65535 {
            return Err(anyhow!("recv_16bL: msg len too long: > 65535 B"));
        }
        let mut msg_buf: Vec<u8> = vec![0; len];
        rx.read_exact(&mut msg_buf).await?;
        //println!("recv'd: {:?}", msg_buf);
        Ok(msg_buf)
    }

    async fn send_16bL(tx: &mut OwnedWriteHalf, msg_buf: &[u8]) -> anyhow::Result<()> {
        if msg_buf.len() > 65535 {
            return Err(anyhow!("send_16bL: message too long: > 65535 B"));
        }
        //println!("send: {:?}", msg_buf);
        let mut len_BE: Vec<u8> = vec![((msg_buf.len() >> 8) as u8), ((msg_buf.len() & 0xff) as u8)];    //16b length in big endian (network byte order)
        len_BE.extend_from_slice(msg_buf);  //append message to length field
        tx.write_all(&len_BE).await?;
        Ok(())
    }

    async fn send_16bL_prelude(tx: &mut OwnedWriteHalf, msg_buf: &[u8], prelude: &[u8]) -> anyhow::Result<()> {
        if msg_buf.len() > 65535 {
            return Err(anyhow!("send_16bL: message too long: > 65535 B"));
        }
        //println!("send_prelude: {:?}", msg_buf);
        let mut msg: Vec<u8> = prelude.to_vec();
        let len_BE: Vec<u8> = vec![((msg_buf.len() >> 8) as u8), ((msg_buf.len() & 0xff) as u8)];    //16b length in big endian (network byte order)
        msg.extend_from_slice(&len_BE);
        msg.extend_from_slice(msg_buf);  //append message to length field & prelude
        tx.write_all(&msg).await?;
        Ok(())
    }

    fn serialize_protoMsg<U: Serialize>(msg: round_based::Msg<U>) -> anyhow::Result<Vec<u8>> {
        let payload = serde_json::to_vec(&msg).context("serialize msg")?;
        Ok(payload)
    }

    fn deserialize_protoMsg<U: DeserializeOwned>(buf: &[u8]) -> anyhow::Result<round_based::Msg<U>> {
        serde_json::from_slice(buf).context("deserialize msg")
    }

    pub /*async*/ fn generateP2pKeys(hosts_file: String, output_file: String, privkey_dir: String) -> Result<()>{

        //open input file
        let in_file = fs::File::open(hosts_file).context("opening hosts file")?;
        let mut reader = csv::Reader::from_reader(in_file);

        let mut peers: Vec<p2pNoisePeer> = Vec::new();
        let mut keypairs: Vec<Keypair> = Vec::new();

        let builder = snow::Builder::new(noise_params.parse().unwrap());

        //pick up lines, check if ids are valid sequence, generate keypairs
        let mut expected_id = 0;
        for result in reader.deserialize() {
            let record: HostsCsvRecord = result?;
            if record.id != expected_id {
                return Err(anyhow!("invalid id sequence!"));
            } else {
                let peer_addr = record.ip.parse::<SocketAddr>()?;

                let kp = builder.generate_keypair()?;

                peers.push(p2pNoisePeer {
                    ID: record.id,
                    addr: peer_addr,
                    pubkey: kp.public.clone(),
                });

                keypairs.push(kp);

                expected_id += 1;
            }
        }


        //write phonebook
        let mut out_string: String = String::new();
        let mut out_file = fs::File::create(output_file)?;
        let mut writer = BufWriter::new(out_file);
        for i in 0..peers.len() {
            writer.write(&serde_json::to_vec(&peers[i].clone()).unwrap()).unwrap();
            if i < (peers.len()-1) {
                writer.write("\n".as_ref()).unwrap();
            }
        }
        writer.flush()?;

        //write private key files
        for i in 0..peers.len() {
            let mut filepath: String = privkey_dir.clone();
            filepath.push_str("/");
            filepath.push_str(&i.to_string());
            //filepath.push_str(".key");

            let mut keyfile_i = fs::File::create(filepath)?;
            let mut keyfilewriter = BufWriter::new(keyfile_i);

            keyfilewriter.write(&serde_json::to_vec(&peer_identity {
                ID: peers[i].ID,
                listen_addr: peers[i].addr,
                pubkey: keypairs[i].public.clone(),
                privkey: keypairs[i].private.clone(),
            }).unwrap())?;
            keyfilewriter.flush()?;
        }
        
        Ok(())
    }
    
    pub fn read_identity(path: String) -> Result<peer_identity> {
        let content = fs::read_to_string(path)?;
        let identity = serde_json::from_str(&content)?;
        Ok(identity)
    }

    pub fn read_phonebook(path: String) -> Result<Vec<p2pNoisePeer>> {

        //open input file
        let in_file = fs::File::open(path)?;
        let mut line_reader = BufReader::new(in_file).lines();

        let mut phonebook: Vec<p2pNoisePeer> = Vec::new();

        //pick up lines and check for valid id sequence
        let mut expected_id = 0;
        for line in line_reader {
            if let Ok(l) = line {
                let peer: p2pNoisePeer = serde_json::from_str(&l)?;

                if peer.ID != expected_id {
                    return Err(anyhow!("invalid ID sequence in phonebook file!"));
                }
                expected_id += 1;

                phonebook.push(peer);
            } else {
                return Err(anyhow!("Error reading phonebook!"));
            }
        }

        Ok(phonebook)
    }

    pub fn local_id(&self) -> u16 {
        return *self.local_ID;
    }

    pub fn n(&self) -> u16 {
        return self.known_peers.len() as u16;
    }
}



#[cfg(test)]
mod tests {
    use std::thread::sleep;
    use std::time::Duration;
    use serde_json::de::Read;
    use super::*;

    #[test]
    fn test_p2p() {
        // Build async runtime
        let mut runtime = runtime::Builder::new_multi_thread();

        runtime.enable_all();

        /*
        if let Some(t) = app.threads {
            runtime.worker_threads(t);
        }
        */

        let runtime = match runtime.build() {
            Ok(r) => r,
            Err(e) => {
                println!("Failed to build async runtime: {}", e);
                exit(1)
            }
        };



        let result = runtime.block_on(async {
            static PARAMS_CLIENT: &'static str = "Noise_KK_25519_AESGCM_SHA256";
            let builder: snow::Builder = snow::Builder::new(PARAMS_CLIENT.parse().unwrap());
            let kp0 = builder.generate_keypair().unwrap();
            let kp1 = builder.generate_keypair().unwrap();
            let kp2 = builder.generate_keypair().unwrap();
            let kp3 = builder.generate_keypair().unwrap();

            let peers_vec: Vec<p2pNoisePeer> = vec![
                p2pNoisePeer { ID: 0, addr: "127.0.0.1:42000".parse::<SocketAddr>().unwrap(), pubkey: kp0.public.clone() },
                p2pNoisePeer { ID: 1, addr: "127.0.0.1:42001".parse::<SocketAddr>().unwrap(), pubkey: kp1.public.clone() },
                p2pNoisePeer { ID: 2, addr: "127.0.0.1:42002".parse::<SocketAddr>().unwrap(), pubkey: kp2.public.clone() },
                p2pNoisePeer { ID: 3, addr: "127.0.0.1:42003".parse::<SocketAddr>().unwrap(), pubkey: kp3.public.clone() }
            ];

            let (p2p0, mut stream0, mut sink0) = p2p::init_p2p::<u32>(String::from("127.0.0.1:42000"), peers_vec.clone(), 0, kp0).await.unwrap();
            let (p2p1, mut stream1, mut sink1) = p2p::init_p2p::<u32>(String::from("127.0.0.1:42001"), peers_vec.clone(), 1, kp1).await.unwrap();
            let (p2p2, mut stream2, mut sink2) = p2p::init_p2p::<u32>(String::from("127.0.0.1:42002"), peers_vec.clone(), 2, kp2).await.unwrap();
            let (p2p3, mut stream3, mut sink3) = p2p::init_p2p::<u32>(String::from("127.0.0.1:42003"), peers_vec.clone(), 3, kp3).await.unwrap();

            println!("network created!");



            //test p2p messages

            let c0to1 = 000001;
            let c1to0 = 010000;
            let c3to2 = 030001;
            let c2to3 = 020003;

            let msg0to1 = Msg{ sender: 1, receiver: Some(2), body: c0to1 };
            let msg1to0 = Msg{ sender: 2, receiver: Some(1), body: c1to0 };
            let msg3to2 = Msg{ sender: 4, receiver: Some(3), body: c3to2 };
            let msg2to3 = Msg{ sender: 3, receiver: Some(4), body: c2to3 };

            sink0.send(msg0to1).await.unwrap();
            sink1.send(msg1to0).await.unwrap();
            sink3.send(msg3to2).await.unwrap();
            sink2.send(msg2to3).await.unwrap();


            println!("Messages sent!");

            if let Some(msg) = stream1.next().await {
                let msgu: Msg<u32> = msg.unwrap();
                println!("msg 0to1 recved: {:?}", msgu);
                assert_eq!(msgu.body, c0to1);
            } else {
                assert!(false);
            }

            if let Some(msg) = stream0.next().await {
                println!("msg 2 recved");
                let msgu: Msg<u32> = msg.unwrap();
                assert_eq!(msgu.body, c1to0);
            } else {
                assert!(false);
            }

            if let Some(msg) = stream2.next().await {
                println!("msg 3 recved");
                let msgu: Msg<u32> = msg.unwrap();
                assert_eq!(msgu.body, c3to2);
            } else {
                assert!(false);
            }

            if let Some(msg) = stream3.next().await {
                println!("msg 4 recved");
                let msgu: Msg<u32> = msg.unwrap();
                assert_eq!(msgu.body, c2to3);
            } else {
                assert!(false);
            }




            //test broadcast
            let cbroadcast = 0xbeef;

            let broadcast_msg = Msg{ sender: 2, receiver: None, body: cbroadcast };
            sink2.send(broadcast_msg).await.unwrap();

            if let Some(msg) = stream0.next().await {
                println!("msg 1 recved");
                let msgu: Msg<u32> = msg.unwrap();
                assert_eq!(msgu.body, cbroadcast);
            } else {
                assert!(false);
            }

            if let Some(msg) = stream1.next().await {
                println!("msg 2 recved");
                let msgu: Msg<u32> = msg.unwrap();
                assert_eq!(msgu.body, cbroadcast);
            } else {
                assert!(false);
            }

            if let Some(msg) = stream3.next().await {
                println!("msg 3 recved");
                let msgu: Msg<u32> = msg.unwrap();
                assert_eq!(msgu.body, cbroadcast);
            } else {
                assert!(false);
            }


        });
    }

}

