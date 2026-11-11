use multi_party_ecdsa::protocols::multi_party_ecdsa::gg_2018::party_i as gg18;
use multi_party_ecdsa::protocols::multi_party_ecdsa::gg_2020::party_i as gg20;
use serde::{Deserialize, Serialize};

use crate::{network::broadcast_network::Id, util::measurement::Measurement};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct NetworkReadyNotification;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct NetworkReadyReply;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DKGFinishedNotification {
    pub mes: Measurement,
    pub run: u32,
    pub notifier_id: Id,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DKGFinishedReply;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SignatureStartNotification;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SignatureStartReply {
    pub signers: Vec<Id>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GetMsgNotification;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GetMsgReply {
    pub msg_hash: Vec<u8>,
}

#[derive(Debug, Serialize, Deserialize)]
pub enum SignatureFinishedNotification {
    GG18 {
        mes: Measurement,
        run: u32,
        notifier_id: Id,
        sig: gg18::SignatureRecid,
    },
    GG20 {
        run: u32,
        mes_off: Measurement,
        mes_on: Measurement,
        notifier_id: Id,
        sig: gg20::SignatureRecid,
    },
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SignatureFinishedReply;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunFinishedReply;
