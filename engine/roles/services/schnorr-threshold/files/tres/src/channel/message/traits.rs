use crate::channel::message::*;
// This file just contains some trait implementations of `From`
// convert between our and frost_dalek's types
impl From<frost_dalek::nizk::NizkOfSecretKey> for NizkOfSecretKey {
  fn from(p: frost_dalek::nizk::NizkOfSecretKey) -> Self {
    Self { s: p.s, r: p.r }
  }
}
impl From<NizkOfSecretKey> for frost_dalek::nizk::NizkOfSecretKey {
  fn from(p: NizkOfSecretKey) -> Self {
    Self { s: p.s, r: p.r }
  }
}

impl From<frost_dalek::keygen::SecretShare> for SecretShare {
  fn from(s: frost_dalek::keygen::SecretShare) -> Self {
    Self { index: s.index, polynomial_evaluation: s.polynomial_evaluation }
  }
}
impl From<&frost_dalek::keygen::SecretShare> for SecretShare {
  fn from(s: &frost_dalek::keygen::SecretShare) -> Self {
    Self { index: s.index, polynomial_evaluation: s.polynomial_evaluation }
  }
}
impl From<&SecretShare> for frost_dalek::keygen::SecretShare {
  fn from(s: &SecretShare) -> Self {
    Self { index: s.index, polynomial_evaluation: s.polynomial_evaluation }
  }
}

impl From<Signer> for frost_dalek::signature::Signer {
  fn from(s: Signer) -> Self {
    Self { participant_index: s.participant_index, published_commitment_share: s.published_commitment_share }
  }
}
impl From<&Signer> for frost_dalek::signature::Signer {
  fn from(s: &Signer) -> Self {
    Self { participant_index: s.participant_index, published_commitment_share: s.published_commitment_share }
  }
}
impl From<&frost_dalek::signature::Signer> for Signer {
  fn from(s: &frost_dalek::signature::Signer) -> Self {
    Self { participant_index: s.participant_index, published_commitment_share: s.published_commitment_share }
  }
}

// frost_dalek's types <-> our messages
impl From<frost_dalek::Participant> for Dkg1Participant {
  fn from(p: frost_dalek::Participant) -> Self {
    Dkg1Participant { commitments: p.commitments, proof_of_secret_key: p.proof_of_secret_key.into() }
  }
}
impl Dkg1Participant {
  pub fn into_with(&self, index: ID) -> frost_dalek::Participant {
    frost_dalek::Participant { index, commitments: self.commitments.clone(), proof_of_secret_key: self.proof_of_secret_key.clone().into() }
  }
}

impl From<frost_dalek::precomputation::PublicCommitmentShareList> for NonceCommitmentList {
  fn from(l: frost_dalek::precomputation::PublicCommitmentShareList) -> Self {
    Self { commitments: l.commitments }
  }
}
impl NonceCommitmentList {
  /// index: participant index of the node which has computed the commitments (i.e., the sender ID)
  pub fn into_with(&self, index: ID) -> frost_dalek::precomputation::PublicCommitmentShareList {
    frost_dalek::precomputation::PublicCommitmentShareList { participant_index: index, commitments: self.commitments.clone() }
  }
}

impl From<frost_dalek::signature::PartialThresholdSignature> for Sign1PartialThresholdSig {
  fn from(partial_sig: frost_dalek::signature::PartialThresholdSignature) -> Self {
    Self { z: partial_sig.z }
  }
}
impl From<&frost_dalek::signature::PartialThresholdSignature> for Sign1PartialThresholdSig {
  fn from(partial_sig: &frost_dalek::signature::PartialThresholdSignature) -> Self {
    Self { z: partial_sig.z }
  }
}
impl Sign1PartialThresholdSig {
  pub fn into_with(&self, index: &ID) -> frost_dalek::signature::PartialThresholdSignature {
    frost_dalek::signature::PartialThresholdSignature { index: *index, z: self.z }
  }
}

