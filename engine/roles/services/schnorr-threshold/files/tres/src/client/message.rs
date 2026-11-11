/// Messages from and to the external client
use std::convert::TryFrom;

use serde::{Deserialize, Serialize};

use curve25519_dalek::ristretto::RistrettoPoint;
use curve25519_dalek::scalar::Scalar;

use crate::node::common::*;

// Contains the public group key
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct GroupKeyMsg {
  group_key: [u8; 32],
}
// A request from the client to sign a certain message
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct SigningRequestMsg {
  /// The message to be signed.
  /// TODO: should be a Vec<u8>. Currently a string because vectors serializes to vec[0]=item1&vec[1]=item2&...
  pub(crate) msg: String,
}
// Reply containing the number of nodes "n" in the system
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct NumParticipantsMsg {
  /// number of participants
  pub n: ID,
}

// ####### BEGIN Adapt structs copied from frost-dalek
// frost_dalek::signature::ThresholdSignature
// also worth reading: https://stackoverflow.com/questions/48782047/how-do-i-use-serde-to-deserialize-arrays-greater-than-32-elements-such-as-u8
/// A complete, aggregated threshold signature.
#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct ThresholdSignature {
  /// R
  pub(crate) r: RistrettoPoint,
  pub(crate) z: Scalar,
}
// ####### END Adapted structs

impl From<&frost_dalek::keygen::GroupKey> for GroupKeyMsg {
  fn from(gk: &frost_dalek::keygen::GroupKey) -> Self {
    Self { group_key: gk.to_bytes() }
  }
}

impl TryFrom<GroupKeyMsg> for frost_dalek::keygen::GroupKey {
  type Error = ();

  fn try_from(m: GroupKeyMsg) -> Result<Self, Self::Error> {
    frost_dalek::keygen::GroupKey::from_bytes(m.group_key)
  }
}

impl From<ThresholdSignature> for frost_dalek::signature::ThresholdSignature {
  fn from(s: ThresholdSignature) -> Self {
    Self { R: s.r, z: s.z }
  }
}
impl From<frost_dalek::signature::ThresholdSignature> for ThresholdSignature {
  fn from(s: frost_dalek::signature::ThresholdSignature) -> Self {
    Self { r: s.R, z: s.z }
  }
}
impl From<&frost_dalek::signature::ThresholdSignature> for ThresholdSignature {
  fn from(s: &frost_dalek::signature::ThresholdSignature) -> Self {
    Self { r: s.R, z: s.z }
  }
}
