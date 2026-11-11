#![allow(non_snake_case)]
#![allow(dead_code)]
use std::{collections::HashMap, time::Instant};

use curv::{
    arithmetic::{BitManipulation, Converter, Samplable},
    cryptographic_primitives::{
        proofs::sigma_dlog::DLogProof, secret_sharing::feldman_vss::VerifiableSS,
    },
    elliptic::curves::{Point, Scalar, Secp256k1},
    BigInt,
};
use kzen_paillier::{DecryptionKey, EncryptionKey, KeyGeneration, Paillier};
use multi_party_ecdsa::protocols::multi_party_ecdsa::gg_2020::{
    party_i::{generate_h1_h2_N_tilde, Keys, Parameters, SharedKeys},
    state_machine::keygen::LocalKey,
};
use serde::{Deserialize, Serialize};
use sha2::Sha256;
use tokio::task;
use zk_paillier::zkproofs::{CompositeDLogProof, DLogStatement, NiCorrectKeyProof};

use crate::{
    network::broadcast_network::{BroadcastReceiver, BroadcastSender, Id},
    network::round::{EncKeys, Sync},
    util::config::{BCType, Config},
    util::crypto::{hash_many, HashDigest, PrivKey, PubKey, SecretEncKey},
    util::measurement::Measurement,
};

