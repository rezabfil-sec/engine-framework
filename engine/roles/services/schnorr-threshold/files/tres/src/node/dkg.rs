use std::fmt;

use frost_dalek::{keygen::SecretShare, Participant};

#[derive(Debug)]
pub enum DkgError {
  /// state is passed as string to avoid ownership issues
  IllegalTransition { from: String, input: DkgEvent },
}
impl fmt::Display for DkgError {
  fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
    match self {
      DkgError::IllegalTransition { from, input } => {
        write!(f, "Illegal transition from {} with input {:?}", from, input)
      }
    }
  }
}
impl std::error::Error for DkgError {
  fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
    match *self {
      _ => None,
    }
  }
}

/// Typestate pattern for FSM, wrapped in an enum for a static size
/// Inspired by https://hoverbear.org/blog/rust-state-machine-pattern/

/// State of DKG of a single remote peer from the viewpoint of the self peer
// MINOR: implement Sealed traits as frost_dalek
#[derive(Debug, Clone)]
pub struct DkgStateMachineInternal<S: MyDkgState> {
  state: S,
}

pub trait MyDkgState: Sync + Send + std::fmt::Debug {}
impl MyDkgState for Stopped {}
impl MyDkgState for Started {}
impl MyDkgState for CollectingOtherParticipants {}
impl MyDkgState for FinishedCollectingParticipants {}
impl MyDkgState for CollectingOtherSecretShares {}

#[derive(Debug, Clone)]
pub struct Stopped {}
#[derive(Debug, Clone)]
pub struct Started {}
/// we know the Participant of this peer, waiting for the `Participant`s of other peers
#[derive(Debug, Clone)]
pub struct CollectingOtherParticipants {
  frost_participant: Participant,
}
#[derive(Debug, Clone)]
pub struct FinishedCollectingParticipants {}
/// we have our secret share from this peer, waiting for the secret shares from the other peers
#[derive(Debug, Clone)]
pub struct CollectingOtherSecretShares {
  share: frost_dalek::keygen::SecretShare,
}

impl DkgStateMachineInternal<Stopped> {
  pub fn new() -> Self {
    DkgStateMachineInternal::<Stopped> { state: Stopped {} }
  }
  pub fn start(self) -> DkgStateMachineInternal<Started> {
    DkgStateMachineInternal::<Started> { state: Started {} }
  }
}

impl DkgStateMachineInternal<Started> {
  pub fn received_commitments_pok(self, p: Participant) -> DkgStateMachineInternal<CollectingOtherParticipants> {
    DkgStateMachineInternal::<CollectingOtherParticipants> { state: CollectingOtherParticipants { frost_participant: p } }
  }
}

impl DkgStateMachineInternal<CollectingOtherParticipants> {
  pub fn finish_collecting_participants(self) -> (DkgStateMachineInternal<FinishedCollectingParticipants>, Participant) {
    (DkgStateMachineInternal::<FinishedCollectingParticipants> { state: FinishedCollectingParticipants {} }, self.state.frost_participant)
  }
}

impl DkgStateMachineInternal<FinishedCollectingParticipants> {
  pub fn received_secret_share(self, share: frost_dalek::keygen::SecretShare) -> DkgStateMachineInternal<CollectingOtherSecretShares> {
    DkgStateMachineInternal::<CollectingOtherSecretShares> { state: CollectingOtherSecretShares { share } }
  }
}

impl DkgStateMachineInternal<CollectingOtherSecretShares> {
  pub fn finish_collecting_shares(self) -> (DkgStateMachineInternal<Stopped>, SecretShare) {
    (DkgStateMachineInternal::<Stopped>::new(), self.state.share)
  }
}