// encapsulate messages in the proper types
impl From<P2PControlMsg> for P2PMessage {
  fn from(msg: P2PControlMsg) -> Self {
    P2PMessage::Control(msg)
  }
}
impl From<P2PDataMsg> for P2PMessage {
  fn from(msg: P2PDataMsg) -> Self {
    P2PMessage::Data(msg)
  }
}
//            ->  ###
impl From<Dkg1Participant> for P2PDataMsg {
  fn from(msg: Dkg1Participant) -> Self {
    P2PDataMsg::Dkg1Participant(msg)
  }
}
impl From<Dkg2SecretShare> for P2PDataMsg {
  fn from(msg: Dkg2SecretShare) -> Self {
    P2PDataMsg::Dkg2SecretShare(msg)
  }
}
impl From<NonceCommitmentList> for P2PDataMsg {
  fn from(msg: NonceCommitmentList) -> Self {
    P2PDataMsg::NonceCommitmentList(msg)
  }
}
impl From<SignInit> for P2PDataMsg {
  fn from(msg: SignInit) -> Self {
    P2PDataMsg::SignInit(msg)
  }
}
impl From<Sign1PartialThresholdSig> for P2PDataMsg {
  fn from(msg: Sign1PartialThresholdSig) -> Self {
    P2PDataMsg::Sign1PartialThresholdSig(msg)
  }
}

//            ->->  ###
impl From<Dkg1Participant> for P2PMessage {
  fn from(msg: Dkg1Participant) -> Self {
    (Into::<P2PDataMsg>::into(msg)).into()
  }
}
impl From<Dkg2SecretShare> for P2PMessage {
  fn from(msg: Dkg2SecretShare) -> Self {
    (Into::<P2PDataMsg>::into(msg)).into()
  }
}
impl From<NonceCommitmentList> for P2PMessage {
  fn from(msg: NonceCommitmentList) -> Self {
    (Into::<P2PDataMsg>::into(msg)).into()
  }
}
impl From<SignInit> for P2PMessage {
  fn from(msg: SignInit) -> Self {
    (Into::<P2PDataMsg>::into(msg)).into()
  }
}
impl From<Sign1PartialThresholdSig> for P2PMessage {
  fn from(msg: Sign1PartialThresholdSig) -> Self {
    (Into::<P2PDataMsg>::into(msg)).into()
  }
}

//            ->  ###
impl From<Broadcast> for P2PControlMsg {
  fn from(msg: Broadcast) -> Self {
    P2PControlMsg::Broadcast(msg)
  }
}
impl From<DkgInit> for P2PControlMsg {
  fn from(msg: DkgInit) -> Self {
    P2PControlMsg::DkgInit(msg)
  }
}
impl From<PreprocessInit> for P2PControlMsg {
  fn from(msg: PreprocessInit) -> Self {
    P2PControlMsg::PreprocessInit(msg)
  }
}

//            ->->  ###
impl From<Broadcast> for P2PMessage {
  fn from(msg: Broadcast) -> Self {
    (Into::<P2PControlMsg>::into(msg)).into()
  }
}
impl From<DkgInit> for P2PMessage {
  fn from(msg: DkgInit) -> Self {
    (Into::<P2PControlMsg>::into(msg)).into()
  }
}
impl From<PreprocessInit> for P2PMessage {
  fn from(msg: PreprocessInit) -> Self {
    (Into::<P2PControlMsg>::into(msg)).into()
  }
}

// Type for handler functions
/// Marker trait for all messages (which are to be handled by a node)
/// Not optimal. We use this as supertype and then cast actual messages back to their type.
pub trait ProcessableMsg: Send + Sync {
  fn as_any(&self) -> &dyn Any;
}

impl ProcessableMsg for Broadcast {
  fn as_any(&self) -> &dyn Any {
    self
  }
}
impl ProcessableMsg for DkgInit {
  fn as_any(&self) -> &dyn Any {
    self
  }
}
impl ProcessableMsg for PreprocessInit {
  fn as_any(&self) -> &dyn Any {
    self
  }
}

