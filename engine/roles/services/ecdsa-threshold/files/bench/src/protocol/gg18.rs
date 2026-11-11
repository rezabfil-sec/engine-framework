#![allow(non_snake_case)]
use crate::network::round::{EncKeys, Sync};
use crate::util::config::{BCType, Config};
use crate::util::crypto::{PrivKey, PubKey, SecretEncKey};
use multi_party_ecdsa::protocols::multi_party_ecdsa::gg_2018::party_i::SignatureRecid;
use std::collections::HashMap;
use std::time::Instant;
use tokio::task;

use curv::cryptographic_primitives::proofs::sigma_correct_homomorphic_elgamal_enc::HomoELGamalProof;
use curv::{
    arithmetic::traits::Converter,
    cryptographic_primitives::{
        proofs::sigma_dlog::DLogProof, secret_sharing::feldman_vss::VerifiableSS,
    },
    elliptic::curves::{Point, Scalar, Secp256k1},
    BigInt,
};
use kzen_paillier::EncryptionKey;
use multi_party_ecdsa::protocols::multi_party_ecdsa::gg_2018::party_i::{
    KeyGenDecommitMessage1, Keys, LocalSignature, Parameters, PartyPrivate, Phase5ADecom1,
    SharedKeys, SignBroadcastPhase1, SignKeys,
};
use multi_party_ecdsa::utilities::mta::{MessageA, MessageB};
use sha2::Sha256;

use crate::network::broadcast_network::{BroadcastReceiver, BroadcastSender, Id};
use crate::util::measurement::Measurement;

#[derive(Clone, Debug)]
pub struct GG18Keys {
    pub party_keys: Keys,
    pub shared_keys: SharedKeys,
    pub vss_scheme_vec: Vec<VerifiableSS<Secp256k1>>,
    pub paillier_key_vector: Vec<EncryptionKey>,
    pub y_sum: Point<Secp256k1>,
}