#[derive(Debug)]
pub enum DkgEvent {
  DkgInit,
  ReceivedParticipant(Participant),
  FinishCollectingParticipants,
  ReceivedSecretShare(frost_dalek::keygen::SecretShare),
  // retrieve SecretShare
  Finish,
}
/// Wraps a DkgStateMachineInternal
/// Clone trait is only needed for error handling, as otherwise the error wouldn't contain the current state or its
/// lifetime would depend on it
#[derive(Debug, Clone)]
pub enum DkgStateMachine {
  Stopped(DkgStateMachineInternal<Stopped>),
  /// we know DKG has started but haven't got a Participant yet
  Started(DkgStateMachineInternal<Started>),
  // received commitments from this peer but waiting for the other peers
  CollectingOtherParticipants(DkgStateMachineInternal<CollectingOtherParticipants>),
  FinishedCollectingParticipants(DkgStateMachineInternal<FinishedCollectingParticipants>),
  // received my secret share from this peer but waiting for the other peers
  CollectingOtherSecretShares(DkgStateMachineInternal<CollectingOtherSecretShares>),
}

impl DkgStateMachine {
  /// DkgStateMachine starts in the `Stopped` state
  pub fn new() -> Self {
    DkgStateMachine::Stopped(DkgStateMachineInternal::<Stopped>::new())
  }
  pub fn process(&mut self, input: DkgEvent) -> Result<(Option<Participant>, Option<SecretShare>), DkgError> {
    // Any idea to do this better but keep it on-stack?
    let mut participant = None;
    let mut secret_share = None;
    // ideally, we would like to move some values out of the reference to self, and then replace it with the new state
    // see https://github.com/rust-lang/rfcs/issues/998
    // In the meanwhile, just swap self with a temporary value and swap it back when we are done
    // Resets on invalid edges cause I can't make the borrow checker see that we only move out of `me` in the success case...
    let me = std::mem::replace(self, DkgStateMachine::new());
    let next_state_res = match me {
      DkgStateMachine::Stopped(m) => match input {
        DkgEvent::DkgInit => Ok(DkgStateMachine::Started(m.start())),
        _ => Err(DkgError::IllegalTransition { from: format!("{:?}", m.state), input }),
      },

      DkgStateMachine::Started(m) => match input {
        DkgEvent::ReceivedParticipant(p) => Ok(DkgStateMachine::CollectingOtherParticipants(m.received_commitments_pok(p))),
        _ => Err(DkgError::IllegalTransition { from: format!("{:?}", m.state), input }),
      },

      DkgStateMachine::CollectingOtherParticipants(m) => match input {
        DkgEvent::FinishCollectingParticipants => {
          let (m, p) = m.finish_collecting_participants();
          participant = Some(p);
          Ok(DkgStateMachine::FinishedCollectingParticipants(m))
        }
        _ => Err(DkgError::IllegalTransition { from: format!("{:?}", m.state), input }),
      },

      DkgStateMachine::FinishedCollectingParticipants(m) => match input {
        DkgEvent::ReceivedSecretShare(s) => Ok(DkgStateMachine::CollectingOtherSecretShares(m.received_secret_share(s))),
        _ => Err(DkgError::IllegalTransition { from: format!("{:?}", m.state), input }),
      },

      DkgStateMachine::CollectingOtherSecretShares(m) => match input {
        DkgEvent::Finish => {
          let (m, share) = m.finish_collecting_shares();
          secret_share = Some(share);
          Ok(DkgStateMachine::Stopped(m))
        }
        _ => Err(DkgError::IllegalTransition { from: format!("{:?}", m.state), input }),
      },
    };
    if let Ok(mut next_state) = next_state_res {
      std::mem::swap(self, &mut next_state);
    } else {
      return Err(next_state_res.unwrap_err());
    }
    Ok((participant, secret_share))
  }
}

// Splitting up the DKG state into each participant was a bad idea. It nicely maps into the existing data structures
// but is ugly for advancing the state machine/doing locking&waiting during concurrent requests
/// Centralized state machine keeping the whole DKG state a node is in
///TODO  Currently only used to sync the state across incoming messages, but should be extended as outlined above
/// Also, this should become a real state machine with built-in transitions
#[derive(Debug)]
pub enum DkgStateMachine2 {
  /// no DKG going on
  Stopped,
  /// wait for all commitments to arrive
  CollectingParticipants,
  /// wait for all secret shares to compute the final long-lived secret share
  CollectingSecretShares(frost_dalek::DistributedKeyGeneration<frost_dalek::keygen::RoundOne>),
}
