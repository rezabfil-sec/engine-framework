use multi_party_ecdsa::protocols::multi_party_ecdsa::gg_2018::party_i as gg18;
use multi_party_ecdsa::protocols::multi_party_ecdsa::gg_2020::party_i as gg20;
use std::collections::HashSet;
use std::time::Duration;
use tokio::time::timeout;

use anyhow::Context;
use futures::{select, FutureExt};
use serde::de::DeserializeOwned;
use tokio::io::AsyncWriteExt;

use rand::distributions::Uniform;
use rand::prelude::Distribution;
use rand::rngs::OsRng;
use tokio::io::{ReadHalf, WriteHalf};
use tokio::net::TcpStream;
use tokio::pin;
use tokio::{
    net::TcpListener,
    sync::mpsc::{self, Receiver, Sender},
};

use crate::util::config::Scheme;
use crate::util::crypto::hash;
use crate::{
    network::broadcast_network::Id,
    network::network_primitives::{connect_recursive, read_next_msg, send_msg},
    util::config::Config,
    util::measurement::Measurement,
};

use self::msgs::SignatureFinishedNotification;

mod msgs;

pub struct SupervisorConn {
    self_id: Id,
    write: WriteHalf<TcpStream>,
    read: ReadHalf<TcpStream>,
}

impl SupervisorConn {
    pub async fn new(self_id: Id, config: &Config) -> Self {
        // Supervisor is player with id 0
        // Get supervisor IP
        let supervisor_addr = config.supervisor_ip;

        let (read, mut write) = connect_recursive(supervisor_addr).await.unwrap();
        // Send own id
        let id_bytes = self_id.to_le_bytes().to_vec();
        send_msg(&mut write, &id_bytes).await;

        SupervisorConn {
            self_id,
            read,
            write,
        }
    }

    pub async fn notify_network_ready(&mut self) {
        let msg = serde_json::to_vec(&msgs::NetworkReadyNotification).unwrap();

        send_msg(&mut self.write, &msg).await;

        match read_next_msg(&mut self.read).await {
            Some(msg) => {
                serde_json::from_slice::<msgs::NetworkReadyReply>(&msg).unwrap();
            }
            _ => panic!("Supervisor socket closed before reply has been received."),
        }
    }

    pub async fn notify_dkg_finished(&mut self, run: u32, mes: Measurement) {
        let msg = msgs::DKGFinishedNotification {
            run,
            notifier_id: self.self_id,
            mes,
        };
        let msg = serde_json::to_vec(&msg).unwrap();

        send_msg(&mut self.write, &msg).await;

        match read_next_msg(&mut self.read).await {
            Some(msg) => {
                let _msg: msgs::DKGFinishedReply = serde_json::from_slice(&msg).unwrap();
            }
            _ => panic!("Supervisor socket closed before reply has been received."),
        }
    }

    pub async fn notify_signature_start(&mut self) -> Vec<Id> {
        let msg = serde_json::to_vec(&msgs::SignatureStartNotification).unwrap();
        send_msg(&mut self.write, &msg).await;

        match read_next_msg(&mut self.read).await {
            Some(msg) => {
                let msg: msgs::SignatureStartReply = serde_json::from_slice(&msg).unwrap();
                msg.signers
            }
            _ => panic!("Supervisor socket closed before reply has been received."),
        }
    }

    pub async fn notify_get_msg_hash(&mut self) -> Vec<u8> {
        let msg = serde_json::to_vec(&msgs::GetMsgNotification).unwrap();
        send_msg(&mut self.write, &msg).await;

        match read_next_msg(&mut self.read).await {
            Some(msg) => {
                let msg: msgs::GetMsgReply = serde_json::from_slice(&msg).unwrap();
                msg.msg_hash
            }
            _ => panic!("Supervisor socket closed before reply has been received."),
        }
    }

