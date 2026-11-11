#![allow(non_snake_case)]

use bls::threshold_bls;
use bls::threshold_bls::party_i::PartialSignature;
use bls::threshold_bls::utilities::ECDDHStatement;
use threshold_bls::state_machine::keygen::LocalKey;
use curv;
use curv::elliptic::curves::bls12_381::g2::GE as GE2;
use curv::elliptic::curves::bls12_381::g1::GE as GE1;
use curv::elliptic::curves::traits::ECPoint;
use anyhow::{anyhow, Result};
use bls::basic_bls::BLSSignature;
use curv::cryptographic_primitives::secret_sharing::feldman_vss::{ShamirSecretSharing, VerifiableSS};


//this struct is basically an adaption of bls::threshold_bls::party_i::combine
pub struct psign_ext {
    t: usize,
    n: usize,
    vk_vec: Vec<GE2>,
    verified_psigs: Vec<PartialSignature>,
    received_psigs: Vec<bool>,
}

impl psign_ext {
    pub fn new(threshold: u16, n_parties: u16, verification_keys: Vec<GE2>) -> psign_ext {
        psign_ext {
            t: threshold as usize,
            n: n_parties as usize,
            vk_vec: verification_keys,
            verified_psigs: vec![],
            received_psigs: vec![false; n_parties as usize],
        }
    }

    ///generates a partial signature and the message in point representation
    pub fn psign(bls_keys: LocalKey, msg: &[u8]) -> (PartialSignature, GE1) {
        let (psig, MsgPoint) = bls_keys.shared_keys.partial_sign(msg);
        (psig, MsgPoint)
    }

    ///maps the message to a point on G1
    pub fn msg_to_point(msg: &[u8]) -> GE1 {
        GE1::hash_to_curve(msg)
    }

    /**
    * Verifies (NIZK) and adds a partial signature to the internal store.
    * Returns Err() if NIZK verification failed,
    * Ok(true) if >= t valid partial signatures are in store,
    * Ok(false) if not enough signatures are stored yet.
    */
    pub fn check_add_psig(&mut self, psig: PartialSignature, MsgPoint: GE1) -> Result<bool> {
        //check if index is valid & if index was already added
        if psig.index > self.n as usize {
            return Err(anyhow!("Signature index out of range: i={}, n={}", psig.index, self.n));
        }
        if self.received_psigs[psig.index] {
            return Err(anyhow!("already added a signature from this peer!"));
        }

        //verify the signature's ec_ddh NIZK
        let delta = ECDDHStatement {
            g1: MsgPoint.clone(),
            h1: psig.sigma_i.clone(),
            g2: GE2::generator(),
            h2: self.vk_vec[psig.index],
        };
        if !psig.ddh_proof.verify(&delta) {
            return Err(anyhow!("Partial signature ec_ddh NIZK verification failed"));
        }

        //add psig to internal store
        self.received_psigs[psig.index] = true;
        self.verified_psigs.push(psig);

        //return, whether we have enough psigs to start aggregation
        Ok(self.verified_psigs.len() >= (self.t + 1) as usize)
    }

    /**
    * Verifies (NIZK) of a partial signature.
    * Returns Err() if NIZK verification failed,
    * Ok() otherwise
    */
    pub fn check_psig(&self, psig: PartialSignature, MsgPoint: GE1, vk_i: GE2) -> bool {
        //verify the signature's ec_ddh NIZK
        let delta = ECDDHStatement {
            g1: MsgPoint.clone(),
            h1: psig.sigma_i.clone(),
            g2: GE2::generator(),
            h2: vk_i,
        };

        return psig.ddh_proof.verify(&delta);
    }

    /**
    * Add a verified psig to the internal store.
    * Returns Err() if failed,
    * Ok(true) if >= t valid partial signatures are in store,
    * Ok(false) if not enough signatures are stored yet.
    */
    pub fn add_psig(&mut self, psig: PartialSignature) -> Result<bool> {
        //check if index is valid & if index was already added
        if psig.index > self.n as usize {
            return Err(anyhow!("Signature index out of range: i={}, n={}", psig.index, self.n));
        }
        if self.received_psigs[psig.index] {
            return Err(anyhow!("already added a signature from this peer!"));
        }

        //add psig to internal store
        self.received_psigs[psig.index] = true;
        self.verified_psigs.push(psig);

        //return, whether we have enough psigs to start aggregation
        Ok(self.verified_psigs.len() >= (self.t + 1) as usize)
    }