const SECURITY: usize = 256;
const PAILLIER_MIN_BIT_LENGTH: usize = 2047;
const PAILLIER_MAX_BIT_LENGTH: usize = 2048;

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Round1MsgOld {
    com: HashDigest,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Round1MsgNew {
    paillier_pub: EncryptionKey,
    range_proof_setup: DLogStatement,
    paillier_zkp: NiCorrectKeyProof,
    range_proof_setup_zkps: (CompositeDLogProof, CompositeDLogProof),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Round1DiffieHellmanMsg {
    diffie_hellman: Point<Secp256k1>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Round2MsgOld {
    vss_scheme: VerifiableSS<Secp256k1>,
    blind_factor: Vec<u8>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Round2P2P {
    secret_share: Scalar<Secp256k1>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct Round3MsgNew {
    dlog_zkp: DLogProof<Secp256k1, Sha256>,
}

/// Run DKR as pure key refresh protocol.
pub async fn run_refreshing(
    self_id: Id,
    config: &Config,
    priv_key: &PrivKey,
    pub_keys: &Vec<(Id, PubKey)>,
    old_key: LocalKey<Secp256k1>,
    sender: &impl BroadcastSender,
    receiver: &mut impl BroadcastReceiver,
) -> (Measurement, LocalKey<Secp256k1>) {
    let mut sync = Sync::new(
        self_id,
        (1..=config.num_players).collect(),
        pub_keys,
        priv_key,
    );

    let threshold = config.threshold;
    let num_players = config.num_players;

    let start_time = Instant::now();
    let mut comp_time = Vec::new();
    let mut total_time = Vec::new();

    let (old_key, round1_msg_old, round2_msg_old, round2_p2p_msgs) =
        task::spawn_blocking(move || {
            let (round1_msg_old, round2_msg_old, round2_p2p_msgs) =
                round1_old(&old_key, threshold, num_players);

            (old_key, round1_msg_old, round2_msg_old, round2_p2p_msgs)
        })
        .await
        .unwrap();

    let (round1_msg_new, paillier_private) = task::spawn_blocking(|| round1_new()).await.unwrap();

    comp_time.push(start_time.elapsed().as_millis());

    let (bc_hash, round1_msgs) = match config.bc_type {
        crate::util::config::BCType::BestEffort => (
            None,
            sync.sync_barrier_default_bc((round1_msg_old, round1_msg_new), sender, receiver)
                .await,
        ),
        crate::util::config::BCType::Echo => (
            None,
            sync.sync_barrier_default_echo_bc((round1_msg_old, round1_msg_new), sender, receiver)
                .await,
        ),
        crate::util::config::BCType::Optimized => {
            let (hash, msgs) = sync
                .sync_barrier_default_bc_get_hash(
                    (round1_msg_old, round1_msg_new),
                    sender,
                    receiver,
                )
                .await;
            (Some(hash), msgs)
        }
    };

    total_time.push(start_time.elapsed().as_millis());
    let round_start = Instant::now();

    let (round1_msgs_old, round1_msgs_new): (Vec<Round1MsgOld>, Vec<Round1MsgNew>) =
        round1_msgs.into_iter().unzip();

    let (old_key, enc_keys) = task::spawn_blocking(move || {
        let enc_keys = round2_get_enc_keys_refreshing(self_id, &old_key);
        (old_key, enc_keys)
    })
    .await
    .unwrap();

    let (paillier_pubkeys, range_proof_setups) =
        task::spawn_blocking(move || round2_new(self_id, round1_msgs_new))
            .await
            .unwrap();

    comp_time.push(round_start.elapsed().as_millis());
    let (round2_bc_msgs, round2_p2p_msgs) = sync
        .sync_barrier_default_bc_and_p2p(
            round2_msg_old,
            round2_p2p_msgs,
            &enc_keys,
            sender,
            receiver,
        )
        .await;
    total_time.push(round_start.elapsed().as_millis());
    let round_start = Instant::now();

    let (old_key, new_share, vss_schemes, round3_msg_new) = task::spawn_blocking(move || {
        let (new_share, vss_schemes, round3_msg) = round3_new(
            self_id,
            round1_msgs_old,
            &old_key.keys_linear.y,
            round2_bc_msgs,
            round2_p2p_msgs,
        );
        (old_key, new_share, vss_schemes, round3_msg)
    })
    .await
    .unwrap();
    comp_time.push(round_start.elapsed().as_millis());

    let round3_msgs = if let BCType::Optimized = config.bc_type {
        sync.sync_barrier_default_bc_send_hash(round3_msg_new, bc_hash.unwrap(), sender, receiver)
            .await
    } else {
        sync.sync_barrier_default_bc(round3_msg_new, sender, receiver)
            .await
    };
    total_time.push(round_start.elapsed().as_millis());
    let round_start = Instant::now();

    let (X_i_vec, own_vss_scheme) = task::spawn_blocking(move || {
        out_all(self_id, round3_msgs, threshold, num_players, vss_schemes)
    })
    .await
    .unwrap();

    comp_time.push(round_start.elapsed().as_millis());
    let total = start_time.elapsed().as_millis();

    let mes = Measurement {
        total,
        per_round_computation: comp_time,
        per_round_total: total_time,
    };

    let new_key = LocalKey {
        paillier_dk: paillier_private,
        pk_vec: X_i_vec,
        keys_linear: SharedKeys {
            y: old_key.keys_linear.y,
            x_i: new_share,
        },
        paillier_key_vec: paillier_pubkeys,
        y_sum_s: old_key.y_sum_s,
        h1_h2_n_tilde_vec: range_proof_setups,
        vss_scheme: own_vss_scheme,
        i: self_id,
        t: threshold,
        n: num_players,
    };
    (mes, new_key)
}

fn round1_old(
    old_key: &LocalKey<Secp256k1>,
    new_threshold: u16,
    new_num_players: u16,
) -> (Round1MsgOld, Round2MsgOld, Vec<(Id, Round2P2P)>) {
    // Note, here indices start from 0, i.e. players: 0..n-1. This is required for lagrange
    let old_players: Vec<Id> = (0..old_key.n).collect();
    // Get lagrange coefficient
    let lagrange = VerifiableSS::<Secp256k1>::map_share_to_new_params(
        &old_key.vss_scheme.parameters,
        old_key.i - 1,
        &old_players,
    );
    // Get w_i = l_i * x_i
    let w_i = old_key.keys_linear.x_i.clone() * lagrange;
    // Get Feldman VSS
    let (vss_scheme, shares) =
        VerifiableSS::<Secp256k1>::share(new_threshold, new_num_players, &w_i);

    // Compute commitment with 256 bit blind factor
    let (com, blind) = compute_vss_com(&vss_scheme);

    let round2_msg = Round2MsgOld {
        vss_scheme,
        blind_factor: blind,
    };
    let round2_p2p_msgs = shares
        .to_vec()
        .into_iter()
        .enumerate()
        .map(|(i, share)| {
            (
                i as u16 + 1,
                Round2P2P {
                    secret_share: share,
                },
            )
        })
        .collect();
    (Round1MsgOld { com }, round2_msg, round2_p2p_msgs)
}

fn round1_new() -> (
    Round1MsgNew,
    // Paillier private key
    DecryptionKey,
) {
    // Generate new paillier key pair
    let (paillier_pub, paillier_priv) = Paillier::keypair().keys();
    // Generate range proof setup
    let (N_tilde, h1, h2, xhi, xhi_inv) = generate_h1_h2_N_tilde();
    let range_proof_setup = DLogStatement {
        N: N_tilde.clone(),
        g: h1.clone(),
        ni: h2.clone(),
    };
    // ZKPs
    // Paillier ZKP
    let paillier_zkp = NiCorrectKeyProof::proof(&paillier_priv, None);

    let dlog_statement_base_h2 = DLogStatement {
        N: N_tilde,
        g: h2,
        ni: h1,
    };
    let proof_base_h1 = CompositeDLogProof::prove(&range_proof_setup, &xhi);
    let proof_base_h2 = CompositeDLogProof::prove(&dlog_statement_base_h2, &xhi_inv);

    let msg_new = Round1MsgNew {
        paillier_pub,
        range_proof_setup,
        paillier_zkp,
        range_proof_setup_zkps: (proof_base_h1, proof_base_h2),
    };

    (msg_new, paillier_priv)
}

// Required for key resharing
fn round1_new_diffied_hellman_setup() -> (Round1DiffieHellmanMsg, Scalar<Secp256k1>) {
    // Sample new diffie hellman point for updated encrytion keys
    let diffie_hellman_secret = Scalar::<Secp256k1>::random();
    let diffie_hellman_point = Point::<Secp256k1>::generator() * &diffie_hellman_secret;

    let msg = Round1DiffieHellmanMsg {
        diffie_hellman: diffie_hellman_point,
    };

    (msg, diffie_hellman_secret)
}

fn round2_new(
    self_id: Id,
    msgs_round1: Vec<Round1MsgNew>,
) -> (Vec<EncryptionKey>, Vec<DLogStatement>) {
    // Check if keys are the same
    let mut paillier_pub_keys = Vec::new();
    let mut range_proof_setups = Vec::new();
    msgs_round1.into_iter().enumerate().for_each(|(id, msg)| {
        if !(id as u16 + 1 == self_id) {
            assert!(
                msg.paillier_pub.n.bit_length() >= PAILLIER_MIN_BIT_LENGTH
                    && msg.paillier_pub.n.bit_length() <= PAILLIER_MAX_BIT_LENGTH,
                "Paillier key does not have correct bit length"
            );

            assert!(
                msg.paillier_zkp
                    .verify(&msg.paillier_pub, zk_paillier::zkproofs::SALT_STRING)
                    .is_ok(),
                "Paillier ZKP is not valid."
            );

            assert!(
                msg.range_proof_setup.N.bit_length() >= PAILLIER_MIN_BIT_LENGTH
                    && msg.range_proof_setup.N.bit_length() <= PAILLIER_MAX_BIT_LENGTH,
                "Range proof setup modulus bit length is incorrect"
            );

            let dlog_statement_base_h2 = DLogStatement {
                N: msg.range_proof_setup.N.clone(),
                g: msg.range_proof_setup.ni.clone(),
                ni: msg.range_proof_setup.g.clone(),
            };

            assert!(
                msg.range_proof_setup_zkps
                    .0
                    .verify(&msg.range_proof_setup)
                    .is_ok()
                    && msg
                        .range_proof_setup_zkps
                        .1
                        .verify(&dlog_statement_base_h2)
                        .is_ok(),
                "Range proof setup ZKPs are invalid."
            );
        }
        paillier_pub_keys.push(msg.paillier_pub);
        range_proof_setups.push(msg.range_proof_setup);
    });
    (paillier_pub_keys, range_proof_setups)
}

fn round2_old_get_enc_keys_resharing(
    self_id: Id,
    diffie_hellman_msgs: Vec<Round1DiffieHellmanMsg>,
    new_players: &Vec<Id>,
    key: &LocalKey<Secp256k1>,
) -> EncKeys {
    let enc_keys = diffie_hellman_msgs
        .into_iter()
        .zip(new_players.iter().filter(|id| **id != self_id))
        .map(|(msg, id)| {
            (
                *id,
                SecretEncKey::from_diffie_hellman(&msg.diffie_hellman, &key.keys_linear.x_i),
            )
        })
        .collect();
    EncKeys {
        keys: enc_keys,
        self_id,
    }
}

fn round2_get_enc_keys_refreshing(self_id: Id, old_key: &LocalKey<Secp256k1>) -> EncKeys {
    let mut key_map = HashMap::new();

    old_key.pk_vec.iter().enumerate().for_each(|(id, X_i)| {
        if id as Id + 1 != self_id {
            let symm_key = SecretEncKey::from_diffie_hellman(X_i, &old_key.keys_linear.x_i);
            key_map.insert(id as Id + 1, symm_key);
        }
    });
    EncKeys {
        self_id,
        keys: key_map,
    }
}

fn round3_new(
    self_id: Id,
    round1_msgs_old: Vec<Round1MsgOld>,
    pub_key: &Point<Secp256k1>,
    bc_msgs_round2: Vec<Round2MsgOld>,
    p2p_msgs_round2: Vec<Round2P2P>,
) -> (
    Scalar<Secp256k1>,
    Vec<VerifiableSS<Secp256k1>>,
    Round3MsgNew,
) {
    // Check if vss scheme is sharing of public key
    let received_pub: Point<Secp256k1> = bc_msgs_round2
        .iter()
        .map(|msg| &msg.vss_scheme.commitments[0])
        .sum();
    assert!(&received_pub == pub_key, "Pub keys do not match");
    let mut secret_shares: Vec<Scalar<Secp256k1>> = Vec::new();
    let mut vss_schemes = Vec::new();
    bc_msgs_round2
        .into_iter()
        .zip(round1_msgs_old)
        .zip(p2p_msgs_round2)
        .enumerate()
        .for_each(|(i, ((bc_round2_msg, round1_msg), p2p_round2_msg))| {
            let id = i as Id + 1;
            if id != self_id {
                // Verify commitment
                let com_ok = verify_vss_com(
                    &bc_round2_msg.vss_scheme,
                    round1_msg.com,
                    bc_round2_msg.blind_factor,
                );
                // We stop if we get an invalid commitment.
                // In a real world scenario, we should check all commitments and output all bad players
                // This is a small implementation detail and does not affect the protocol
                assert!(com_ok, "Received invalid commitment from  {}", id);

                let share_ok = bc_round2_msg
                    .vss_scheme
                    .validate_share(&p2p_round2_msg.secret_share, self_id)
                    .is_ok();
                // Again, we should output all players as for the com assertion
                assert!(share_ok, "Received invalid key share from  {}", id);
                // Add secret share to output
            }
            secret_shares.push(p2p_round2_msg.secret_share);
            vss_schemes.push(bc_round2_msg.vss_scheme);
        });

    let new_private_key_share = secret_shares.into_iter().sum::<Scalar<Secp256k1>>();

    let dlog_zkp = DLogProof::prove(&new_private_key_share);
    (
        new_private_key_share,
        vss_schemes,
        Round3MsgNew { dlog_zkp },
    )
}

fn out_all(
    self_id: Id,
    round3_msgs: Vec<Round3MsgNew>,
    threshold: u16,
    num_players: u16,
    vss_schemes: Vec<VerifiableSS<Secp256k1>>,
) -> (Vec<Point<Secp256k1>>, VerifiableSS<Secp256k1>) {
    let params = Parameters {
        share_count: num_players,
        threshold,
    };
    // Vector is needed because they use this only to get the number of players n for whatever reason
    // The actual points are not used whatsoever
    let dummy_vec: Vec<_> = (0..params.share_count)
        .into_iter()
        .map(|_| Point::<Secp256k1>::zero())
        .collect();
    let dlog_zkps: Vec<_> = round3_msgs.into_iter().map(|msg| msg.dlog_zkp).collect();
    // Verify dlog proofs, error contains full list of bad actors
    Keys::verify_dlog_proofs_check_against_vss(&params, &dlog_zkps, &dummy_vec, &vss_schemes)
        .unwrap();
    let X_i_vec = dlog_zkps.into_iter().map(|zkp| zkp.pk).collect();
    let own_vss_scheme = vss_schemes[self_id as usize - 1].clone();
    (X_i_vec, own_vss_scheme)
}

fn compute_vss_com(vss: &VerifiableSS<Secp256k1>) -> (HashDigest, Vec<u8>) {
    let mut com_bytes: Vec<Vec<u8>> = vss
        .commitments
        .iter()
        .map(|point| point.to_bytes(true).to_vec())
        .collect();
    let blind_factor = BigInt::sample(SECURITY).to_bytes();
    com_bytes.push(blind_factor.clone());
    (hash_many(&com_bytes), blind_factor)
}

fn verify_vss_com(vss: &VerifiableSS<Secp256k1>, com: HashDigest, blind_factor: Vec<u8>) -> bool {
    let mut com_bytes: Vec<Vec<u8>> = vss
        .commitments
        .iter()
        .map(|point| point.to_bytes(true).to_vec())
        .collect();
    com_bytes.push(blind_factor);
    let ver_hash = hash_many(&com_bytes);
    ver_hash == com
}