    pub async fn notify_signature_finished_gg18(
        &mut self,
        run: u32,
        mes: Measurement,
        sig: gg18::SignatureRecid,
    ) {
        let msg = msgs::SignatureFinishedNotification::GG18 {
            run,
            mes,
            sig,
            notifier_id: self.self_id,
        };

        let msg = serde_json::to_vec(&msg).unwrap();

        send_msg(&mut self.write, &msg).await;

        match read_next_msg(&mut self.read).await {
            Some(msg) => {
                let _msg: msgs::SignatureFinishedReply = serde_json::from_slice(&msg).unwrap();
            }
            _ => panic!("Supervisor socket closed before reply has been received."),
        }
    }

    pub async fn notify_signature_finished_gg20(
        &mut self,
        run: u32,
        mes_on: Measurement,
        mes_off: Measurement,
        sig: gg20::SignatureRecid,
    ) {
        let msg = msgs::SignatureFinishedNotification::GG20 {
            run,
            mes_on,
            mes_off,
            sig,
            notifier_id: self.self_id,
        };

        let msg = serde_json::to_vec(&msg).unwrap();

        send_msg(&mut self.write, &msg).await;

        match read_next_msg(&mut self.read).await {
            Some(msg) => {
                let _msg: msgs::SignatureFinishedReply = serde_json::from_slice(&msg).unwrap();
            }
            _ => panic!("Supervisor socket closed before reply has been received."),
        }
    }
}

async fn run_server(
    config: &Config,
    handler: &Sender<Vec<u8>>,
    sync_chan: &tokio::sync::broadcast::Sender<(HashSet<Id>, Vec<u8>)>,
) {
    // Supervisor is player with id 0
    // Change here to the config IP
    let addr = config.supervisor_ip;
    let listener = TcpListener::bind(addr).await.unwrap();
    for _ in 0..config.num_players {
        let handler = handler.clone();
        // Subscribe to broadcast channel
        let mut receiver = sync_chan.subscribe();

        let (socket, _) = listener.accept().await.unwrap();

        tokio::spawn(async move {
            let (mut read, mut write) = tokio::io::split(socket);

            let id_bytes = read_next_msg(&mut read).await.unwrap();
            let id = u16::from_le_bytes(id_bytes.try_into().unwrap());

            // Spawn handler task for incoming messages from socket
            tokio::spawn(async move {
                loop {
                    // Contains next message once available
                    let next_msg = read_next_msg(&mut read).fuse();
                    // Checks if out channel has been closed
                    let closed = handler.closed().fuse();
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
                        handler.send(msg).await.unwrap();
                    } else {
                        // Out channel, i.e. source_in or read half of socket,
                        // i.e. read has been closed
                        // Shutdown thread, read half of socket is dropped
                        break;
                    }
                }
            });
            // Spawn handler task for outgoing messages
            tokio::spawn(async move {
                loop {
                    // Wait on broadcast channel for supervisor reply and forward it
                    match receiver.recv().await {
                        Ok((receivers, msg)) => {
                            // Check if own id is in receiver set and forward message if it is
                            if receivers.contains(&id) {
                                send_msg(&mut write, &msg).await;
                            }
                        }
                        // If Err is returned, broadcast receiver has been dropped => Task can stop
                        Err(_) => break,
                    }
                }
            });
        });
    }
}

async fn collect_msgs_<M: DeserializeOwned>(num_expected: u16, incoming: &mut Receiver<Vec<u8>>) {
    let mut num_received: u16 = 0;

    while let Some(msg) = incoming.recv().await {
        num_received += 1;
        let _msg: M = serde_json::from_slice(&msg).unwrap();

        if num_received >= num_expected {
            break;
        }
    }

    if num_received < num_expected {
        panic!("Incoming channel closed before all messages have been received.")
    }
}

