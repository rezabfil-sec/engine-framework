#![allow(dead_code)]
use std::collections::HashMap;

use anyhow::Context;
use serde::{de::DeserializeOwned, Deserialize, Serialize};

use crate::network::broadcast_network::{BroadcastReceiver, BroadcastSender, Id};
use crate::util::crypto::{hash, hash_many, HashDigest, PrivKey, PubKey, SecretEncKey, Sig};

#[derive(Serialize, Deserialize)]
enum Msg {
    BroadcastMsg {
        round: u16,
        from: Id,
        body: Vec<u8>,
        sig: Sig,
    },
    P2PMsg {
        round: u16,
        from: Id,
        body: Vec<u8>,
        sig: Sig,
    },
}

#[derive(Debug, Clone)]
pub struct EncKeys {
    pub keys: HashMap<Id, SecretEncKey>,
    pub self_id: Id,
}

impl EncKeys {
    pub fn get_key(&self, id: Id) -> &SecretEncKey {
        self.keys.get(&id).unwrap()
    }
}

/// Used to synchronize protocol processes between rounds.
pub struct Sync {
    participants: Vec<Id>,
    self_id: Id,
    curr_round: u16,
    next_round_msgs: Vec<Msg>,
    pub_keys: HashMap<Id, PubKey>,
    private_key: PrivKey,
}

impl Sync {
    pub fn new(
        self_id: Id,
        participants: Vec<Id>,
        pub_keys: &Vec<(Id, PubKey)>,
        priv_key: &PrivKey,
    ) -> Self {
        Sync {
            self_id,
            participants,
            curr_round: 1,
            next_round_msgs: Vec::new(),
            pub_keys: pub_keys.clone().into_iter().collect(),
            private_key: priv_key.clone(),
        }
    }
    /// Sends broadcast message.
    pub async fn send_broadcast<M>(&mut self, broadcast_msg: M, sender: &impl BroadcastSender)
    where
        M: Serialize + DeserializeOwned + Clone,
    {
        // Msg body needs to be serialized into JSON
        let body = serde_json::to_vec(&broadcast_msg).unwrap();
        let sig = self.private_key.sign(&hash(&body));
        let msg: Msg = Msg::BroadcastMsg {
            round: self.curr_round,
            from: self.self_id,
            body,
            sig,
        };
        // Here we can use bincode
        let msg = bincode::serialize(&msg).unwrap();
        sender.broadcast(&msg).await;
    }

    /// Sends p2p messages. Returns own message if it is contained in messages.
    pub async fn send_p2p<M>(
        &mut self,
        p2p_msgs: Vec<(Id, M)>,
        enc_keys: Option<&EncKeys>,
        sender: &impl BroadcastSender,
    ) -> Option<M>
    where
        M: Serialize + Clone,
    {
        let mut own_msg = None;
        for (to, msg) in p2p_msgs {
            if to != self.self_id {
                // msg content needs to be serialized into JSON
                let mut msg = serde_json::to_vec(&msg).unwrap();
                if let Some(enc_keys) = enc_keys {
                    let key = enc_keys.get_key(to);
                    let enc_msg = key.encrypt(&msg);
                    // For encrypted msg we can use bincode
                    msg = bincode::serialize(&enc_msg).unwrap();
                }

                let sig = self.private_key.sign(&hash(&msg));

                let msg: Msg = Msg::P2PMsg {
                    round: self.curr_round,
                    from: self.self_id,
                    body: msg,
                    sig,
                };
                // Broadcast msg layer can be encrypted with bincode
                let msg = bincode::serialize(&msg).unwrap();

                sender.send_p2p(&to, &msg).await;
            } else {
                own_msg = Some(msg);
            }
        }
        own_msg
    }

