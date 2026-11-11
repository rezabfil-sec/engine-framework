#![allow(dead_code)]

use aes_gcm::aead::{Aead, NewAead};
use aes_gcm::{Aes256Gcm, Nonce};
use anyhow::anyhow;
use anyhow::Context;
use curv::arithmetic::traits::Converter;
use curv::elliptic::curves::{Point, Scalar, Secp256k1};
use curv::BigInt;

use k256::ecdsa::Signature;

use k256::ecdsa::signature::{DigestSigner, DigestVerifier};
use k256::ecdsa::{SigningKey, VerifyingKey};
use k256::elliptic_curve::sec1::ToEncodedPoint;
use k256::EncodedPoint;
use rand::{rngs::OsRng, RngCore};
use serde::{self, Deserialize, Serialize};
use sha2::{Digest, Sha256};

#[derive(Debug, Clone)]
pub struct PrivKey {
    key: SigningKey,
}

impl PrivKey {
    pub const BYTE_LENGTH: usize = 32;
    pub fn new(bls_priv_key: SigningKey) -> Self {
        PrivKey { key: bls_priv_key }
    }

    pub fn from_bytes(key_bytes: Vec<u8>) -> anyhow::Result<PrivKey> {
        SigningKey::from_bytes(&key_bytes)
            .map(Self::new)
            .context("Deserializing private key.")
    }

    pub fn to_bytes(&self) -> Vec<u8> {
        self.key.to_bytes().to_vec()
    }

    pub fn sign(&self, digest: &HashDigest) -> Sig {
        let sig: Signature = self.key.sign_digest(Sha256::new().chain(digest.digest));
        Sig { sig }
    }

    pub fn generate() -> Self {
        PrivKey {
            key: SigningKey::random(&mut OsRng),
        }
    }
}

#[derive(Clone, Debug)]
pub struct PubKey {
    key: VerifyingKey,
}

impl PubKey {
    pub const BYTE_LENGTH: usize = 65;
    pub fn new(bls_priv_key: VerifyingKey) -> PubKey {
        PubKey { key: bls_priv_key }
    }

    pub fn from_bytes(key_bytes: Vec<u8>) -> anyhow::Result<PubKey> {
        EncodedPoint::from_bytes(key_bytes)
            .map_err(|err| anyhow!(err.to_string()))
            .and_then(|key| {
                VerifyingKey::from_encoded_point(&key).map_err(|err| anyhow!(err.to_string()))
            })
            .map(Self::new)
            .context("Deserializing public key")
    }

    pub fn to_bytes(&self) -> Vec<u8> {
        self.key.to_encoded_point(false).to_bytes().to_vec()
    }