async fn collect_msgs<M: DeserializeOwned>(
    num_expected: u16,
    incoming: &mut Receiver<Vec<u8>>,
) -> Vec<M> {
    let mut num_received: u16 = 0;
    let mut msgs = Vec::new();

    while let Some(msg) = incoming.recv().await {
        num_received += 1;
        let msg: M = serde_json::from_slice(&msg).unwrap();

        msgs.push(msg);

        if num_received >= num_expected {
            break;
        }
    }

    if num_received < num_expected {
        panic!("Incoming channel closed before all messages have been received.")
    }

    msgs
}

async fn network_ready_sync(
    participants: &Vec<Id>,
    incoming: &mut Receiver<Vec<u8>>,
    sync_chan: &tokio::sync::broadcast::Sender<(HashSet<Id>, Vec<u8>)>,
) {
    let num_expected = participants.len() as u16;
    collect_msgs_::<msgs::NetworkReadyNotification>(num_expected, incoming).await;
    let msg = serde_json::to_vec(&msgs::NetworkReadyReply)
        .context("Serializing network ready reply.")
        .unwrap();
    let receivers: HashSet<Id> = participants.clone().into_iter().collect();

    sync_chan
        .send((receivers, msg))
        .map_err(|_| "Unable to broadcast  network ready sync message")
        .unwrap();
}

async fn dkg_finished_sync(
    config: &Config,
    incoming: &mut Receiver<Vec<u8>>,
    sync_chan: &tokio::sync::broadcast::Sender<(HashSet<Id>, Vec<u8>)>,
) {
    let msgs: Vec<msgs::DKGFinishedNotification> = collect_msgs(config.num_players, incoming).await;

    for msg in msgs {
        write_mes_to_csv(
            String::from(format!("res/{}_dkg_total.csv", config.scheme)),
            String::from(format!("res/{}_dkg_round_computation.csv", config.scheme)),
            String::from(format!("res/{}_dkg_round_total.csv", config.scheme)),
            msg.run,
            msg.notifier_id,
            msg.mes,
            config,
        )
        .await;
    }

    let receivers: HashSet<Id> = (1..=config.num_players).collect();
    let msg = serde_json::to_vec(&msgs::DKGFinishedReply).unwrap();
    sync_chan.send((receivers, msg)).unwrap();
}

async fn dkr_finished_sync(
    config: &Config,
    incoming: &mut Receiver<Vec<u8>>,
    sync_chan: &tokio::sync::broadcast::Sender<(HashSet<Id>, Vec<u8>)>,
) {
    let msgs: Vec<msgs::DKGFinishedNotification> = collect_msgs(config.num_players, incoming).await;

    for msg in msgs {
        write_mes_to_csv(
            String::from(format!("res/{}_dkr_total.csv", config.scheme)),
            String::from(format!("res/{}_dkr_round_computation.csv", config.scheme)),
            String::from(format!("res/{}_dkr_round_total.csv", config.scheme)),
            msg.run,
            msg.notifier_id,
            msg.mes,
            config,
        )
        .await;
    }

    let receivers: HashSet<Id> = (1..=config.num_players).collect();
    let msg = serde_json::to_vec(&msgs::DKGFinishedReply).unwrap();
    sync_chan.send((receivers, msg)).unwrap();
}

async fn signature_start_sync(
    config: &Config,
    incoming: &mut Receiver<Vec<u8>>,
    sync_chan: &tokio::sync::broadcast::Sender<(HashSet<Id>, Vec<u8>)>,
) -> Vec<Id> {
    // Simply wait for all messages
    collect_msgs_::<msgs::SignatureStartNotification>(config.num_players, incoming).await;

    let signers = random_player_sample(config.num_players, config.threshold + 1);

    let msg = serde_json::to_vec(&msgs::SignatureStartReply {
        signers: signers.clone(),
    })
    .context("Serialize signature start reply.")
    .unwrap();

    let receivers = (1..=config.num_players).collect();

    sync_chan
        .send((receivers, msg))
        .map_err(|_| "Unable to broadcast signature start reply")
        .unwrap();

    signers
}