/// GG18 DKG protocol
pub async fn run_gg18_keygen(
    self_id: Id,
    num_players: u16,
    threshold: u16,
    config: &Config,
    pub_keys: &Vec<(Id, PubKey)>,
    priv_key: &PrivKey,
    sender: &impl BroadcastSender,
    receiver: &mut impl BroadcastReceiver,
) -> (Measurement, GG18Keys) {
    let receiver = receiver;
    let mut per_round_computation: Vec<u128> = Vec::new();
    let mut per_round_total: Vec<u128> = Vec::new();

    let mut sync = Sync::new(self_id, (1..=num_players).collect(), pub_keys, priv_key);

    // Round 1
    let start_time = Instant::now();

    let ((bc1, decom1), party_keys) = task::spawn_blocking(move || {
        let party_keys = Keys::create(self_id);
        (
            party_keys.phase1_broadcast_phase3_proof_of_correct_key(),
            party_keys,
        )
    })
    .await
    .unwrap();

    per_round_computation.push(start_time.elapsed().as_millis());

    let (bc_hash, coms_round1) = match config.bc_type {
        crate::util::config::BCType::BestEffort => (
            None,
            sync.sync_barrier_default_bc(bc1, sender, receiver).await,
        ),
        crate::util::config::BCType::Echo => (
            None,
            sync.sync_barrier_default_echo_bc(bc1, sender, receiver)
                .await,
        ),
        crate::util::config::BCType::Optimized => {
            let (hash, msgs) = sync
                .sync_barrier_default_bc_get_hash(bc1, sender, receiver)
                .await;
            (Some(hash), msgs)
        }
    };

    per_round_total.push(start_time.elapsed().as_millis());

    let start_time_round2 = Instant::now();
    per_round_computation.push(0);

    let decoms_round2 = if let BCType::Optimized = config.bc_type {
        sync.sync_barrier_default_bc_send_hash(decom1, bc_hash.unwrap(), sender, receiver)
            .await
    } else {
        sync.sync_barrier_default_bc(decom1, sender, receiver).await
    };

    per_round_total.push(start_time_round2.elapsed().as_millis());

    let start_time_round3 = Instant::now();

    // get symmetric encryption keys for p2p channels
    let (vss_scheme, p2p_msgs, params, y_vec, y_sum, enc_keys, party_keys, coms_round1) =
        task::spawn_blocking(move || {
            let mut enc_keys: HashMap<Id, SecretEncKey> = HashMap::new();
            for i in 1..=num_players {
                if i != self_id {
                    let decom_j: KeyGenDecommitMessage1 = decoms_round2[i as usize - 1].clone();
                    let key = SecretEncKey::from_diffie_hellman(&decom_j.y_i, &party_keys.u_i);
                    enc_keys.insert(i, key);
                }
            }

            let enc_keys = EncKeys {
                self_id,
                keys: enc_keys,
            };

            let y_vec: Vec<Point<Secp256k1>> =
                decoms_round2.clone().into_iter().map(|d| d.y_i).collect();
            let (head, tail) = y_vec.split_at(1);
            let y_sum = tail.iter().fold(head[0].clone(), |acc, x| acc + x);

            let params = Parameters {
                threshold,
                share_count: num_players,
            };
            let (vss_scheme, secret_shares, _index) = party_keys
                .phase1_verify_com_phase3_verify_correct_key_phase2_distribute(
                    &params,
                    &decoms_round2,
                    &coms_round1,
                )
                .expect("invalid key");

            let p2p_msgs = secret_shares
                .into_iter()
                .enumerate()
                .map(|(id, msg)| (id as Id + 1, msg))
                .collect();

            (
                vss_scheme,
                p2p_msgs,
                params,
                y_vec,
                y_sum,
                enc_keys,
                party_keys,
                coms_round1,
            )
        })
        .await
        .unwrap();

    per_round_computation.push(start_time_round3.elapsed().as_millis());

    let (bc_hash, (vss_schemes_round3, shares_round3)) = match config.bc_type {
        crate::util::config::BCType::BestEffort => (
            None,
            sync.sync_barrier_default_bc_and_p2p(vss_scheme, p2p_msgs, &enc_keys, sender, receiver)
                .await,
        ),
        crate::util::config::BCType::Echo => (
            None,
            sync.sync_barrier_default_echo_bc_and_p2p(
                vss_scheme, p2p_msgs, &enc_keys, sender, receiver,
            )
            .await,
        ),
        crate::util::config::BCType::Optimized => {
            let (hash, msgs_bc, msgs_p2p) = sync
                .sync_barrier_default_bc_get_hash_and_p2p(
                    vss_scheme, p2p_msgs, &enc_keys, sender, receiver,
                )
                .await;
            (Some(hash), (msgs_bc, msgs_p2p))
        }
    };

    per_round_total.push(start_time_round3.elapsed().as_millis());

    let start_time_round4 = Instant::now();

    let (shared_keys, dlog_proof, party_keys, params, vss_schemes_round3, y_vec) =
        task::spawn_blocking(move || {
            let (shared_keys, dlog_proof) = party_keys
                .phase2_verify_vss_construct_keypair_phase3_pok_dlog(
                    &params,
                    &y_vec,
                    &shares_round3,
                    &vss_schemes_round3,
                    self_id,
                )
                .expect("invalid vss");
            (
                shared_keys,
                dlog_proof,
                party_keys,
                params,
                vss_schemes_round3,
                y_vec,
            )
        })
        .await
        .unwrap();

    per_round_computation.push(start_time_round4.elapsed().as_millis());

    let dlog_proofs = if let BCType::Optimized = config.bc_type {
        sync.sync_barrier_default_bc_send_hash(dlog_proof, bc_hash.unwrap(), sender, receiver)
            .await
    } else {
        sync.sync_barrier_default_bc(dlog_proof, sender, receiver)
            .await
    };

    per_round_total.push(start_time_round4.elapsed().as_millis());

    let start_time_output = Instant::now();

    task::spawn_blocking(move || {
        Keys::verify_dlog_proofs(&params, &dlog_proofs, &y_vec).expect("Bad dlog proof");
    })
    .await
    .unwrap();

    per_round_computation.push(start_time_output.elapsed().as_millis());
    let total = start_time.elapsed().as_millis();

    let mes = Measurement {
        total,
        per_round_computation,
        per_round_total,
    };

    let keys = GG18Keys {
        paillier_key_vector: coms_round1.iter().map(|x| x.e.clone()).collect(),
        vss_scheme_vec: vss_schemes_round3,
        shared_keys,
        party_keys,
        y_sum,
    };

    (mes, keys)
}

