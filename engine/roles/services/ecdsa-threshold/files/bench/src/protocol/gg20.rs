#![allow(non_snake_case)]
use std::collections::HashMap;
use std::iter;
use std::time::Instant;

use curv::arithmetic::Converter;
use curv::cryptographic_primitives::proofs::sigma_correct_homomorphic_elgamal_enc::HomoELGamalProof;
use curv::cryptographic_primitives::proofs::sigma_valid_pedersen::PedersenProof;
use curv::elliptic::curves::{Point, Scalar, Secp256k1};
use curv::BigInt;
use kzen_paillier::EncryptionKey;
use multi_party_ecdsa::protocols::multi_party_ecdsa::gg_2020::party_i::{
    verify, KeyGenDecommitMessage1, Keys, LocalSignature, SignDecommitPhase1, SignKeys,
    SignatureRecid,
};
use multi_party_ecdsa::protocols::multi_party_ecdsa::gg_2020::party_i::{
    Parameters, SignBroadcastPhase1,
};
use multi_party_ecdsa::protocols::multi_party_ecdsa::gg_2020::state_machine::keygen::{
    LocalKey, ProceedError,
};
use multi_party_ecdsa::utilities::mta::{MessageA, MessageB};
use multi_party_ecdsa::utilities::zk_pdl_with_slack::PDLwSlackProof;
use sha2::Sha256;
use tokio::task;
use zk_paillier::zkproofs::DLogStatement;

use crate::network::round::EncKeys;
use crate::util::config::BCType;
use crate::util::crypto::{PrivKey, PubKey, SecretEncKey};
use crate::util::measurement::Measurement;
use crate::{
    network::broadcast_network::{BroadcastReceiver, BroadcastSender, Id},
    network::round::Sync,
    util::config::Config,
};