async fn get_msg_sync(
    signers: &Vec<Id>,
    incoming: &mut Receiver<Vec<u8>>,
    sync_chan: &tokio::sync::broadcast::Sender<(HashSet<Id>, Vec<u8>)>,
) {
    collect_msgs_::<msgs::GetMsgNotification>(signers.len() as u16, incoming).await;

    let msg = serde_json::to_vec(&msgs::GetMsgReply {
        msg_hash: random_msg_hash(),
    })
    .unwrap();
    sync_chan
        .send((signers.clone().into_iter().collect(), msg))
        .map_err(|_| "Unable to broadcast signature start reply")
        .unwrap();
}

async fn signature_finished_sync(
    config: &Config,
    signers: &Vec<Id>,
    incoming: &mut Receiver<Vec<u8>>,
    sync_chan: &tokio::sync::broadcast::Sender<(HashSet<Id>, Vec<u8>)>,
) {
    let msgs: Vec<SignatureFinishedNotification> =
        collect_msgs(config.threshold + 1, incoming).await;

    for msg in msgs {
        match msg {
            SignatureFinishedNotification::GG18 {
                mes,
                run,
                notifier_id,
                sig: _sig,
            } => {
                write_mes_to_csv(
                    String::from("res/gg18_sig_total.csv"),
                    String::from("res/gg18_sig_round_computation.csv"),
                    String::from("res/gg18_sig_round_total.csv"),
                    run,
                    notifier_id,
                    mes,
                    config,
                )
                .await;
            }
            SignatureFinishedNotification::GG20 {
                run,
                mes_off,
                mes_on,
                notifier_id,
                sig: _sig,
            } => {
                write_mes_to_csv(
                    String::from("res/gg20_on_sig_total.csv"),
                    String::from("res/gg20_on_sig_round_computation.csv"),
                    String::from("res/gg20_on_sig_round_total.csv"),
                    run,
                    notifier_id,
                    mes_on,
                    config,
                )
                .await;

                write_mes_to_csv(
                    String::from("res/gg20_off_sig_total.csv"),
                    String::from("res/gg20_off_sig_round_computation.csv"),
                    String::from("res/gg20_off_sig_round_total.csv"),
                    run,
                    notifier_id,
                    mes_off,
                    config,
                )
                .await;
            }
        }
    }

    let receivers: HashSet<Id> = signers.clone().into_iter().collect();
    let msg = serde_json::to_vec(&msgs::SignatureFinishedReply).unwrap();
    sync_chan.send((receivers, msg)).unwrap();
}

pub async fn run(config: &Config) {
    let (handler, mut incoming) = mpsc::channel(1024);
    let (sync_chan, _) = tokio::sync::broadcast::channel(1024);

    // Clone for server task
    let handler2 = handler.clone();
    let sync_chan2 = sync_chan.clone();
    let config2 = config.clone();
    // Spawn server task
    tokio::spawn(async move {
        let config = config2;
        run_server(&config, &handler2, &sync_chan2).await;
    });
    let players: Vec<Id> = (1..=config.num_players).collect();

    timeout(
        Duration::from_secs(600),
        network_ready_sync(&players, &mut incoming, &sync_chan),
    )
    .await
    .unwrap();

    // Run experiment runs
    for run in 0..config.num_dkg_runs {
        println!(
            "DKG Run {} for ({}, {}) setup",
            run, config.threshold, config.num_players
        );
        // Wait for players to init network connections and synchronize them
        // network_ready_sync(&players, &mut incoming, &sync_chan).await;
        // Wait for generators to finishe DKG and write measurements
        timeout(
            Duration::from_secs(600),
            dkg_finished_sync(&config, &mut incoming, &sync_chan),
        )
        .await
        .unwrap();
    }

    if let Scheme::GG20 = config.scheme {
        timeout(
            Duration::from_secs(600),
            network_ready_sync(&players, &mut incoming, &sync_chan),
        )
        .await
        .unwrap();
        for run in 0..config.num_dkg_runs {
            println!(
                "DKR Run {} for ({}, {}) setup",
                run, config.threshold, config.num_players
            );
            // Wait for players to init network connections and synchronize them
            // network_ready_sync(&players, &mut incoming, &sync_chan).await;
            // Wait for generators to finishe DKG and write measurements
            timeout(
                Duration::from_secs(600),
                dkr_finished_sync(&config, &mut incoming, &sync_chan),
            )
            .await
            .unwrap();
        }
    };

    // Sample set of signers
    let signers = signature_start_sync(&config, &mut incoming, &sync_chan).await;

    timeout(
        Duration::from_secs(600),
        network_ready_sync(&signers, &mut incoming, &sync_chan),
    )
    .await
    .unwrap();

    for run in 0..config.num_sig_runs {
        println!(
            "Sig Run {} for ({}, {}) setup",
            run, config.threshold, config.num_players
        );

        get_msg_sync(&signers, &mut incoming, &sync_chan).await;
        // Wait for signers to init network
        //network_ready_sync(&signers, &mut incoming, &sync_chan).await;
        // Additional sync for online phase
        if config.scheme == Scheme::GG20 {
            timeout(
                Duration::from_secs(600),
                network_ready_sync(&signers, &mut incoming, &sync_chan),
            )
            .await
            .unwrap();
        }
        // Wait for signers to finish signature protocol
        timeout(
            Duration::from_secs(600),
            signature_finished_sync(&config, &signers, &mut incoming, &sync_chan),
        )
        .await
        .unwrap();
    }

    // Delay to wait until all messages have been sent by socket takss
    tokio::time::sleep(Duration::from_secs(1)).await;
}