    /// Receive messages of current round. The broadcast and p2p flags specify whether broadcast, p2p or both types of messages
    /// are received in the round. Returns hash maps with all messages from other players, one for broadcast and one for p2p.
    pub async fn receive(
        &mut self,
        broadcast: bool,
        p2p: bool,
        // We seperate p2p own msg and group id here because we allow not including own p2p msg
        receiver: &mut impl BroadcastReceiver,
    ) -> (HashMap<Id, Vec<u8>>, HashMap<Id, Vec<u8>>) {
        let mut expected_num_msgs = 0;
        if broadcast {
            expected_num_msgs += self.participants.len() - 1;
        }
        if p2p {
            expected_num_msgs += self.participants.len() - 1;
        }

        let mut received_bc: HashMap<Id, Vec<u8>> = HashMap::new();
        let mut received_p2p: HashMap<Id, Vec<u8>> = HashMap::new();

        // Take msgs received in last round
        let mut msgs_rcvd_in_last_round = std::mem::replace(&mut self.next_round_msgs, Vec::new());
        let mut num_received = 0;
        while num_received < expected_num_msgs {
            // Take next message from last round messages until last round messages is
            let msg: Msg = match msgs_rcvd_in_last_round.pop() {
                Some(msg) => msg,
                None => receiver
                    .next_msg()
                    .await
                    .map(|msg| bincode::deserialize(&msg).unwrap())
                    .unwrap(),
            };

            match msg {
                Msg::BroadcastMsg {
                    round,
                    from,
                    body,
                    sig,
                } => {
                    if round > self.curr_round {
                        self.next_round_msgs.push(Msg::BroadcastMsg {
                            round,
                            from,
                            body,
                            sig,
                        });
                    } else {
                        assert!(
                            sig.verify(self.pub_keys.get(&from).unwrap(), &hash(&body)),
                            "Received msg with invalid signature from {}",
                            from
                        );

                        num_received += 1;
                        received_bc.insert(from, body);
                    }
                }
                Msg::P2PMsg {
                    round,
                    from,
                    body,
                    sig,
                } => {
                    if round > self.curr_round {
                        self.next_round_msgs.push(Msg::P2PMsg {
                            round,
                            from,
                            body,
                            sig,
                        })
                    } else {
                        assert!(
                            sig.verify(self.pub_keys.get(&from).unwrap(), &hash(&body)),
                            "Received msg with invalid signature from {}",
                            from
                        );

                        num_received += 1;

                        received_p2p.insert(from, body);
                    }
                }
            }
        }

        // Inc round counter
        self.curr_round += 1;

        (received_bc, received_p2p)
    }

    /// Helper function for best effort broadcast sync barrier.
    pub async fn sync_barrier_default_bc<M>(
        &mut self,
        broadcast_msg: M,
        sender: &impl BroadcastSender,
        receiver: &mut impl BroadcastReceiver,
    ) -> Vec<M>
    where
        M: Serialize + DeserializeOwned + Clone,
    {
        self.send_broadcast(broadcast_msg.clone(), sender).await;
        let (received, _) = self.receive(true, false, receiver).await;
        self.get_ordered_out_bc(received, Some(&broadcast_msg))
    }
    /// Best effort sync barrier, but also returns hash for optimized echo bc.
    pub async fn sync_barrier_default_bc_get_hash<M>(
        &mut self,
        broadcast_msg: M,
        sender: &impl BroadcastSender,
        receiver: &mut impl BroadcastReceiver,
    ) -> (HashDigest, Vec<M>)
    where
        M: Serialize + DeserializeOwned + Clone,
    {
        self.send_broadcast(broadcast_msg.clone(), sender).await;
        let (received, _) = self.receive(true, false, receiver).await;
        let ordered =
            self.get_ordered_out_ser(received, Some(&serde_json::to_vec(&broadcast_msg).unwrap()));

        let hash = hash_many(&ordered);

        let out = ordered
            .into_iter()
            .zip(&self.participants)
            .map(|(msg, id)| {
                if *id == self.self_id {
                    broadcast_msg.clone()
                } else {
                    serde_json::from_slice(&msg).unwrap()
                }
            })
            .collect();
        (hash, out)
    }
    /// Best effort bc but hash for optimized echo bc is appended.
    pub async fn sync_barrier_default_bc_send_hash<M>(
        &mut self,
        broadcast_msg: M,
        previous_round_hash: HashDigest,
        sender: &impl BroadcastSender,
        receiver: &mut impl BroadcastReceiver,
    ) -> Vec<M>
    where
        M: Serialize + DeserializeOwned + Clone,
    {
        self.send_broadcast((previous_round_hash.clone(), broadcast_msg.clone()), sender)
            .await;

        let (received, _) = self.receive(true, false, receiver).await;
        self.get_ordered_out_bc_check_hash(received, &broadcast_msg, previous_round_hash)
    }
    /// Get hash and append hash in round for optimized echo bc.
    pub async fn sync_barrier_default_bc_get_and_send_hash<M>(
        &mut self,
        broadcast_msg: M,
        previous_round_hash: HashDigest,
        sender: &impl BroadcastSender,
        receiver: &mut impl BroadcastReceiver,
    ) -> (HashDigest, Vec<M>)
    where
        M: Serialize + DeserializeOwned + Clone,
    {
        self.send_broadcast(
            (
                previous_round_hash.clone(),
                serde_json::to_vec(&broadcast_msg).unwrap(),
            ),
            sender,
        )
        .await;
        let (received, _) = self.receive(true, false, receiver).await;
        let ordered = self.get_ordered_out_ser_check_hash(
            received,
            &serde_json::to_vec(&broadcast_msg).unwrap(),
            previous_round_hash,
        );

        let hash = hash_many(&ordered);

        let out = ordered
            .into_iter()
            .zip(&self.participants)
            .map(|(msg, id)| {
                if *id == self.self_id {
                    broadcast_msg.clone()
                } else {
                    serde_json::from_slice(&msg).unwrap()
                }
            })
            .collect();
        (hash, out)
    }
    /// Additional round if last round was robust broadcast round. For optimized echo bc.
    pub async fn get_and_check_last_round_hashes_default(
        &mut self,
        hash: HashDigest,
        sender: &impl BroadcastSender,
        receiver: &mut impl BroadcastReceiver,
    ) {
        self.send_broadcast(hash.clone(), sender).await;

        let (received, _) = self.receive(true, false, receiver).await;
        received.into_iter().for_each(|(from, other_hash)| {
            let other_hash = serde_json::from_slice(&other_hash).unwrap();
            assert_eq!(
                hash, other_hash,
                "Hash from {} did not match own hash",
                from
            );
        });
    }