/// GG18 Signature protocol
pub async fn run_gg18_signing(
    self_id: Id,
    keys: &GG18Keys,
    signers: Vec<Id>,
    msg: Vec<u8>,
    priv_key: &PrivKey,
    pub_keys: &Vec<(Id, PubKey)>,
    sender: &impl BroadcastSender,
    receiver: &mut impl BroadcastReceiver,
) -> (Measurement, SignatureRecid) {
    let private = PartyPrivate::set_private(keys.party_keys.clone(), keys.shared_keys.clone());
    let keys = keys.clone();

    let mut sync = Sync::new(self_id, signers.clone(), pub_keys, priv_key);

    let id_to_index: HashMap<Id, usize> =
        signers.iter().enumerate().map(|(i, id)| (*id, i)).collect();

    let get_signer_index = move |signer_id| *id_to_index.get(&signer_id).unwrap();

    let start_time = Instant::now();
    let mut per_round_computation: Vec<u128> = Vec::new();
    let mut per_round_total: Vec<u128> = Vec::new();

    let (m_a_k, keys, sign_keys, com, decom, xi_com_vec, signers_zero, signers) =
        task::spawn_blocking(move || {
            let signers_zero: Vec<u16> = signers.clone().into_iter().map(|x| x - 1).collect();

            let sign_keys = SignKeys::create(
                &private,
                // vss_scheme comes from DKG protocol -> Here player if = player index in vector
                &keys.vss_scheme_vec[usize::from(self_id - 1)],
                self_id - 1,
                &signers_zero,
            );

            let xi_com_vec = Keys::get_commitments_to_xi(&keys.vss_scheme_vec);

            let (com, decom) = sign_keys.phase1_broadcast();

            let (m_a_k, _) = MessageA::a(&sign_keys.k_i, &keys.party_keys.ek, &[]);
            (
                m_a_k,
                keys,
                sign_keys,
                com,
                decom,
                xi_com_vec,
                signers_zero,
                signers,
            )
        })
        .await
        .unwrap();

    per_round_computation.push(start_time.elapsed().as_millis());

    let (bc_hash, round1_msgs) = sync
        .sync_barrier_default_bc_get_hash((com.clone(), m_a_k), sender, receiver)
        .await;

    per_round_total.push(start_time.elapsed().as_millis());

    let round2_start_time = Instant::now();

    let (p2p_msgs, beta_vec, ni_vec, mut bc1_vec, keys, signers, sign_keys, get_signer_index) =
        task::spawn_blocking(move || {
            let bc1_vec: Vec<SignBroadcastPhase1> =
                round1_msgs.iter().map(|x| x.0.clone()).collect();
            let mut m_a_vec: Vec<MessageA> = round1_msgs.iter().map(|x| x.1.clone()).collect();
            m_a_vec.remove(get_signer_index(self_id));

            let mut m_b_gamma_send_vec: Vec<MessageB> = Vec::new();
            let mut beta_vec: Vec<Scalar<Secp256k1>> = Vec::new();
            let mut m_b_w_send_vec: Vec<MessageB> = Vec::new();
            let mut ni_vec: Vec<Scalar<Secp256k1>> = Vec::new();
            let mut j = 0;
            for id in &signers {
                if *id != self_id {
                    let (m_b_gamma, beta_gamma, _, _) = MessageB::b(
                        &sign_keys.gamma_i,
                        // Again, player id = player index
                        &keys.paillier_key_vector[*id as usize - 1],
                        m_a_vec[j].clone(),
                        &[],
                    )
                    .unwrap();
                    let (m_b_w, beta_wi, _, _) = MessageB::b(
                        &sign_keys.w_i,
                        // Again, player id = player index
                        &keys.paillier_key_vector[*id as usize - 1],
                        m_a_vec[j].clone(),
                        &[],
                    )
                    .unwrap();

                    m_b_gamma_send_vec.push(m_b_gamma);
                    m_b_w_send_vec.push(m_b_w);
                    beta_vec.push(beta_gamma);
                    ni_vec.push(beta_wi);
                    j += 1;
                }
            }

            let mut p2p_msgs: Vec<(Id, (MessageB, MessageB))> = Vec::new();
            // We need j m_b vectors do not contain entry for self index.
            let mut j = 0;
            for id in &signers {
                if *id != self_id {
                    p2p_msgs.push((
                        *id,
                        (m_b_gamma_send_vec[j].clone(), m_b_w_send_vec[j].clone()),
                    ));
                    j += 1;
                }
            }

            (
                p2p_msgs,
                beta_vec,
                ni_vec,
                bc1_vec,
                keys,
                signers,
                sign_keys,
                get_signer_index,
            )
        })
        .await
        .unwrap();

    per_round_computation.push(round2_start_time.elapsed().as_millis());

    let round2_msgs = sync
        .sync_barrier_default_p2p_no_enc(p2p_msgs, sender, receiver)
        .await;

    per_round_total.push(round2_start_time.elapsed().as_millis());

    let round3_start_time = Instant::now();

    let (delta_i, m_b_gamma_rec_vec, _m_b_w_rec_vec, sigma, signers, sign_keys) =
        task::spawn_blocking(move || {
            let m_b_gamma_rec_vec: Vec<MessageB> =
                round2_msgs.iter().map(|x| x.0.clone()).collect();
            let m_b_w_rec_vec: Vec<MessageB> = round2_msgs.iter().map(|x| x.1.clone()).collect();

            let mut alpha_vec: Vec<Scalar<Secp256k1>> = Vec::new();
            let mut miu_vec: Vec<Scalar<Secp256k1>> = Vec::new();

            let mut j = 0;
            for id in &signers {
                if *id != self_id {
                    let m_b = m_b_gamma_rec_vec[j].clone();

                    let alpha_ij_gamma = m_b
                        .verify_proofs_get_alpha(&keys.party_keys.dk, &sign_keys.k_i)
                        .expect("wrong dlog or m_b");
                    let m_b = m_b_w_rec_vec[j].clone();
                    let alpha_ij_wi = m_b
                        .verify_proofs_get_alpha(&keys.party_keys.dk, &sign_keys.k_i)
                        .expect("wrong dlog or m_b");
                    alpha_vec.push(alpha_ij_gamma.0);
                    miu_vec.push(alpha_ij_wi.0);
                    let g_w_i = Keys::update_commitments_to_xi(
                        &xi_com_vec[*id as usize - 1],
                        // For vss_scheme_vec, player id == signer index
                        &keys.vss_scheme_vec[*id as usize - 1],
                        *id - 1,
                        &signers_zero,
                    );
                    assert_eq!(m_b.b_proof.pk, g_w_i);
                    j += 1;
                }
            }

            let delta_i = sign_keys.phase2_delta_i(&alpha_vec, &beta_vec);
            let sigma = sign_keys.phase2_sigma_i(&miu_vec, &ni_vec);
            (
                delta_i,
                m_b_gamma_rec_vec,
                m_b_w_rec_vec,
                sigma,
                signers,
                sign_keys,
            )
        })
        .await
        .unwrap();

    per_round_computation.push(round3_start_time.elapsed().as_millis());

    let (bc_hash, round3_msgs) = sync
        .sync_barrier_default_bc_get_and_send_hash(delta_i, bc_hash, sender, receiver)
        .await;

    per_round_total.push(round3_start_time.elapsed().as_millis());

    let round4_start_time = Instant::now();

    let delta_inv = task::spawn_blocking(move || SignKeys::phase3_reconstruct_delta(&round3_msgs))
        .await
        .unwrap();

    per_round_computation.push(round4_start_time.elapsed().as_millis());

    let (bc_hash, mut round4_msgs) = sync
        .sync_barrier_default_bc_get_and_send_hash(decom, bc_hash, sender, receiver)
        .await;

    per_round_total.push(round4_start_time.elapsed().as_millis());

    let round5_start_time = Instant::now();
    let (phase5_com, phase5a_decom, helgamal_proof, dlog_proof_rho, local_sig, R, get_signer_index) =
        task::spawn_blocking(move || {
            let decom_i = round4_msgs.remove(get_signer_index(self_id));
            bc1_vec.remove(get_signer_index(self_id));

            let b_proof_vec = (0..m_b_gamma_rec_vec.len())
                .map(|i| &m_b_gamma_rec_vec[i].b_proof)
                .collect::<Vec<&DLogProof<Secp256k1, Sha256>>>();
            let R = SignKeys::phase4(&delta_inv, &b_proof_vec, round4_msgs, &bc1_vec)
                .expect("bad gamma_i decommit");

            // adding local g_gamma_i
            let R = R + decom_i.g_gamma_i * delta_inv;

            // we assume the message is already hashed (by the signer).
            let message_bn = BigInt::from_bytes(&msg[..]);
            let local_sig = LocalSignature::phase5_local_sig(
                &sign_keys.k_i,
                &message_bn,
                &R,
                &sigma,
                &keys.y_sum,
            );

            let (phase5_com, phase5a_decom, helgamal_proof, dlog_proof_rho) =
                local_sig.phase5a_broadcast_5b_zkproof();
            (
                phase5_com,
                phase5a_decom,
                helgamal_proof,
                dlog_proof_rho,
                local_sig,
                R,
                get_signer_index,
            )
        })
        .await
        .unwrap();
    per_round_computation.push(round5_start_time.elapsed().as_millis());

    let (bc_hash, mut round5_msgs) = sync
        .sync_barrier_default_bc_get_and_send_hash(phase5_com, bc_hash, sender, receiver)
        .await;

    per_round_total.push(round5_start_time.elapsed().as_millis());

    let round6_start_time = Instant::now();
    per_round_computation.push(0);

    let (bc_hash, mut round6_msgs) = sync
        .sync_barrier_default_bc_get_and_send_hash(
            (phase5a_decom.clone(), helgamal_proof, dlog_proof_rho),
            bc_hash,
            sender,
            receiver,
        )
        .await;

    per_round_total.push(round6_start_time.elapsed().as_millis());

    let round7_start_time = Instant::now();
    let (phase5_com2, phase5d_decom2, round6_msgs_with_self, local_sig) =
        task::spawn_blocking(move || {
            let round6_msgs_with_self = round6_msgs.clone();
            round6_msgs.remove(get_signer_index(self_id));
            round5_msgs.remove(get_signer_index(self_id));

            let phase5a_decom_vec: Vec<Phase5ADecom1> =
                round6_msgs.iter().map(|x| x.0.clone()).collect();
            let phase5a_elgamal_vec: Vec<HomoELGamalProof<Secp256k1, Sha256>> =
                round6_msgs.iter().map(|x| x.1.clone()).collect();
            let phase5a_dlog_vec: Vec<DLogProof<Secp256k1, Sha256>> =
                round6_msgs.iter().map(|x| x.2.clone()).collect();

            let (phase5_com2, phase5d_decom2) = local_sig
                .phase5c(
                    &phase5a_decom_vec,
                    &round5_msgs,
                    &phase5a_elgamal_vec,
                    &phase5a_dlog_vec,
                    &phase5a_decom.V_i,
                    &R,
                )
                .expect("Error phase 5");
            (
                phase5_com2,
                phase5d_decom2,
                round6_msgs_with_self,
                local_sig,
            )
        })
        .await
        .unwrap();
    per_round_computation.push(round7_start_time.elapsed().as_millis());

    let (bc_hash, comm5c_vec) = sync
        .sync_barrier_default_bc_get_and_send_hash(phase5_com2, bc_hash, sender, receiver)
        .await;

    per_round_total.push(round7_start_time.elapsed().as_millis());

    let round8_start_time = Instant::now();
    per_round_computation.push(0);

    let (bc_hash, decom5d_vec) = sync
        .sync_barrier_default_bc_get_and_send_hash(phase5d_decom2, bc_hash, sender, receiver)
        .await;
    per_round_total.push(round8_start_time.elapsed().as_millis());

    let round9_start_time = Instant::now();
    let (s_i, local_sig) = task::spawn_blocking(move || {
        let phase5a_decom_vec_with_self: Vec<Phase5ADecom1> =
            round6_msgs_with_self.iter().map(|x| x.0.clone()).collect();

        let s_i = local_sig
            .phase5d(&decom5d_vec, &comm5c_vec, &phase5a_decom_vec_with_self)
            .expect("bad com 5d");

        (s_i, local_sig)
    })
    .await
    .unwrap();

    per_round_computation.push(round9_start_time.elapsed().as_millis());

    let sig_shares = sync
        .sync_barrier_default_bc_send_hash(s_i, bc_hash, sender, receiver)
        .await;

    per_round_total.push(round9_start_time.elapsed().as_millis());

    let out_start_time = Instant::now();

    let sig_shares: Vec<Scalar<Secp256k1>> = sig_shares
        .into_iter()
        .zip(signers)
        .filter(|(_, id)| *id != self_id)
        .map(|x| x.0)
        .collect();

    per_round_computation.push(out_start_time.elapsed().as_millis());

    let sig = local_sig.output_signature(&sig_shares).unwrap();

    let total = start_time.elapsed().as_millis();

    let mes = Measurement {
        total,
        per_round_computation,
        per_round_total,
    };

    (mes, sig)
}