/// GG20 DKG protocol.
pub async fn run_gg20_keygen(
    self_id: Id,
    config: &Config,
    priv_key: &PrivKey,
    pub_keys: &Vec<(Id, PubKey)>,
    sender: &impl BroadcastSender,
    receiver: &mut impl BroadcastReceiver,
) -> (Measurement, LocalKey<Secp256k1>) {
    let config = config.clone();

    let mut per_round_computation: Vec<u128> = Vec::new();
    let mut per_round_total: Vec<u128> = Vec::new();

    let mut sync = Sync::new(
        self_id,
        (1..=config.num_players).collect(),
        pub_keys,
        priv_key,
    );

    // Round 1
    let start_time = Instant::now();

    let ((bc1, decom1), party_keys) = task::spawn_blocking(move || {
        let party_keys = Keys::create(self_id as usize);
        let out = party_keys.phase1_broadcast_phase3_proof_of_correct_key_proof_of_correct_h1h2();
        (out, party_keys)
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

    // Round 2
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
            for i in 1..=config.num_players {
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
                threshold: config.threshold,
                share_count: config.num_players,
            };

            let vss_result = {
                party_keys
                    .phase1_verify_com_phase3_verify_correct_key_verify_dlog_phase2_distribute(
                        &params,
                        &decoms_round2,
                        &coms_round1,
                    )
                    .map_err(ProceedError::Round2VerifyCommitments)
                    .unwrap()
            };

            let vss_scheme = vss_result.0;
            let p2p_msgs = vss_result
                .1
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

    // Round 4
    let start_time_round4 = Instant::now();
    let (shared_keys, dlog_proof, party_keys, params, vss_schemes_round3, y_vec) =
        task::spawn_blocking(move || {
            let (shared_keys, dlog_proof) = party_keys
                .phase2_verify_vss_construct_keypair_phase3_pok_dlog(
                    &params,
                    &y_vec,
                    &shares_round3,
                    &vss_schemes_round3,
                    self_id as usize,
                )
                .map_err(ProceedError::Round3VerifyVssConstruct)
                .unwrap();
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

    let (dlog_proofs, params, vss_schemes_round3) = task::spawn_blocking(move || {
        Keys::verify_dlog_proofs_check_against_vss(
            &params,
            &dlog_proofs,
            &y_vec,
            &vss_schemes_round3,
        )
        .map_err(ProceedError::Round4VerifyDLogProof)
        .unwrap();

        (dlog_proofs, params, vss_schemes_round3)
    })
    .await
    .unwrap();

    per_round_computation.push(start_time_output.elapsed().as_millis());
    let total = start_time.elapsed().as_millis();

    let pk_vec = (0..params.share_count as usize)
        .map(|i| dlog_proofs[i].pk.clone())
        .collect::<Vec<Point<Secp256k1>>>();

    let paillier_key_vec = (0..params.share_count)
        .map(|i| coms_round1[i as usize].e.clone())
        .collect::<Vec<EncryptionKey>>();
    let h1_h2_n_tilde_vec = coms_round1
        .iter()
        .map(|bc1| bc1.dlog_statement.clone())
        .collect::<Vec<DLogStatement>>();

    let local_key = LocalKey {
        paillier_dk: party_keys.dk,
        pk_vec,

        keys_linear: shared_keys.clone(),
        paillier_key_vec,
        y_sum_s: y_sum,
        h1_h2_n_tilde_vec,

        vss_scheme: vss_schemes_round3[usize::from(self_id - 1)].clone(),

        i: self_id,
        t: config.threshold,
        n: config.num_players,
    };
    let measurement = Measurement {
        total,
        per_round_computation,
        per_round_total,
    };

    (measurement, local_key)
}

/// Offline phase of GG20 signature protocol.
pub async fn run_sig_offline(
    self_id: Id,
    signers: Vec<Id>,
    local_key: &LocalKey<Secp256k1>,
    pub_keys: &Vec<(Id, PubKey)>,
    priv_key: &PrivKey,
    sender: &impl BroadcastSender,
    receiver: &mut impl BroadcastReceiver,
) -> (Measurement, PreSig) {
    let mut sync = Sync::new(self_id, signers.clone(), pub_keys, priv_key);

    let local_key = local_key.clone();

    let mut signer_index = 1;
    for id in &signers {
        if *id == self_id {
            break;
        }
        signer_index += 1;
    }
    let start_time = Instant::now();
    let mut per_round_computation: Vec<u128> = Vec::new();
    let mut per_round_total: Vec<u128> = Vec::new();

    let ((round1_msg, m_a, _bc1, decom1, sign_keys), signers, local_key) =
        task::spawn_blocking(move || {
            (
                round1(signer_index, &signers, &local_key),
                signers,
                local_key,
            )
        })
        .await
        .unwrap();

    per_round_computation.push(start_time.elapsed().as_millis());

    let (bc_hash, round1_msgs) = sync
        .sync_barrier_default_bc_get_hash(round1_msg, sender, receiver)
        .await;

    per_round_total.push(start_time.elapsed().as_millis());
    let round2_start_time = Instant::now();

    let ((round2_send_msgs, beta_vec, ni_vec, bc_vec, m_a_vec), signers, sign_keys, local_key) =
        task::spawn_blocking(move || {
            (
                round2(round1_msgs, signer_index, &signers, &sign_keys, &local_key),
                signers,
                sign_keys,
                local_key,
            )
        })
        .await
        .unwrap();

    per_round_computation.push(round2_start_time.elapsed().as_millis());

    let p2p_msgs = round2_send_msgs
        .into_iter()
        .map(|(sign_i, msg)| (signers[sign_i as usize - 1], msg))
        .collect();

    let round2_msgs = sync
        .sync_barrier_default_p2p_no_enc(p2p_msgs, sender, receiver)
        .await;

    per_round_total.push(round2_start_time.elapsed().as_millis());
    let round3_start_time = Instant::now();

    let (
        (round3_msg, m_b_gamma_s, _delta_i, t_i, l_i, sigma_i, _t_i_proof),
        signers,
        local_key,
        sign_keys,
        _beta_vec,
        _ni_vec,
    ) = task::spawn_blocking(move || {
        (
            round3(
                round2_msgs,
                signer_index,
                &signers,
                &local_key,
                &sign_keys,
                &beta_vec,
                &ni_vec,
            ),
            signers,
            local_key,
            sign_keys,
            beta_vec,
            ni_vec,
        )
    })
    .await
    .unwrap();

    per_round_computation.push(round3_start_time.elapsed().as_millis());

    let (bc_hash, round3_msgs) = sync
        .sync_barrier_default_bc_get_and_send_hash(round3_msg, bc_hash, sender, receiver)
        .await;
    per_round_total.push(round3_start_time.elapsed().as_millis());

    let round4_start_time = Instant::now();

    let ((round4_msg, delta_inv, t_vec), signers, _decom1) =
        task::spawn_blocking(move || (round4(round3_msgs, &signers, &decom1), signers, decom1))
            .await
            .unwrap();

    per_round_computation.push(round4_start_time.elapsed().as_millis());

    let (bc_hash, round4_msgs) = sync
        .sync_barrier_default_bc_get_and_send_hash(round4_msg, bc_hash, sender, receiver)
        .await;

    per_round_total.push(round4_start_time.elapsed().as_millis());

    let round5_start_time = Instant::now();

    let ((round5_msg, R, _R_dash, _phase5_proofs_vec), signers, sign_keys, local_key) =
        task::spawn_blocking(move || {
            (
                round5(
                    round4_msgs,
                    signer_index,
                    &signers,
                    &sign_keys,
                    &local_key,
                    &m_b_gamma_s,
                    &bc_vec,
                    &delta_inv,
                    m_a,
                ),
                signers,
                sign_keys,
                local_key,
            )
        })
        .await
        .unwrap();

    per_round_computation.push(round5_start_time.elapsed().as_millis());

    let (bc_hash, round5_msgs) = sync
        .sync_barrier_default_bc_get_and_send_hash(round5_msg, bc_hash, sender, receiver)
        .await;

    per_round_total.push(round5_start_time.elapsed().as_millis());

    let round6_start_time = Instant::now();

    let ((round6_msg, _S_i, _homo_elgamal_proof), signers, local_key, R, sigma_i) =
        task::spawn_blocking(move || {
            (
                round6(
                    round5_msgs,
                    &signers,
                    &local_key,
                    &R,
                    &m_a_vec,
                    t_i,
                    &sigma_i,
                    l_i,
                ),
                signers,
                local_key,
                R,
                sigma_i,
            )
        })
        .await
        .unwrap();

    per_round_computation.push(round6_start_time.elapsed().as_millis());

    let (bc_hash, round6_msgs) = sync
        .sync_barrier_default_bc_get_and_send_hash(round6_msg, bc_hash, sender, receiver)
        .await;

    // Last round of ACK messages
    sync.get_and_check_last_round_hashes_default(bc_hash, sender, receiver)
        .await;
    per_round_total.push(round6_start_time.elapsed().as_millis());

    let out_start_time = Instant::now();

    let (local_key, _signers, R, _t_vec) = task::spawn_blocking(move || {
        verification(round6_msgs, &signers, &local_key, &R, &t_vec);
        (local_key, signers, R, t_vec)
    })
    .await
    .unwrap();

    per_round_computation.push(out_start_time.elapsed().as_millis());

    let total = start_time.elapsed().as_millis();

    let mes = Measurement {
        total,
        per_round_total,
        per_round_computation,
    };

    let offline_out = PreSig {
        local_key,
        sign_keys,
        R,
        sigma_i,
    };

    (mes, offline_out)
}

#[derive(Clone, Debug)]
pub struct PreSig {
    local_key: LocalKey<Secp256k1>,
    sign_keys: SignKeys,
    R: Point<Secp256k1>,
    sigma_i: Scalar<Secp256k1>,
}

/// Online phase of GG20 signature protocol.
pub async fn run_sig_online(
    self_id: Id,
    signers: Vec<Id>,
    pre_sig: PreSig,
    msg_hash: &Vec<u8>,
    priv_key: &PrivKey,
    pub_keys: &Vec<(Id, PubKey)>,
    sender: &impl BroadcastSender,
    receiver: &mut impl BroadcastReceiver,
) -> (Measurement, SignatureRecid) {
    let mut sync = Sync::new(self_id, signers.clone(), pub_keys, priv_key);

    let msg_hash = BigInt::from_bytes(&msg_hash);

    let start_time = Instant::now();
    let mut comp_ts = Vec::new();

    let (local_sig, msg_hash, pre_sig) = task::spawn_blocking(move || {
        (
            LocalSignature::phase7_local_sig(
                &pre_sig.sign_keys.k_i,
                &msg_hash,
                &pre_sig.R,
                &pre_sig.sigma_i,
                &pre_sig.local_key.y_sum_s,
            ),
            msg_hash,
            pre_sig,
        )
    })
    .await
    .unwrap();

    comp_ts.push(start_time.elapsed().as_millis());
    // Here no robust broadcast is required
    let all_s_i = sync
        .sync_barrier_default_bc(local_sig.s_i.clone(), sender, receiver)
        .await;

    let total_ts = start_time.elapsed().as_millis();

    let sig = task::spawn_blocking(move || {
        let other_s_i: Vec<_> = all_s_i
            .into_iter()
            .zip(signers)
            .filter(|(_, id)| *id != self_id)
            .map(|(s_i, _)| s_i)
            .collect();

        local_sig.output_signature(&other_s_i).unwrap()
    })
    .await
    .unwrap();
    comp_ts.push(start_time.elapsed().as_millis());
    let total = start_time.elapsed().as_millis();
    assert!(verify(&sig, &pre_sig.local_key.y_sum_s, &msg_hash).is_ok());
    let mes = Measurement {
        total,
        per_round_computation: vec![comp_ts[0], comp_ts[1] - total_ts],
        per_round_total: vec![total_ts],
    };
    (mes, sig)
}

fn round1(
    sig_index: u16,
    signers: &Vec<Id>,
    local_key: &LocalKey<Secp256k1>,
) -> (
    (MessageA, SignBroadcastPhase1),
    (MessageA, BigInt),
    SignBroadcastPhase1,
    SignDecommitPhase1,
    SignKeys,
) {
    let sign_keys = SignKeys::create(
        &local_key.keys_linear.x_i,
        &local_key.vss_scheme.clone(),
        usize::from(signers[usize::from(sig_index - 1)]) - 1,
        &signers
            .iter()
            .map(|&i| usize::from(i) - 1)
            .collect::<Vec<_>>(),
    );
    let (bc1, decom1) = sign_keys.phase1_broadcast();

    let party_ek = local_key.paillier_key_vec[usize::from(local_key.i - 1)].clone();
    // Fixes bug in library implementation
    let mut signer_setups = Vec::new();
    for id in signers {
        signer_setups.push(local_key.h1_h2_n_tilde_vec[*id as usize - 1].clone());
    }

    let m_a = MessageA::a(&sign_keys.k_i, &party_ek, &signer_setups);

    let msg = (m_a.0.clone(), bc1.clone());

    (msg, m_a, bc1, decom1, sign_keys)
}

fn round2(
    input_msgs: Vec<(MessageA, SignBroadcastPhase1)>,
    sign_index: u16,
    signers: &Vec<Id>,
    sign_keys: &SignKeys,
    local_key: &LocalKey<Secp256k1>,
) -> (
    Vec<(Id, (MessageB, MessageB))>,
    Vec<Scalar<Secp256k1>>,
    Vec<Scalar<Secp256k1>>,
    Vec<SignBroadcastPhase1>,
    Vec<MessageA>,
) {
    let (m_a_vec, bc_vec): (Vec<_>, Vec<_>) = input_msgs.into_iter().unzip();

    let mut m_b_gamma_vec = Vec::new();
    let mut beta_vec = Vec::new();
    let mut m_b_w_vec = Vec::new();
    let mut ni_vec = Vec::new();

    let ttag = signers.len();
    let l_s: Vec<_> = signers
        .iter()
        .cloned()
        .map(|i| usize::from(i) - 1)
        .collect();
    let i = usize::from(sign_index - 1);
    // Fixes bug in state machine implementation
    let mut signer_setups = Vec::new();
    for id in signers {
        signer_setups.push(local_key.h1_h2_n_tilde_vec[*id as usize - 1].clone());
    }

    for j in 0..ttag - 1 {
        let ind = if j < i { j } else { j + 1 };
        let (m_b_gamma, beta_gamma, _beta_randomness, _beta_tag) = MessageB::b(
            &sign_keys.gamma_i,
            &local_key.paillier_key_vec[l_s[ind]],
            m_a_vec[ind].clone(),
            &signer_setups,
        )
        .expect("Incorrect Alice's range proof in MtA");
        let (m_b_w, beta_wi, _, _) = MessageB::b(
            &sign_keys.w_i,
            &local_key.paillier_key_vec[l_s[ind]],
            m_a_vec[ind].clone(),
            &signer_setups,
        )
        .expect("Incorrect Alice's range proof in MtA");

        m_b_gamma_vec.push(m_b_gamma);
        beta_vec.push(beta_gamma);
        m_b_w_vec.push(m_b_w);
        ni_vec.push(beta_wi);
    }

    let party_indices = (1..=signers.len())
        .map(|j| u16::try_from(j).unwrap())
        .filter(|&j| j != sign_index);
    let out_msgs: Vec<_> = party_indices
        .zip(m_b_gamma_vec)
        .zip(m_b_w_vec)
        .map(|((j, gamma_i), w_i)| (j, (gamma_i.clone(), w_i.clone())))
        .collect();
    (out_msgs, beta_vec, ni_vec, bc_vec, m_a_vec)
}

// Messages do not contain self message
fn round3(
    input_msgs: Vec<(MessageB, MessageB)>,
    signer_index: u16,
    signers: &Vec<Id>,
    local_key: &LocalKey<Secp256k1>,
    sign_keys: &SignKeys,
    beta_vec: &Vec<Scalar<Secp256k1>>,
    ni_vec: &Vec<Scalar<Secp256k1>>,
) -> (
    (
        Scalar<Secp256k1>,
        Point<Secp256k1>,
        PedersenProof<Secp256k1, Sha256>,
    ),
    Vec<MessageB>,
    Scalar<Secp256k1>,
    Point<Secp256k1>,
    Scalar<Secp256k1>,
    Scalar<Secp256k1>,
    PedersenProof<Secp256k1, Sha256>,
) {
    let (m_b_gamma_s, m_b_w_s): (Vec<_>, Vec<_>) = input_msgs.into_iter().unzip();

    let mut alpha_vec = Vec::new();
    let mut miu_vec = Vec::new();

    let ttag = signers.len();
    let index = usize::from(signer_index) - 1;
    let l_s: Vec<_> = signers
        .iter()
        .cloned()
        .map(|i| usize::from(i) - 1)
        .collect();
    let g_w_vec = SignKeys::g_w_vec(&local_key.pk_vec[..], &l_s[..], &local_key.vss_scheme);
    for j in 0..ttag - 1 {
        let ind = if j < index { j } else { j + 1 };
        let m_b = m_b_gamma_s[j].clone();

        let alpha_ij_gamma = m_b
            .verify_proofs_get_alpha(&local_key.paillier_dk, &sign_keys.k_i)
            .expect("wrong dlog or m_b");
        let m_b = m_b_w_s[j].clone();
        let alpha_ij_wi = m_b
            .verify_proofs_get_alpha(&local_key.paillier_dk, &sign_keys.k_i)
            .expect("wrong dlog or m_b");
        assert_eq!(m_b.b_proof.pk, g_w_vec[ind]);

        alpha_vec.push(alpha_ij_gamma.0);
        miu_vec.push(alpha_ij_wi.0);
    }

    let delta_i = sign_keys.phase2_delta_i(&alpha_vec, beta_vec);

    let sigma_i = sign_keys.phase2_sigma_i(&miu_vec, ni_vec);
    let (t_i, l_i, t_i_proof) = SignKeys::phase3_compute_t_i(&sigma_i);
    let out_msg = (delta_i.clone(), t_i.clone(), t_i_proof.clone());
    (out_msg, m_b_gamma_s, delta_i, t_i, l_i, sigma_i, t_i_proof)
}

// Input_msgs: Has to include self
fn round4(
    input_msgs: Vec<(
        Scalar<Secp256k1>,
        Point<Secp256k1>,
        PedersenProof<Secp256k1, Sha256>,
    )>,
    signers: &Vec<Id>,
    decom1: &SignDecommitPhase1,
) -> (SignDecommitPhase1, Scalar<Secp256k1>, Vec<Point<Secp256k1>>) {
    let mut delta_vec = Vec::new();
    let mut t_vec = Vec::new();
    let mut t_proof_vec = Vec::new();
    for (delta, t, t_proof) in input_msgs {
        delta_vec.push(delta);
        t_vec.push(t);
        t_proof_vec.push(t_proof);
    }

    let delta_inv = SignKeys::phase3_reconstruct_delta(&delta_vec);
    let ttag = signers.len();
    for proof in t_proof_vec.iter().take(ttag) {
        PedersenProof::verify(proof).expect("error T proof");
    }

    let msg = decom1.clone();
    (msg, delta_inv, t_vec)
}

// input_msgs:
fn round5(
    input_msgs: Vec<SignDecommitPhase1>,
    signer_index: u16,
    signers: &Vec<Id>,
    sign_keys: &SignKeys,
    local_key: &LocalKey<Secp256k1>,
    mb_gamma_s: &Vec<MessageB>,
    bc_vec: &Vec<SignBroadcastPhase1>,
    delta_inv: &Scalar<Secp256k1>,
    m_a: (MessageA, BigInt),
) -> (
    (Point<Secp256k1>, Vec<PDLwSlackProof>),
    Point<Secp256k1>,
    Point<Secp256k1>,
    Vec<PDLwSlackProof>,
) {
    let decom_vec: Vec<_> = input_msgs;

    let ttag = signers.len();
    let b_proof_vec: Vec<_> = (0..ttag - 1).map(|i| &mb_gamma_s[i].b_proof).collect();
    let R = SignKeys::phase4(
        delta_inv,
        &b_proof_vec[..],
        decom_vec,
        &bc_vec,
        usize::from(signer_index - 1),
    )
    .expect(""); //TODO: propagate the error
    let R_dash = &R * &sign_keys.k_i;

    // each party sends first message to all other parties
    let mut phase5_proofs_vec = Vec::new();
    let l_s: Vec<_> = signers
        .iter()
        .cloned()
        .map(|i| usize::from(i) - 1)
        .collect();
    let index = usize::from(signer_index - 1);
    for j in 0..ttag - 1 {
        let ind = if j < index { j } else { j + 1 };
        let proof = LocalSignature::phase5_proof_pdl(
            &R_dash,
            &R,
            &m_a.0.c,
            &local_key.paillier_key_vec[l_s[index]],
            &sign_keys.k_i,
            &m_a.1,
            &local_key.h1_h2_n_tilde_vec[l_s[ind]],
        );

        phase5_proofs_vec.push(proof);
    }

    let out_msg = (R_dash.clone(), phase5_proofs_vec.clone());

    (out_msg, R, R_dash, phase5_proofs_vec)
}

// input_msgs: Includes self
fn round6(
    input_msgs: Vec<(Point<Secp256k1>, Vec<PDLwSlackProof>)>,
    signers: &Vec<Id>,
    local_key: &LocalKey<Secp256k1>,
    R: &Point<Secp256k1>,
    m_a_vec: &Vec<MessageA>,
    t_i: Point<Secp256k1>,
    sigma_i: &Scalar<Secp256k1>,
    l_i: Scalar<Secp256k1>,
) -> (
    (Point<Secp256k1>, HomoELGamalProof<Secp256k1, Sha256>),
    Point<Secp256k1>,
    HomoELGamalProof<Secp256k1, Sha256>,
) {
    let (r_dash_vec, pdl_proof_mat_inc_me): (Vec<_>, Vec<_>) = input_msgs.into_iter().unzip();

    let l_s: Vec<_> = signers
        .iter()
        .cloned()
        .map(|i| usize::from(i) - 1)
        .collect();
    let ttag = signers.len();
    for i in 0..ttag {
        LocalSignature::phase5_verify_pdl(
            &pdl_proof_mat_inc_me[i],
            &r_dash_vec[i],
            R,
            &m_a_vec[i].c,
            &local_key.paillier_key_vec[l_s[i]],
            &local_key.h1_h2_n_tilde_vec,
            &l_s,
            i,
        )
        .expect("phase5 verify pdl error");
    }
    LocalSignature::phase5_check_R_dash_sum(&r_dash_vec).expect("R_dash error");

    let (S_i, homo_elgamal_proof) =
        LocalSignature::phase6_compute_S_i_and_proof_of_consistency(R, &t_i, &sigma_i, &l_i);
    let out_msg = (S_i.clone(), homo_elgamal_proof.clone());

    (out_msg, S_i, homo_elgamal_proof)
}

// input_msg: including self
fn verification(
    input_msgs: Vec<(Point<Secp256k1>, HomoELGamalProof<Secp256k1, Sha256>)>,
    signers: &Vec<Id>,
    local_key: &LocalKey<Secp256k1>,
    R: &Point<Secp256k1>,
    t_vec: &Vec<Point<Secp256k1>>,
) {
    let (S_i_vec, hegp_vec): (Vec<_>, Vec<_>) = input_msgs.into_iter().unzip();
    let R_vec: Vec<_> = iter::repeat(R.clone()).take(signers.len()).collect();

    LocalSignature::phase6_verify_proof(&S_i_vec, &hegp_vec, &R_vec, t_vec).unwrap();
    LocalSignature::phase6_check_S_i_sum(&local_key.y_sum_s, &S_i_vec).unwrap();
}
