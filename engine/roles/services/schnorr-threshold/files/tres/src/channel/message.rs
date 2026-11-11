use std::any::Any;

use curve25519_dalek::ristretto::RistrettoPoint;
use curve25519_dalek::scalar::Scalar;

use bincode::config::{BigEndian, Bounded, FixintEncoding, WithOtherEndian, WithOtherIntEncoding, WithOtherLimit};
use bincode::{DefaultOptions, Options};
use serde::{Deserialize, Serialize};
use zeroize::Zeroize;

use nom::{branch::alt, bytes::complete::tag, bytes::streaming::take, number, IResult};

use crate::node::common::*;

mod traits;
pub use traits::*;

pub(crate) const MAX_P2PMSG_SIZE: u64 = 2u64.pow(24) - 1; // = 16777215; 3 bytes for the length field

/// As in transport::noise::packet, we have to parse stuff from the network
/// However, this file uses a different approach to parse/synthesize packets: serde + bincode
fn bincfg() -> WithOtherIntEncoding<WithOtherEndian<WithOtherLimit<DefaultOptions, Bounded>, BigEndian>, FixintEncoding> {
  bincode::DefaultOptions::new().with_limit(MAX_P2PMSG_SIZE).with_big_endian().with_fixint_encoding()
}

// ####### BEGIN Adapt structs copied from frost-dalek
// Instead of adding serde support there, derive needed traits here. Can be upstreamed later, though.
// (Upstream is not stable yet)

// frost_dalek::nizk::NizkOfSecretKey;
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct NizkOfSecretKey {
  /// The scalar portion of the Schnorr signature encoding the context.
  s: Scalar,
  /// The scalar portion of the Schnorr signature which is the actual signature.
  r: Scalar,
}

// frost_dalek::keygen::SecretShare;
#[derive(Serialize, Deserialize, Clone, Debug, Zeroize, PartialEq)]
#[zeroize(drop)]
pub struct SecretShare {
  /// The participant index that this secret share was calculated for.
  pub index: u32,
  /// The final evaluation of the polynomial for the participant-respective
  /// indeterminant.
  pub polynomial_evaluation: Scalar,
}

// frost_dalek::signature::Signer
#[derive(Serialize, Deserialize, Clone, Copy, Debug, PartialEq)]
pub struct Signer {
  /// The participant index of this signer.
  pub participant_index: u32,
  /// One of the commitments that were published by each signing participant
  /// in the pre-computation phase.
  pub published_commitment_share: (RistrettoPoint, RistrettoPoint),
}

// ####### Adapted structs END

// Message IDs (0 is reserved)
const P2PMESSAGE_BROADCAST: u8 = 1;
const P2PMESSAGE_DKG_INIT: u8 = 2;
const P2PMESSAGE_DKG1PARTICIPANT: u8 = 3;
const P2PMESSAGE_DKG2SECRETSHARE: u8 = 4;

const P2PMESSAGE_PREPROCESS_INIT: u8 = 10;
const P2PMESSAGE_NONCECOMMITMENTLIST: u8 = 11;

const P2PMESSAGE_SIGNINIT: u8 = 20;
const P2PMESSAGE_SIGN1PARTIALTHRESHOLDSIG: u8 = 21;

/// first DKG msg
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct Dkg1Participant {
  // not sent because already known by receiver:  index: u32,
  /// C
  pub(crate) commitments: Vec<RistrettoPoint>,
  /// signature
  pub(crate) proof_of_secret_key: NizkOfSecretKey,
}
/// second DKG msg
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct Dkg2SecretShare {
  /// MINOR: really transmit index or leave it out?
  pub(crate) secret_share: SecretShare,
}

/// Used to emulate a broadcast (over unicast channels)
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Broadcast {
  /// The ID of the peer this broadcast was received from.
  /// Otherwise (if this msg originated from the sending node), the id is 0
  pub(crate) src_id: ID,
  pub(crate) payload: P2PDataMsg,
}
/// start a new DKG phase
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct DkgInit {
  /// the threshold number of nodes
  pub(crate) t: ID,
}

