use std::{fmt::Display, fs, net::SocketAddr};

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum Scheme {
    GG18,
    GG20,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum BCType {
    BestEffort,
    Echo,
    Optimized,
}

impl Display for Scheme {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Scheme::GG18 => write!(f, "gg18"),
            Scheme::GG20 => write!(f, "gg20"),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    pub supervisor_ip: SocketAddr,
    pub peers: Vec<SocketAddr>, // Updated peers to be a Vec
    pub num_players: u16,
    pub threshold: u16,
    pub base_port: u16,
    pub num_dkg_runs: u16,
    pub num_dkr_runs: u16,
    pub num_sig_runs: u16,
    pub scheme: Scheme,
    pub bc_type: BCType,
}

impl Config {
    pub fn read(config_file: String) -> Result<Config> {
        let config_string_res = fs::read_to_string(config_file).context("Reading config file.");
        config_string_res.and_then(|config_string| {
            serde_yaml::from_str::<Config>(&config_string).context("Deserializing yaml.")
        })
    }

    pub fn get_address(&self, peer_id: u16) -> Option<SocketAddr> {
        if peer_id <= self.num_players {
            let index = peer_id as usize;
            self.peers.get(index).cloned()
        } else {
            None
        }
    }
}