async fn write_mes_to_csv(
    total_fn: String,
    per_round_comp_fn: String,
    per_round_total_fn: String,
    run: u32,
    id: Id,
    mes: Measurement,
    config: &Config,
) {
    let mut total_file = tokio::fs::OpenOptions::new()
        .create(true)
        .write(true)
        .append(true)
        .open(total_fn)
        .await
        .unwrap();
    let mut per_round_comp_file = tokio::fs::OpenOptions::new()
        .create(true)
        .write(true)
        .append(true)
        .open(per_round_comp_fn)
        .await
        .unwrap();
    let mut per_round_total_file = tokio::fs::OpenOptions::new()
        .create(true)
        .write(true)
        .append(true)
        .open(per_round_total_fn)
        .await
        .unwrap();

    total_file
        .write(
            format!(
                "{},{},{},{},{}\n",
                config.threshold, config.num_players, id, run, mes.total
            )
            .as_bytes(),
        )
        .await
        .unwrap();

    for i in 1..=mes.per_round_computation.len() {
        per_round_comp_file
            .write(
                format!(
                    "{},{},{},{},{},{}\n",
                    config.threshold,
                    config.num_players,
                    id,
                    run,
                    i,
                    mes.per_round_computation[i - 1]
                )
                .as_bytes(),
            )
            .await
            .unwrap();
    }

    for i in 1..=mes.per_round_total.len() {
        per_round_total_file
            .write(
                format!(
                    "{},{},{},{},{},{}\n",
                    config.threshold,
                    config.num_players,
                    id,
                    run,
                    i,
                    mes.per_round_total[i - 1]
                )
                .as_bytes(),
            )
            .await
            .unwrap();
    }
}

fn random_player_sample(num_players: u16, sample_size: u16) -> Vec<Id> {
    let mut sample_vec: Vec<Id> = (1..=num_players).collect();
    let mut out: Vec<Id> = (0..sample_size)
        .map(|_| {
            let i = Uniform::from(0..sample_vec.len()).sample(&mut OsRng);
            let new_id = sample_vec[i];
            sample_vec.remove(i);
            new_id
        })
        .collect();
    out.sort();
    out
}

fn random_msg_hash() -> Vec<u8> {
    let msg_len = Uniform::from(1..2056).sample(&mut OsRng);
    let msg = (0..msg_len).map(|_| rand::random()).collect();
    hash(&msg).to_bytes()
}