    /// Sync barrier with standard echo bc, i.e. with additional round.
    pub async fn sync_barrier_default_echo_bc<M>(
        &mut self,
        broadcast_msg: M,
        sender: &impl BroadcastSender,
        receiver: &mut impl BroadcastReceiver,
    ) -> Vec<M>
    where
        M: Serialize + DeserializeOwned + Clone,
    {
        self.send_broadcast(broadcast_msg.clone(), sender).await;
        let (received, _) = self.receive(true, false, receiver).await;
        let own_acks: HashMap<Id, HashDigest> =
            received.iter().map(|(id, msg)| (*id, hash(msg))).collect();
        let ack_vec: Vec<(Id, HashDigest)> = own_acks
            .iter()
            .map(|(id, dig)| (*id, dig.clone()))
            .collect();
        self.send_broadcast(ack_vec, sender).await;
        let (received_acks, _) = self.receive(true, false, receiver).await;
        received_acks.into_iter().for_each(|(_, acks)| {
            let acks: Vec<(Id, HashDigest)> = serde_json::from_slice(&acks).unwrap();
            acks.into_iter().for_each(|(ack_id, dig)| {
                if ack_id != self.self_id {
                    assert_eq!(
                        &dig,
                        own_acks
                            .get(&ack_id)
                            .context(format!("{}: Getting own ack for {}", self.self_id, ack_id))
                            .unwrap(),
                        "Received ack hash did not match own ack hash"
                    );
                }
            });
        });

        self.get_ordered_out_bc(received, Some(&broadcast_msg))
    }
    /// Helper function for sync barrier with only p2p.
    pub async fn sync_barrier_default_p2p<M>(
        &mut self,
        p2p_msgs: Vec<(Id, M)>,
        enc_keys: &EncKeys,
        sender: &impl BroadcastSender,
        receiver: &mut impl BroadcastReceiver,
    ) -> Vec<M>
    where
        M: Serialize + DeserializeOwned + Clone,
    {
        let own_msg = self.send_p2p(p2p_msgs, Some(enc_keys), sender).await;
        let (_, received) = self.receive(false, true, receiver).await;

        self.get_ordered_out_p2p(received, own_msg.as_ref(), enc_keys)
    }
    /// Sync barrier with only p2p and p2p msgs are not encrypted. This is useful for signature protocols.
    pub async fn sync_barrier_default_p2p_no_enc<M>(
        &mut self,
        p2p_msgs: Vec<(Id, M)>,
        sender: &impl BroadcastSender,
        receiver: &mut impl BroadcastReceiver,
    ) -> Vec<M>
    where
        M: Serialize + DeserializeOwned + Clone,
    {
        let own_msg = self.send_p2p(p2p_msgs, None, sender).await;
        let (_, received) = self.receive(false, true, receiver).await;

        self.get_ordered_out_bc(received, own_msg.as_ref())
    }
    /// Best effort sync barrier with p2p and bc.
    pub async fn sync_barrier_default_bc_and_p2p<MB, MP>(
        &mut self,
        broadcast_msg: MB,
        p2p_msgs: Vec<(Id, MP)>,
        enc_keys: &EncKeys,
        sender: &impl BroadcastSender,
        receiver: &mut impl BroadcastReceiver,
    ) -> (Vec<MB>, Vec<MP>)
    where
        MB: Serialize + DeserializeOwned + Clone,
        MP: Serialize + DeserializeOwned + Clone,
    {
        self.send_broadcast(broadcast_msg.clone(), sender).await;
        let own_p2p = self.send_p2p(p2p_msgs, Some(enc_keys), sender).await;
        let (received_bc, received_p2p) = self.receive(true, true, receiver).await;

        (
            self.get_ordered_out_bc(received_bc, Some(&broadcast_msg)),
            self.get_ordered_out_p2p(received_p2p, own_p2p.as_ref(), enc_keys),
        )
    }
    /// Sync barrier with p2p and bc. Standard echo bc is used for bc.
    pub async fn sync_barrier_default_echo_bc_and_p2p<MB, MP>(
        &mut self,
        broadcast_msg: MB,
        p2p_msgs: Vec<(Id, MP)>,
        enc_keys: &EncKeys,
        sender: &impl BroadcastSender,
        receiver: &mut impl BroadcastReceiver,
    ) -> (Vec<MB>, Vec<MP>)
    where
        MB: Serialize + DeserializeOwned + Clone,
        MP: Serialize + DeserializeOwned + Clone,
    {
        self.send_broadcast(broadcast_msg.clone(), sender).await;
        let own_p2p = self.send_p2p(p2p_msgs, Some(enc_keys), sender).await;
        let (received_bc, received_p2p) = self.receive(true, true, receiver).await;
        let own_acks: HashMap<Id, HashDigest> = received_bc
            .iter()
            .map(|(id, msg)| (*id, hash(msg)))
            .collect();
        let ack_vec: Vec<(Id, HashDigest)> = own_acks
            .iter()
            .map(|(id, dig)| (*id, dig.clone()))
            .collect();
        self.send_broadcast(ack_vec, sender).await;
        let (received_acks, _) = self.receive(true, false, receiver).await;
        received_acks.into_iter().for_each(|(_, acks)| {
            let acks: Vec<(Id, HashDigest)> = serde_json::from_slice(&acks).unwrap();
            acks.into_iter().for_each(|(ack_id, dig)| {
                if ack_id != self.self_id {
                    assert_eq!(
                        &dig,
                        own_acks
                            .get(&ack_id)
                            .context(format!("{}: Getting own ack for {}", self.self_id, ack_id))
                            .unwrap(),
                        "Received ack hash did not match own ack hash"
                    );
                }
            });
        });

        (
            self.get_ordered_out_bc(received_bc, Some(&broadcast_msg)),
            self.get_ordered_out_p2p(received_p2p, own_p2p.as_ref(), enc_keys),
        )
    }
    /// Sync barrier with best effort bc and p2p. Hash of bc messages is returned for omptimized echo bc.
    pub async fn sync_barrier_default_bc_get_hash_and_p2p<MB, MP>(
        &mut self,
        broadcast_msg: MB,
        p2p_msgs: Vec<(Id, MP)>,
        enc_keys: &EncKeys,
        sender: &impl BroadcastSender,
        receiver: &mut impl BroadcastReceiver,
    ) -> (HashDigest, Vec<MB>, Vec<MP>)
    where
        MB: Serialize + DeserializeOwned + Clone,
        MP: Serialize + DeserializeOwned + Clone,
    {
        self.send_broadcast(broadcast_msg.clone(), sender).await;
        let own_p2p = self.send_p2p(p2p_msgs, Some(enc_keys), sender).await;
        let (received_bc, received_p2p) = self.receive(true, true, receiver).await;

        let ordered = self.get_ordered_out_ser(
            received_bc,
            Some(&serde_json::to_vec(&broadcast_msg).unwrap()),
        );

        let hash = hash_many(&ordered);

        let out_bc = ordered
            .into_iter()
            .zip(self.participants.clone())
            .map(|(msg, id)| {
                if id == self.self_id {
                    broadcast_msg.clone()
                } else {
                    serde_json::from_slice(&msg).unwrap()
                }
            })
            .collect();
        let out_p2p = self.get_ordered_out_p2p(received_p2p, own_p2p.as_ref(), enc_keys);

        (hash, out_bc, out_p2p)
    }

