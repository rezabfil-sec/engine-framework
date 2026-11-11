use async_trait::async_trait;
use std::{collections::HashMap, net::SocketAddr};

use futures::{future, select, FutureExt};

use tokio::{
    io::{ReadHalf, WriteHalf},
    net::{TcpListener, TcpStream},
    pin,
    sync::mpsc,
    sync::mpsc::{Receiver, Sender},
};

use crate::{
    network::broadcast_network::{BroadcastReceiver, BroadcastSender, Id},
    network::network_primitives::{open_connection, read_next_msg, send_msg},
};

#[derive(Debug, Clone)]
pub struct TcpNetworkSender {
    sink: Sender<(Option<Id>, Vec<u8>)>,
}

#[derive(Debug)]
pub struct TcpNetworkReceiver {
    source: Receiver<Vec<u8>>,
}

#[async_trait]
impl BroadcastSender for TcpNetworkSender {
    async fn send_p2p(&self, to: &Id, msg: &Vec<u8>) {
        self.sink.send((Some(*to), msg.clone())).await.unwrap();
    }

    async fn broadcast(&self, msg: &Vec<u8>) {
        self.sink.send((None, msg.clone())).await.unwrap();
    }
}

#[async_trait]
impl BroadcastReceiver for TcpNetworkReceiver {
    async fn next_msg(&mut self) -> Option<Vec<u8>> {
        self.source.recv().await
    }
}

pub type Addrs = HashMap<u16, SocketAddr>;

pub async fn connect_to_network(
    addrs: Addrs,
    self_id: Id,
) -> (TcpNetworkSender, TcpNetworkReceiver) {
    // chan to collect connections
    let (conns_tx, conns_rx) = mpsc::channel(1024);

    // active part of network intialization, i.e. connections that are intialized as a client
    // clone write end of chans to move them to the async task
    let conns_tx_1 = conns_tx.clone();

    let num_players = addrs.len();
    let self_addr = addrs.get(&self_id).unwrap().clone();

    let num_ext_cons = addrs
        .iter()
        .map(|(id, _)| *id)
        .filter(|id| *id > self_id)
        .collect::<Vec<Id>>()
        .len();

    // spawn init task
    tokio::spawn(async move {
        let addrs = addrs;
        init_network(self_id, &addrs, &conns_tx_1).await;
    });
    // spawn server task for incoming connections
    tokio::spawn(async move {
        incoming_conns_server(self_addr, conns_tx.clone(), num_ext_cons as u16).await
    });

    // collect connections from active intialization and connection server
    let num_required_conns: u16 = (num_players - 1) as u16;
    let (write_conns, read_conns) =
        collect_conns_and_init_socket_tasks(num_required_conns, conns_rx, self_id).await;

    let (out_tx, out_rx) = mpsc::channel(1024);

    tokio::spawn(async move {
        let mut write_conns = write_conns;
        let mut out_rx = out_rx;

        while let Some((to, msg)) = out_rx.recv().await {
            match to {
                Some(id) => match write_conns.get_mut(&id) {
                    Some(write) => {
                        send_msg(write, &msg).await;
                    }
                    None => {
                        panic!(
                            "{}: Peer {} not found. Maybe you tried to send message to yourself.",
                            self_id, id
                        );
                    }
                },
                None => {
                    future::join_all(write_conns.iter_mut().map(|(_, conn)| async {
                        send_msg(conn, &msg).await;
                    }))
                    .await;
                }
            }
        }
    });

    (
        TcpNetworkSender { sink: out_tx },
        TcpNetworkReceiver { source: read_conns },
    )
}

async fn init_network(
    self_index: Id,
    addrs: &Addrs,
    conn_chan: &Sender<(Id, (ReadHalf<TcpStream>, WriteHalf<TcpStream>))>,
) {
    // contact all peers with larger index
    // establish connections to contacts
    future::join_all(addrs.into_iter().map(|(i, addr)| async move {
        // open connection to address
        if i < &self_index {
            let socket = open_connection(self_index, *addr).await.unwrap();

            // send established connection to connection handler thread
            conn_chan.clone().send((*i as u16, socket)).await.unwrap();
        }
    }))
    .await;
}

async fn collect_conns_and_init_socket_tasks(
    num_required_connections: u16,
    mut chan: Receiver<(Id, (ReadHalf<TcpStream>, WriteHalf<TcpStream>))>,
    self_id: Id,
) -> (HashMap<Id, WriteHalf<TcpStream>>, Receiver<Vec<u8>>) {
    let mut write_conns = HashMap::new();
    let mut read_conns = Vec::new();
    let mut num_conns = 0;

    // Collect incoming sockets from in chan
    while let Some((index, (read_half, write_half))) = chan.recv().await {
        write_conns.insert(index, write_half);
        read_conns.push(read_half);

        num_conns += 1;
        if num_conns == num_required_connections as usize {
            break;
        }
    }

    if num_conns != num_required_connections as usize {
        panic!(
            "Connection handler channel closed before all connections have been received. Self {}. Received conns: {}.",
            self_id, num_conns
        )
    }

    // socket -> task -> source_in -> source
    let (source_in, source) = mpsc::channel(1024);

    // Spawn threads that read sockets and feed source
    // Threads are closed once the source is closed
    // Important that threads drop read halfes of sockets
    for mut read in read_conns {
        let source_in = source_in.clone();
        tokio::spawn(async move {
            loop {
                // Contains next message once available
                let next_msg = read_next_msg(&mut read).fuse();
                // Checks if out channel has been closed
                let closed = source_in.closed().fuse();
                // Required for select
                pin!(next_msg, closed);
                // Race futures against each other
                // First future to complete is handled
                let next = select! {
                    msg_option = next_msg  => Some(msg_option),
                   () = closed => None,
                };

                if let Some(Some(msg)) = next {
                    // If message is available, send message to source
                    source_in.send(msg).await.unwrap();
                } else {
                    // Out channel, i.e. source_in or read half of socket,
                    // i.e. read has been closed
                    // Shutdown thread, read half of socket is dropped
                    break;
                }
            }
        });
    }
    (write_conns, source)
}

async fn incoming_conns_server(
    self_addr: SocketAddr,
    conn_chan: Sender<(Id, (ReadHalf<TcpStream>, WriteHalf<TcpStream>))>,
    num_cons: u16,
) {
    let listener = TcpListener::bind(self_addr).await.unwrap();

    for _ in 0..num_cons {
        let (socket, _) = listener.accept().await.unwrap();
        let conn_chan = conn_chan.clone();

        tokio::spawn(async move {
            let (mut socket_read, socket_write) = tokio::io::split(socket);
            // if none is received, i.e. the socket has been closed by the client, drop the socket by returning
            if let Some(index_msg) = read_next_msg(&mut socket_read).await {
                let incoming_index: u16 = u16::from_le_bytes(index_msg.try_into().unwrap());

                conn_chan
                    .send((incoming_index, (socket_read, socket_write)))
                    .await
                    .unwrap();
            }
        });
    }
    drop(listener);
}