/// initiates a preprocessing phase
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct PreprocessInit {
  /// the number of nonces/commitments to generate ahead of signing
  /// Short alias is for request via HTTP querystrings from the client (less parsing + typing for manual interaction)
  #[serde(alias = "n")]
  #[serde(rename(serialize = "n"))]
  pub(crate) number_of_commitments: usize,
}
/// Message containing a list of public commitments to the nonces
/// Corresponds to `frost_dalek::precomputation::PublicCommitmentShareList`
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct NonceCommitmentList {
  // left out `participant_index` because it's implicitely known
  pub commitments: Vec<(RistrettoPoint, RistrettoPoint)>,
}

/// Initiates the computation of a group signature: requests a partial signature from the receiver
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SignInit {
  /// message to be signed by the group
  pub msg: Vec<u8>,
  /// list of signing participants (their respective nonce commitments)
  pub b: Vec<Signer>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct Sign1PartialThresholdSig {
  // left out `participant_index` because it's implicitely known
  /// partial threshold signature
  pub z: Scalar,
}

/// A P2P message
/// Format:
/// type: 1 byte
/// length (of following bytes): 2 byte
/// payloadbytes: the serialized P2PMessageContent
/// This format is not minimal (e.g., see bincode's VarintEncoding) but compatible to other languages/parsing libraries
/// (not that this is really needed, but it was interesting to figure out)
///
/// We only distinguish between control and data messages in the code but not on the wire (same format there)
#[derive(Debug, Clone)]
pub enum P2PMessage {
  Control(P2PControlMsg),
  Data(P2PDataMsg),
}

/// Messages having a payload for FROST
/// PartialEq is required for simulated broadcast: find out whether 2 messages are indeed identical
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub enum P2PDataMsg {
  Dkg1Participant(Dkg1Participant),
  Dkg2SecretShare(Dkg2SecretShare),
  NonceCommitmentList(NonceCommitmentList),
  SignInit(SignInit),
  Sign1PartialThresholdSig(Sign1PartialThresholdSig),
}
/// Messages used to manage the interactions between peers
#[derive(Debug, Clone)]
pub enum P2PControlMsg {
  DkgInit(DkgInit),
  Broadcast(Broadcast),
  PreprocessInit(PreprocessInit),
}

/// length field: 3 bytes (after the type field)
fn parse_length(input: &[u8]) -> IResult<&[u8], u32> {
  number::streaming::u24(nom::number::Endianness::Big)(input)
}

// This is ugly. MINOR: remove the explicit length field. It does more harm than good. Bincode still adds a length field
// for variable-length payloads.  Caveat: then the receiver/sender both must use bincode/serde
fn dkg_1_participant_parser(i: &[u8]) -> IResult<&[u8], P2PMessage> {
  let (i, _) = tag([P2PMESSAGE_DKG1PARTICIPANT])(i)?; // consumes message if it starts with this Message ID
  let (i, length) = parse_length(i)?;
  let (i, structbytes) = take(length)(i)?;

  let msg = bincfg().deserialize(structbytes);
  if msg.is_err() {
    return Err(nom::Err::Failure(nom::error::Error::new(structbytes, nom::error::ErrorKind::Complete)));
  }

  Ok((i, P2PMessage::Data(P2PDataMsg::Dkg1Participant(msg.unwrap()))))
}
fn dkg_2_secretshare_parser(i: &[u8]) -> IResult<&[u8], P2PMessage> {
  let (i, _) = tag([P2PMESSAGE_DKG2SECRETSHARE])(i)?; // consumes message if it starts with this Message ID
  let (i, length) = parse_length(i)?;
  let (i, structbytes) = take(length)(i)?;

  let msg = bincfg().deserialize(structbytes);
  if msg.is_err() {
    return Err(nom::Err::Failure(nom::error::Error::new(structbytes, nom::error::ErrorKind::Complete)));
  }

  Ok((i, P2PMessage::Data(P2PDataMsg::Dkg2SecretShare(msg.unwrap()))))
}
/// MINOR: same length field issue as in dkg_1_participant_parser
fn nonce_commitment_list_parser(i: &[u8]) -> IResult<&[u8], P2PMessage> {
  let (i, _) = tag([P2PMESSAGE_NONCECOMMITMENTLIST])(i)?; // consumes message if it starts with this Message ID
  let (i, length) = parse_length(i)?;
  let (i, structbytes) = take(length)(i)?;

  let msg = bincfg().deserialize(structbytes);
  if msg.is_err() {
    return Err(nom::Err::Failure(nom::error::Error::new(structbytes, nom::error::ErrorKind::Complete)));
  }

  let msg: NonceCommitmentList = msg.unwrap();
  Ok((i, Into::<P2PMessage>::into(msg)))
}
fn sign_init_parser(i: &[u8]) -> IResult<&[u8], P2PMessage> {
  let (i, _) = tag([P2PMESSAGE_SIGNINIT])(i)?; // consumes message if it starts with this Message ID
  let (i, length) = parse_length(i)?;
  let (i, structbytes) = take(length)(i)?;

  let msg = bincfg().deserialize(structbytes);
  if msg.is_err() {
    return Err(nom::Err::Failure(nom::error::Error::new(structbytes, nom::error::ErrorKind::Complete)));
  }

  let msg: SignInit = msg.unwrap();
  Ok((i, Into::<P2PMessage>::into(msg)))
}
fn sign_1_partial_threshold_sig_parser(i: &[u8]) -> IResult<&[u8], P2PMessage> {
  let (i, _) = tag([P2PMESSAGE_SIGN1PARTIALTHRESHOLDSIG])(i)?; // consumes message if it starts with this Message ID
  let (i, length) = parse_length(i)?;
  let (i, structbytes) = take(length)(i)?;

  let msg = bincfg().deserialize(structbytes);
  if msg.is_err() {
    return Err(nom::Err::Failure(nom::error::Error::new(structbytes, nom::error::ErrorKind::Complete)));
  }

  let msg: Sign1PartialThresholdSig = msg.unwrap();
  Ok((i, Into::<P2PMessage>::into(msg)))
}

fn dkg_init_parser(i: &[u8]) -> IResult<&[u8], P2PMessage> {
  let (i, _) = tag([P2PMESSAGE_DKG_INIT])(i)?; // consumes message if it starts with this Message ID
  let (i, length) = parse_length(i)?;
  let (i, structbytes) = take(length)(i)?;

  let msg = bincfg().deserialize(structbytes);
  if msg.is_err() {
    return Err(nom::Err::Failure(nom::error::Error::new(structbytes, nom::error::ErrorKind::Complete)));
  }

  Ok((i, P2PMessage::Control(P2PControlMsg::DkgInit(msg.unwrap()))))
}

fn broadcast_parser(i: &[u8]) -> IResult<&[u8], P2PMessage> {
  let (i, _) = tag([P2PMESSAGE_BROADCAST])(i)?; // consumes message if it starts with this Message ID
  let (i, length) = parse_length(i)?;
  let (i, structbytes) = take(length)(i)?;

  let msg = bincfg().deserialize(structbytes);
  if msg.is_err() {
    return Err(nom::Err::Failure(nom::error::Error::new(structbytes, nom::error::ErrorKind::Complete)));
  }

  Ok((i, P2PMessage::Control(P2PControlMsg::Broadcast(msg.unwrap()))))
}

fn preprocess_init_parser(i: &[u8]) -> IResult<&[u8], P2PMessage> {
  let (i, _) = tag([P2PMESSAGE_PREPROCESS_INIT])(i)?; // consumes message if it starts with this Message ID
  let (i, length) = parse_length(i)?;
  let (i, structbytes) = take(length)(i)?;

  let msg = bincfg().deserialize(structbytes);
  if msg.is_err() {
    return Err(nom::Err::Failure(nom::error::Error::new(structbytes, nom::error::ErrorKind::Complete)));
  }

  let msg: PreprocessInit = msg.unwrap();
  Ok((i, Into::<P2PMessage>::into(msg)))
}

impl P2PMessage {
  pub fn parse(input: &[u8]) -> IResult<&[u8], Self> {
    // println!("parse {}", hex::encode(&input));
    alt((
      sign_1_partial_threshold_sig_parser,
      sign_init_parser,
      nonce_commitment_list_parser,
      preprocess_init_parser,
      dkg_init_parser,
      broadcast_parser,
      dkg_1_participant_parser,
      dkg_2_secretshare_parser,
    ))(input)
  }

  pub fn to_bytes(&self) -> bincode::Result<Vec<u8>> {
    let binconfig = bincfg();

    let (msgtype, mut msgbytes) = match self {
      P2PMessage::Data(datamsg) => match datamsg {
        P2PDataMsg::Dkg1Participant(msgstruct) => (P2PMESSAGE_DKG1PARTICIPANT, binconfig.serialize(msgstruct)?),
        P2PDataMsg::Dkg2SecretShare(msgstruct) => (P2PMESSAGE_DKG2SECRETSHARE, binconfig.serialize(msgstruct)?),
        P2PDataMsg::NonceCommitmentList(msgstruct) => (P2PMESSAGE_NONCECOMMITMENTLIST, binconfig.serialize(msgstruct)?),
        P2PDataMsg::SignInit(msgstruct) => (P2PMESSAGE_SIGNINIT, binconfig.serialize(msgstruct)?),
        P2PDataMsg::Sign1PartialThresholdSig(msgstruct) => (P2PMESSAGE_SIGN1PARTIALTHRESHOLDSIG, binconfig.serialize(msgstruct)?),
      },
      P2PMessage::Control(controlmsg) => match controlmsg {
        P2PControlMsg::DkgInit(msgstruct) => (P2PMESSAGE_DKG_INIT, binconfig.serialize(msgstruct)?),
        P2PControlMsg::Broadcast(msgstruct) => (P2PMESSAGE_BROADCAST, binconfig.serialize(msgstruct)?),
        P2PControlMsg::PreprocessInit(msgstruct) => (P2PMESSAGE_PREPROCESS_INIT, binconfig.serialize(msgstruct)?),
      },
    };
    let mut packet = binconfig.serialize(&msgtype)?;
    assert!(packet.len() == 1); // 1 byte for the type
    if msgbytes.len() > (MAX_P2PMSG_SIZE as usize) {
      return Err(serde::ser::Error::custom(format!("Msg too long: {} bytes", msgbytes.len())));
    }
    // not really necessary to have a length field here, but convenient for the parser
    let mut length_field = binconfig.serialize(&(msgbytes.len() as u32))?;
    length_field.remove(0); // there has to be a better way to obtain only 3 bytes/a serialized u24 ?
    assert!(length_field.len() == 3); // 3 bytes for the length

    packet.append(&mut length_field);
    //println!("packet {}", hex::encode(&packet));
    packet.append(&mut msgbytes);
    //println!("packet {}", hex::encode(&packet));
    Ok(packet)
  }
}

#[cfg(test)]
mod tests {
  use super::*;

  #[test]
  fn parsing() {
    let mut msgbytes: Vec<u8> = vec![P2PMESSAGE_DKG_INIT]; // msg type
    msgbytes.append(&mut vec![0x00, 0x00, 0x04]); // length - bincode serializes ID=u32
    msgbytes.append(&mut vec![0x00, 0x00, 0x01, 0x02]); // t :usize = 258

    let res = P2PMessage::parse(&msgbytes);
    let (rest, parsed_message) = res.unwrap();
    assert_eq!(rest.len(), 0); // we don't allow trailing bytes, but assert this anyways
    match parsed_message {
      P2PMessage::Control(P2PControlMsg::DkgInit(msgstruct)) => {
        assert_eq!(msgstruct.t, 258);
      }
      _ => panic!("wrong msg"),
    }
  }
  #[test]
  fn synthesizing() {
    let msg = P2PMessage::Control(P2PControlMsg::DkgInit(DkgInit { t: 259 }));
    let res = msg.to_bytes();
    assert!(res.is_ok());
    let msgbytes = res.unwrap();
    assert_eq!(msgbytes, vec![P2PMESSAGE_DKG_INIT, 0x00, 0x00, 0x04, 0x00, 0x00, 0x01, 0x03]);
  }
}