    fn get_ordered_out_bc<M: DeserializeOwned + Clone>(
        &self,
        msgs: HashMap<Id, Vec<u8>>,
        own_msg: Option<&M>,
    ) -> Vec<M> {
        let mut msgs = msgs;
        let mut out = Vec::new();
        for id in &self.participants {
            if *id != self.self_id {
                let msg = msgs
                    .remove(&id)
                    .context(format!(
                        "Getting msg of player {}. Self: {}. Round: {}",
                        id, self.self_id, self.curr_round
                    ))
                    .unwrap();
                out.push(serde_json::from_slice(&msg).unwrap());
            } else {
                if let Some(own_msg) = own_msg {
                    out.push(own_msg.clone());
                }
            }
        }
        out
    }

    fn get_ordered_out_bc_check_hash<M: DeserializeOwned + Clone>(
        &self,
        msgs: HashMap<Id, Vec<u8>>,
        own_msg: &M,
        hash: HashDigest,
    ) -> Vec<M> {
        let mut msgs = msgs;
        let mut out = Vec::new();
        for id in &self.participants {
            if *id != self.self_id {
                let msg = msgs
                    .remove(&id)
                    .context(format!(
                        "Getting msg of player {}. Self: {}. Round: {}",
                        id, self.self_id, self.curr_round
                    ))
                    .unwrap();
                let (rcvd_hash, msg): (HashDigest, M) = serde_json::from_slice(&msg).unwrap();
                assert_eq!(
                    rcvd_hash, hash,
                    "Received hash from {} did not match own hash",
                    id
                );
                out.push(msg);
            } else {
                out.push(own_msg.clone());
            }
        }
        out
    }

