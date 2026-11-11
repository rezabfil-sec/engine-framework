use std::fs;

use anyhow::Context;
use serde::Serialize;

use crate::{
    network::broadcast_network::Id,
    util::crypto::{PrivKey, PubKey},
};

#[derive(Clone, Debug, Serialize, serde::Deserialize)]
pub struct KeysFile {
    priv_key: String,
    pub_keys: Vec<String>,
}

impl KeysFile {
    pub fn read(file_path: String) -> (PrivKey, Vec<PubKey>) {
        let file_content = fs::read_to_string(file_path)
            .context("Reading keys file.")
            .unwrap();
        let key_file: KeysFile = serde_yaml::from_str(&file_content)
            .context("Deserializing keys file")
            .unwrap();
        let priv_key = hex::decode(key_file.priv_key)
            .context("Deserializing hex encoding.")
            .map(|string| string.to_vec())
            .and_then(|bytes| PrivKey::from_bytes(bytes))
            .context("Deserializing private key from bytes.")
            .unwrap();
        let pub_keys = key_file
            .pub_keys
            .into_iter()
            .map(|hex_key| {
                hex::decode(hex_key)
                    .context("Deserializing hex encoding.")
                    .map(|string| string.to_vec())
                    .and_then(|pk_bytes| PubKey::from_bytes(pk_bytes))
                    .context("Deserializing public key.")
                    .unwrap()
            })
            .collect();

        (priv_key, pub_keys)
    }

    pub fn read_from_prefix(path_prefix: String, self_id: Id) -> (PrivKey, Vec<PubKey>) {
        let file_path = self_keys_file_name(path_prefix, self_id);
        Self::read(file_path)
    }
}

fn self_keys_file_name(path_prefix: String, self_id: Id) -> String {
    format!("{}_{}.keys", path_prefix, self_id)
}

pub fn generate_keys_files(path_prefix: String, num_players: u16) {
    let priv_keys: Vec<PrivKey> = (1..=num_players)
        .into_iter()
        .map(|_| PrivKey::generate())
        .collect();

    let pub_keys: Vec<PubKey> = priv_keys
        .iter()
        .map(|priv_key| PubKey::from_priv_key(priv_key))
        .collect();

    let pub_keys: Vec<String> = pub_keys
        .into_iter()
        .map(|pub_key| hex::encode(pub_key.to_bytes()))
        .collect();

    priv_keys.into_iter().enumerate().for_each(|(i, priv_key)| {
        let file_name = self_keys_file_name(path_prefix.clone(), i as u16 + 1);
        let keys_file = KeysFile {
            priv_key: hex::encode(priv_key.to_bytes()),
            pub_keys: pub_keys.clone(),
        };

        fs::write(
            file_name,
            serde_yaml::to_vec(&keys_file)
                .context("Writing keys file.")
                .unwrap(),
        )
        .unwrap();
    })
}