    pub fn from_priv_key(priv_key: &PrivKey) -> Self {
        PubKey {
            key: VerifyingKey::from(&priv_key.key),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Sig {
    sig: Signature,
}

impl Sig {
    pub const BYTE_LENGTH: usize = 72;
    pub fn new(signature: Signature) -> Sig {
        Sig { sig: signature }
    }

    pub fn from_bytes(sig_bytes: Vec<u8>) -> anyhow::Result<Sig> {
        bincode::deserialize(&sig_bytes)
            .map(Self::new)
            .context("Deserialize sig")
    }

    pub fn to_bytes(&self) -> Vec<u8> {
        bincode::serialize(&self.sig).unwrap()
    }

    pub fn verify(&self, pub_key: &PubKey, digest: &HashDigest) -> bool {
        pub_key
            .key
            .verify_digest(Sha256::new().chain(digest.digest), &self.sig)
            .is_ok()
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct HashDigest {
    digest: [u8; 32],
}

impl HashDigest {
    pub fn to_bytes(&self) -> Vec<u8> {
        self.digest.to_vec()
    }

    pub fn from_bytes(bytes: &[u8]) -> HashDigest {
        let mut digest_bytes: [u8; 32] = Default::default();
        digest_bytes.copy_from_slice(bytes);
        HashDigest {
            digest: digest_bytes,
        }
    }
}

pub fn hash(msg: &Vec<u8>) -> HashDigest {
    let mut hasher = Sha256::new();
    hasher.update(msg);
    let digest = hasher.finalize();
    let mut digest_bytes: [u8; 32] = Default::default();
    digest_bytes.copy_from_slice(&digest);

    HashDigest {
        digest: digest_bytes,
    }
}

pub fn hash_many(msgs: &Vec<Vec<u8>>) -> HashDigest {
    let mut hasher = Sha256::new();
    for msg in msgs {
        hasher.update(msg);
    }
    let digest = hasher.finalize();

    let mut digest_bytes: [u8; 32] = Default::default();
    digest_bytes.copy_from_slice(&digest);
    HashDigest {
        digest: digest_bytes,
    }
}

#[derive(Clone, PartialEq, Debug, serde::Serialize, serde::Deserialize)]
pub struct SymmEncMsg {
    pub ciphertext: Vec<u8>,
    pub tag: Vec<u8>,
}

#[derive(Clone, Debug)]
pub struct SecretEncKey {
    key: Vec<u8>,
}

impl SecretEncKey {
    const KEY_BYTES_LEN: usize = 32;

    pub fn from_diffie_hellman(public: &Point<Secp256k1>, secret: &Scalar<Secp256k1>) -> Self {
        let mut key_bytes = BigInt::to_bytes(&(public * secret).x_coord().unwrap());
        let mut key: Vec<u8> = vec![0; Self::KEY_BYTES_LEN - key_bytes.len()];
        key.append(&mut key_bytes);
        SecretEncKey { key }
    }

    pub fn random() -> Self {
        SecretEncKey {
            key: (0..Self::KEY_BYTES_LEN).map(|_| rand::random()).collect(),
        }
    }
}

impl SecretEncKey {
    pub fn encrypt(&self, msg: &Vec<u8>) -> SymmEncMsg {
        let aes_key = aes_gcm::Key::from_slice(&self.key);
        let cipher = Aes256Gcm::new(aes_key);

        let mut nonce = [0u8; 12];
        OsRng.fill_bytes(&mut nonce);
        let nonce = Nonce::from_slice(&nonce);

        let ciphertext = cipher
            .encrypt(nonce, &msg[..])
            .expect("encryption failure!");

        SymmEncMsg {
            ciphertext,
            tag: nonce.to_vec(),
        }
    }
    pub fn decrypt(&self, enc_msg: SymmEncMsg) -> Vec<u8> {
        let aes_key = aes_gcm::Key::from_slice(&self.key);
        let nonce = Nonce::from_slice(&enc_msg.tag);
        let gcm = Aes256Gcm::new(aes_key);

        let out = gcm.decrypt(nonce, enc_msg.ciphertext.as_slice());
        out.unwrap()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn priv_ser() {
        let key = PrivKey::generate();
        let key_bytes = key.to_bytes();
        assert_eq!(PrivKey::BYTE_LENGTH, key_bytes.len());
        let key = PrivKey::from_bytes(key_bytes.clone()).unwrap();
        let key_bytes2 = key.to_bytes();
        assert_eq!(key_bytes, key_bytes2);
    }

    #[test]
    fn pub_ser() {
        let priv_key = PrivKey::generate();
        let key = PubKey::from_priv_key(&priv_key);
        let key_bytes = key.to_bytes();
        assert_eq!(PubKey::BYTE_LENGTH, key_bytes.len());
        let key = PubKey::from_bytes(key_bytes.clone()).unwrap();
        let key_bytes2 = key.to_bytes();
        assert_eq!(key_bytes, key_bytes2);
    }

    #[test]
    fn sig_ser() {
        let key = PrivKey::generate();
        let msg: Vec<u8> = (0..64).map(|_| rand::random()).collect();
        let sig = key.sign(&hash(&msg));
        let sig_bytes = sig.to_bytes();
        assert_eq!(Sig::BYTE_LENGTH, sig_bytes.len());
        let sig_des = Sig::from_bytes(sig_bytes.clone()).unwrap();
        let sig_des_bytes = sig_des.to_bytes();
        assert_eq!(sig_des_bytes, sig_bytes);
    }

    #[test]
    fn symmetric_encryption() {
        let msg: Vec<u8> = (0..1024).map(|_| rand::random()).collect();
        let key = SecretEncKey::random();

        let enc = key.encrypt(&msg);
        let dec = key.decrypt(enc);

        assert_eq!(msg, dec);
    }
}
