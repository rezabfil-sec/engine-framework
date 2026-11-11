use curv::elliptic::curves::Secp256k1;
use std::{collections::HashMap, net::SocketAddr, time::Duration};
use tokio::time::timeout;

use multi_party_ecdsa::protocols::multi_party_ecdsa::gg_2020::state_machine::keygen::LocalKey;

use crate::{
    network::broadcast_network::{BroadcastReceiver, BroadcastSender, Id},
    network::tcp_broadcast_network as tcp,
    protocol::dkr::run_refreshing,
    protocol::gg18::{run_gg18_keygen, run_gg18_signing, GG18Keys},
    protocol::gg20::{run_gg20_keygen, run_sig_offline, run_sig_online},
    supervisor::SupervisorConn,
    util::config::Config,
    util::crypto::{PrivKey, PubKey},
    util::keys_file::KeysFile,
    util::measurement::Measurement,
};

enum KeyWrapper {
    GG18KeyWrapper { keys: GG18Keys },
    GG20KeyWrapper { keys: LocalKey<Secp256k1> },
}

async fn run_dkg(
    self_id: Id,
    config: &Config,
    pub_keys: &Vec<(Id, PubKey)>,
    priv_key: &PrivKey,
    sender: &impl BroadcastSender,
    receiver: &mut impl BroadcastReceiver,
) -> (Measurement, KeyWrapper) {
    match config.scheme {
        crate::util::config::Scheme::GG18 => {
            let (mes, key) = run_gg18_keygen(
                self_id,
                config.num_players,
                config.threshold,
                config,
                pub_keys,
                priv_key,
                sender,
                receiver,
            )
            .await;
            (mes, KeyWrapper::GG18KeyWrapper { keys: key })
        }
        crate::util::config::Scheme::GG20 => {
            let (mes, key) =
                run_gg20_keygen(self_id, config, priv_key, pub_keys, sender, receiver).await;
            (mes, KeyWrapper::GG20KeyWrapper { keys: key })
        }
    }
}

pub async fn run(config: &Config, self_id: Id) {
    // Get here addresses here
    let addrs: HashMap<Id, SocketAddr> = (1..config.num_players + 1)
        .into_iter()
        .map(|i| (i, config.get_address(i).unwrap()))
        .collect();

    let mut supervisor_conn = SupervisorConn::new(self_id, config).await;

    let (priv_key, pub_keys) = KeysFile::read_from_prefix(String::from("keys/keyfile"), self_id);
    let pub_keys = (1..=config.num_players).zip(pub_keys.into_iter()).collect();

    let key_wrapper = {
        let mut last_key_wrapper = None;

        let (tcp_broadcast_sender, mut tcp_broadcast_receiver) =
            tcp::connect_to_network(addrs.clone(), self_id).await;

        supervisor_conn.notify_network_ready().await;

        // DKG runs
        for run in 1..=config.num_dkg_runs {
            let run = run as u32;
            // Synchronize after network has been set up
            // supervisor_conn.notify_network_ready().await;

            // Run DKG protocol
            let (mes, key_wrapper) = timeout(
                Duration::from_secs(600),
                run_dkg(
                    self_id,
                    config,
                    &pub_keys,
                    &priv_key,
                    &tcp_broadcast_sender,
                    &mut tcp_broadcast_receiver,
                ),
            )
            .await
            .unwrap();

            supervisor_conn.notify_dkg_finished(run, mes).await;

            if run as u16 == config.num_dkg_runs {
                last_key_wrapper = Some(key_wrapper)
            }
        }
        last_key_wrapper.unwrap()
    };

    let key_wrapper = if let KeyWrapper::GG20KeyWrapper { keys } = key_wrapper {
        let mut last_keys = keys;

        let (tcp_broadcast_sender, mut tcp_broadcast_receiver) =
            tcp::connect_to_network(addrs.clone(), self_id).await;

        supervisor_conn.notify_network_ready().await;

        for run in 1..=config.num_dkr_runs {
            let run = run as u32;

            let (mes, new_key) = run_refreshing(
                self_id,
                config,
                &priv_key,
                &pub_keys,
                last_keys,
                &tcp_broadcast_sender,
                &mut tcp_broadcast_receiver,
            )
            .await;

            last_keys = new_key;
            supervisor_conn.notify_dkg_finished(run, mes).await;
        }
        KeyWrapper::GG20KeyWrapper { keys: last_keys }
    } else {
        key_wrapper
    };

    let signers = supervisor_conn.notify_signature_start().await;

    // Get here addresses here
    let signer_addrs = signers
        .clone()
        .into_iter()
        .map(|signer_id| {
            let index = signer_id as usize; 
            (signer_id, config.peers.get(index).unwrap().clone())})
        .collect();

    if signers.contains(&self_id) {
        let (tcp_broadcast_sender, mut tcp_broadcast_receiver) =
            tcp::connect_to_network(signer_addrs, self_id).await;
        supervisor_conn.notify_network_ready().await;

        for run in 1..=config.num_sig_runs {
            let run = run as u32;

            let msg_hash = supervisor_conn.notify_get_msg_hash().await;

            match &key_wrapper {
                KeyWrapper::GG18KeyWrapper { keys } => {
                    // Setup network
                    //supervisor_conn.notify_network_ready().await;

                    let (mes, sig) = timeout(
                        Duration::from_secs(600),
                        run_gg18_signing(
                            self_id,
                            &keys,
                            signers.clone(),
                            msg_hash,
                            &priv_key,
                            &pub_keys,
                            &tcp_broadcast_sender,
                            &mut tcp_broadcast_receiver,
                        ),
                    )
                    .await
                    .unwrap();
                    supervisor_conn
                        .notify_signature_finished_gg18(run, mes, sig)
                        .await;
                }
                KeyWrapper::GG20KeyWrapper { keys } => {
                    // Run offline stage
                    let (mes_off, pre_sig) = {
                        timeout(
                            Duration::from_secs(600),
                            run_sig_offline(
                                self_id,
                                signers.clone(),
                                keys,
                                &pub_keys,
                                &priv_key,
                                &tcp_broadcast_sender,
                                &mut tcp_broadcast_receiver,
                            ),
                        )
                        .await
                        .unwrap()
                    };
                    supervisor_conn.notify_network_ready().await;
                    let (mes_on, sig) = {
                        timeout(
                            Duration::from_secs(600),
                            run_sig_online(
                                self_id,
                                signers.clone(),
                                pre_sig,
                                &msg_hash,
                                &priv_key,
                                &pub_keys,
                                &tcp_broadcast_sender,
                                &mut tcp_broadcast_receiver,
                            ),
                        )
                        .await
                        .unwrap()
                    };
                    supervisor_conn
                        .notify_signature_finished_gg20(run, mes_on, mes_off, sig)
                        .await;
                    // Run online stage
                }
            };
        }
    } else {
        // Terminate
    }
}