    pub fn combine(&self) -> Result<BLSSignature> {
        //check if we have enough psigs in store
        if self.verified_psigs.len() < (self.t + 1) as usize {
            return Err(anyhow!("Not enough (>= t+1) partial signatures in store!"))
        }

        //build signing-node-index array
        let mut s = vec![];
        for psig in self.verified_psigs.iter() {
            s.push(psig.index);
        }

        //lagrange interpolate psigs
        let (head, tail) = self.verified_psigs.split_at(1);
        let sigma = tail[0..(self.t as usize)].iter().fold(
            &head[0].sigma_i
                * &VerifiableSS::<GE1>::map_share_to_new_params(
                &ShamirSecretSharing { threshold: self.t, share_count: self.n },
                head[0].index,
                &s[0..(self.t as usize + 1)],
            ),
            |acc, x| {
                acc + &x.sigma_i
                    * &VerifiableSS::<GE1>::map_share_to_new_params(
                    &ShamirSecretSharing { threshold: self.t, share_count: self.n },
                    x.index,
                    &s[0..(self.t as usize + 1)],
                )
            },
        );

        Ok(BLSSignature { sigma })
    }
}

#[cfg(test)]
mod tests {
    use std::process::exit;
    use anyhow::Context;
    use super::*;

    async fn read_bls_keys(path: String) -> Result<threshold_bls::state_machine::keygen::LocalKey> {
        let secret = tokio::fs::read(path).await.context("read file with local secret key")?;
        let secret = serde_json::from_slice(&secret).context("deserialize local secret key")?;

        Ok(secret)
    }

    fn verify(
        public_key: String,
        signature: String,
        msg: String,
    ) -> Result<bool> {

        //decode keys from hex
        let public_key = hex::decode(public_key).context("public key is not valid hex encoded string")?;
        let signature = hex::decode(signature).context("signature key is not valid hex encoded string")?;
        let msg = hex::decode(msg).context("message not valid hex encoded string")?;

        //deserialize signature and oubkey to points on curves
        let signature = curv::elliptic::curves::bls12_381::g1::GE::from_bytes(&signature)
            .map_err(|e| anyhow!("signature is not valid g1 point: {:?}", e))?;
        let public_key = curv::elliptic::curves::bls12_381::g2::GE::from_bytes(&public_key)
            .map_err(|e| anyhow!("public key is not valid g2 point: {:?}", e))?;

        //verify signature with pubkey
        let valid = BLSSignature { sigma: signature }.verify(&msg, &public_key);

        Ok(valid)
    }

    #[test]
    fn test_sign_ext() {
        //keygen must have been successful for this thest to pass

        //some bits to sign
        let test_digest: Vec<u8> = vec![69, 32];


        // Build async runtime
        let mut runtime = tokio::runtime::Builder::new_multi_thread();

        runtime.enable_all();

        /*
        if let Some(t) = app.threads {
            runtime.worker_threads(t);
        }
        */

        let runtime = match runtime.build() {
            Ok(r) => r,
            Err(e) => {
                println!("Failed to build async runtime: {}", e);
                exit(1)
            }
        };

        let result = runtime.block_on(async {

            //setup:

            let lk0 = read_bls_keys("test_k_dir/bls_keys/0".parse().unwrap()).await.unwrap();
            let lk1 = read_bls_keys("test_k_dir/bls_keys/1".parse().unwrap()).await.unwrap();
            let lk2 = read_bls_keys("test_k_dir/bls_keys/2".parse().unwrap()).await.unwrap();


            //generate partial signatures

            let (psig0, msg_pt) = psign_ext::psign(lk0.clone(), &test_digest.clone());
            let (psig1, msg_pt1) = psign_ext::psign(lk1.clone(), &test_digest.clone());
            let (psig2, msg_pt2) = psign_ext::psign(lk2, &test_digest.clone());

            //create aggregator object and input partial signatures
            let mut aggregator = psign_ext::new(lk0.t(), lk0.n(), lk0.vk_vec);

            assert_eq!(aggregator.check_add_psig(psig0, msg_pt.clone()).unwrap(), false);
            assert_eq!(aggregator.check_add_psig(psig1, msg_pt.clone()).unwrap(), false);
            assert_eq!(aggregator.check_add_psig(psig2, msg_pt.clone()).unwrap(), true);

            //combine signatures
            let sig = aggregator.combine().unwrap();

            println!("Combined signature: {:?}", sig);


            //verify signature
            let public_key = curv::elliptic::curves::traits::ECPoint::pk_to_key_slice(&lk1.public_key());
            let signature = curv::elliptic::curves::traits::ECPoint::pk_to_key_slice(&sig.sigma);
            let ver = verify(hex::encode(public_key.clone()), hex::encode(signature.clone()), hex::encode(test_digest.clone())).unwrap();

            assert_eq!(ver, true);
            println!("Signature valid: {}", ver);
        });
    }

}