impl ProcessableMsg for Dkg1Participant {
  fn as_any(&self) -> &dyn Any {
    self
  }
}
impl ProcessableMsg for Dkg2SecretShare {
  fn as_any(&self) -> &dyn Any {
    self
  }
}
impl ProcessableMsg for NonceCommitmentList {
  fn as_any(&self) -> &dyn Any {
    self
  }
}
impl ProcessableMsg for SignInit {
  fn as_any(&self) -> &dyn Any {
    self
  }
}
impl ProcessableMsg for Sign1PartialThresholdSig {
  fn as_any(&self) -> &dyn Any {
    self
  }
}

//    Casting from generic type

type CastFromProcessableMsgError = &'static str;
pub trait CastFromProcessableMsg<T: ProcessableMsg> {
  fn cast(&self) -> Result<&T, CastFromProcessableMsgError>;
}
// MINOR: write a macro for this
impl CastFromProcessableMsg<Broadcast> for dyn ProcessableMsg {
  fn cast(&self) -> Result<&Broadcast, CastFromProcessableMsgError> {
    if let Some(msg) = self.as_any().downcast_ref::<Broadcast>() {
      Ok(msg)
    } else {
      Err("Not a Broadcast!")
    }
  }
}
impl CastFromProcessableMsg<DkgInit> for dyn ProcessableMsg {
  fn cast(&self) -> Result<&DkgInit, CastFromProcessableMsgError> {
    if let Some(msg) = self.as_any().downcast_ref::<DkgInit>() {
      Ok(msg)
    } else {
      Err("Not a DkgInit!")
    }
  }
}
impl CastFromProcessableMsg<PreprocessInit> for dyn ProcessableMsg {
  fn cast(&self) -> Result<&PreprocessInit, CastFromProcessableMsgError> {
    if let Some(msg) = self.as_any().downcast_ref::<PreprocessInit>() {
      Ok(msg)
    } else {
      Err("Not a PreprocessInit!")
    }
  }
}

impl CastFromProcessableMsg<Dkg1Participant> for dyn ProcessableMsg {
  fn cast(&self) -> Result<&Dkg1Participant, CastFromProcessableMsgError> {
    if let Some(msg) = self.as_any().downcast_ref::<Dkg1Participant>() {
      Ok(msg)
    } else {
      Err("Not a Dkg1Participant!")
    }
  }
}
impl CastFromProcessableMsg<Dkg2SecretShare> for dyn ProcessableMsg {
  fn cast(&self) -> Result<&Dkg2SecretShare, CastFromProcessableMsgError> {
    if let Some(msg) = self.as_any().downcast_ref::<Dkg2SecretShare>() {
      Ok(msg)
    } else {
      Err("Not a Dkg2SecretShare!")
    }
  }
}
impl CastFromProcessableMsg<NonceCommitmentList> for dyn ProcessableMsg {
  fn cast(&self) -> Result<&NonceCommitmentList, CastFromProcessableMsgError> {
    if let Some(msg) = self.as_any().downcast_ref::<NonceCommitmentList>() {
      Ok(msg)
    } else {
      Err("Not a NonceCommitmentList!")
    }
  }
}
impl CastFromProcessableMsg<SignInit> for dyn ProcessableMsg {
  fn cast(&self) -> Result<&SignInit, CastFromProcessableMsgError> {
    if let Some(msg) = self.as_any().downcast_ref::<SignInit>() {
      Ok(msg)
    } else {
      Err("Not a SignInit!")
    }
  }
}
impl CastFromProcessableMsg<Sign1PartialThresholdSig> for dyn ProcessableMsg {
  fn cast(&self) -> Result<&Sign1PartialThresholdSig, CastFromProcessableMsgError> {
    if let Some(msg) = self.as_any().downcast_ref::<Sign1PartialThresholdSig>() {
      Ok(msg)
    } else {
      Err("Not a Sign1PartialThresholdSig!")
    }
  }
}

// MINOR: Casting from generic type
//impl<T> OwnedCastFromProcessableMsg<T> for T
//where
//  T: ProcessableMsg,
//{}