    fn get_ordered_out_ser_check_hash(
        &self,
        msgs: HashMap<Id, Vec<u8>>,
        own_msg: &Vec<u8>,
        hash: HashDigest,
    ) -> Vec<Vec<u8>> {
        let mut msgs = msgs;
        let mut out = Vec::new();
        for id in &self.participants {
            if *id != self.self_id {
                let msg = msgs
                    .remove(id)
                    .context(format!(
                        "Getting msg of player {}. Self: {}. Round: {}",
                        id, self.self_id, self.curr_round
                    ))
                    .unwrap();
                let (rcvd_hash, msg): (HashDigest, Vec<u8>) = serde_json::from_slice(&msg).unwrap();
                assert_eq!(
                    rcvd_hash, hash,
                    "Received hash from {} did not match own hash",
                    id
                );
                out.push(msg);
            } else {
                out.push(own_msg.clone());
            }
        }
        out
    }

    fn get_ordered_out_ser(
        &self,
        msgs: HashMap<Id, Vec<u8>>,
        own_msg: Option<&Vec<u8>>,
    ) -> Vec<Vec<u8>> {
        let mut msgs = msgs;
        let mut out = Vec::new();
        for id in &self.participants {
            if *id != self.self_id {
                let msg = msgs
                    .remove(&id)
                    .context(format!(
                        "Getting msg of player {}. Self: {}. Round: {}",
                        id, self.self_id, self.curr_round
                    ))
                    .unwrap();
                out.push(msg);
            } else {
                if let Some(own_msg) = own_msg {
                    out.push(own_msg.clone());
                }
            }
        }
        out
    }

    fn get_ordered_out_p2p<M: DeserializeOwned + Clone>(
        &self,
        msgs: HashMap<Id, Vec<u8>>,
        own_msg: Option<&M>,
        enc_keys: &EncKeys,
    ) -> Vec<M> {
        let mut msgs = msgs;
        let mut out = Vec::new();
        for id in &self.participants {
            if *id != self.self_id {
                let msg = msgs
                    .remove(id)
                    .context(format!("Getting msg of player {}", id))
                    .unwrap();
                let msg = bincode::deserialize(&msg).unwrap();
                let msg = enc_keys.get_key(*id).decrypt(msg);
                out.push(serde_json::from_slice(&msg).unwrap());
            } else {
                if let Some(msg) = own_msg {
                    out.push(msg.clone());
                }
            }
        }
        out
    }

    fn get_ordered_out_p2p_encrypted(&self, msgs: HashMap<Id, Vec<u8>>) -> Vec<Vec<u8>> {
        let mut msgs = msgs;
        let mut out = Vec::new();
        for id in &self.participants {
            if *id != self.self_id {
                let msg = msgs
                    .remove(&id)
                    .context(format!("Getting msg of player {}", id))
                    .unwrap();
                out.push(msg);
            }
        }
        out
    }
}
