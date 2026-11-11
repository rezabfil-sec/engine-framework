use std::collections::BTreeMap;
use std::collections::HashSet;
use std::convert::Infallible;
use std::convert::TryFrom;
use std::error::Error;
use std::iter::Iterator;
use std::mem;
use std::net::SocketAddr;
use std::option::Option;
use std::pin::Pin;
use std::string::String;
use std::sync::Arc;

use futures::stream::{self, StreamExt};
use futures::Future;
use hyper::service::{make_service_fn, service_fn};
use hyper::{Body, Method, Request, Response, Server, StatusCode};
use rand::rngs::OsRng;
use serde_qs;
use tokio::net::TcpListener;
use tokio::net::TcpStream; // for stream.write_all()
use tokio::sync::Notify;
use tokio::sync::RwLock; // std::sync::Mutex may deadlock when trying to lock() inside the same thread
use tokio::sync::{mpsc, mpsc::UnboundedSender, watch}; // async channels
use tokio::sync::{RwLockReadGuard, RwLockWriteGuard};
use tokio::time;
use tokio_stream::wrappers::UnboundedReceiverStream;

use tracing::{debug, info, trace, warn}; // error

use curve25519_dalek::ristretto::RistrettoPoint;
use frost_dalek::{
  keygen::{Coefficients, GroupKey, IndividualPublicKey},
  precomputation, signature,
  signature::{PartialThresholdSignature, SignatureAggregator, ThresholdSignature},
  Participant,
};

pub mod common;
mod dkg;
mod error;
pub mod validator;
use crate::channel::{message::*, P2PChannel};
use crate::client;
use crate::node::common::*;
use crate::node::dkg::*;
use crate::node::error::*;
use crate::node::validator::*;
use crate::transport::noise::*;
use crate::transport::*;
use crate::util;
use crate::util::logging::debug_msg_string;

// sorry for the overly long lines some times. rustfmt does not handle some stuff like function chains smaller than the
// limit in a good way, but afaik this will chnge with rustfmt 2.0.0

enum SATask {
  /// build B: the list of participants and their commitments
  ParticipantList,
  /// aggregate partial signatures, consuming the commitments/nonces
  Aggregate,
}

/// MINOR: might be more efficient to pass T by value
type HandlerFn<T> = dyn for<'a> Fn(&'a Arc<Node>, &'a ID, &'a T) -> Pin<Box<dyn Future<Output = ()> + 'a + Send>> + Send + Sync;
type BoxedHandlerFn = Arc<HandlerFn<dyn ProcessableMsg>>;

struct Handlers {
  broadcast: Option<BoxedHandlerFn>,
  dkg_init: Option<BoxedHandlerFn>,
  dkg_1_participant: Option<BoxedHandlerFn>,
  dkg_2_secret_share: Option<BoxedHandlerFn>,
  preprocess_init: Option<BoxedHandlerFn>,
  nonce_commitment_list: Option<BoxedHandlerFn>,
  sign_init: Option<BoxedHandlerFn>,
  sign_1_partial_threshold_sig: Option<BoxedHandlerFn>,
}
impl Default for Handlers {
  fn default() -> Self {
    Handlers {
      // this casting here is kind of ugly but upcasting in the handler to &dyn ProcessableMsg didn't work...
      // MINOR: pass msg via the heap to allow for zero-copy handling
      broadcast: Some(Arc::new(move |x, y, z| Box::pin(Node::handle_broadcast(x, y, z.cast().unwrap())))),
      dkg_init: Some(Arc::new(move |x, y, z| Box::pin(Node::handle_dkg_init(x, y, z.cast().unwrap())))),
      dkg_1_participant: Some(Arc::new(move |x, y, z| Box::pin(Node::handle_dkg_1_participant(x, y, z.cast().unwrap())))),
      dkg_2_secret_share: Some(Arc::new(move |x, y, z| Box::pin(Node::handle_dkg_2_secret_share(x, y, z.cast().unwrap())))),
      preprocess_init: Some(Arc::new(move |x, y, z| Box::pin(Node::handle_preprocess_init(x, y, z.cast().unwrap())))),
      nonce_commitment_list: Some(Arc::new(move |x, y, z| Box::pin(Node::handle_preprocess_nonce_commitment_list(x, y, z.cast().unwrap())))),
      sign_init: Some(Arc::new(move |x, y, z| Box::pin(Node::handle_sign_init(x, y, z.cast().unwrap())))),
      sign_1_partial_threshold_sig: Some(Arc::new(move |x, y, z| Box::pin(Node::handle_sign_1_partial_threshold_sig(x, y, z.cast().unwrap())))),
    }
  }
}

struct IncomingBroadcast {
  /// the actual payload which is to be broadcast
  payload: P2PDataMsg,
  /// set of nodes where we already have received an ackowledgement
  received_from: HashSet<ID>,
}
impl IncomingBroadcast {
  /// `n_1` gives the total number of nodes from which we expect an acknowledgement from
  pub fn new(payload: P2PDataMsg, received_from: ID, n_1: usize) -> Self {
    let mut set = HashSet::with_capacity(n_1);
    set.insert(received_from);
    IncomingBroadcast { payload, received_from: set }
  }
}
// FIXME refactor this mess into subcomponents
pub struct NodeInfo {
  /// host:port where this node is reachable
  pub addr: std::string::String,
  /// a secure channel to this peer. Messages are queued to be sent by a dedicated task.
  pub channel: Option<UnboundedSender<P2PMessage>>,
  /// Cache in case we need to send sth. but have lost the connection and it's the remote peer's turn to reconnect
  to_be_sent_after_reconnect: Option<stream::Fuse<UnboundedReceiverStream<P2PMessage>>>,
  /// the long-term channel public key file
  pub pubkey: Vec<u8>,
  handlers: Handlers,
  /// In case we are receiving a broadcast from this node we need to verify that all other have also received it
  incoming_broadcast: Option<IncomingBroadcast>,
  /// communication during DKG
  dkg_comm: DkgStateMachine,
  /// long-term signing verification share (public key) (only present after DKG)
  partial_threshold_pubkey: Option<IndividualPublicKey>,

  // SA-specific stuff
  /// public commitments of this peer. Only contains elements on the signature aggregator node
  sa_nonce_commitments: Vec<(RistrettoPoint, RistrettoPoint)>,
}

impl NodeInfo {
  // accepts String and &str as addr
  pub fn new<S: Into<String>>(addr: S, pubkey: Vec<u8>) -> NodeInfo {
    NodeInfo {
      addr: addr.into(),
      channel: None,
      to_be_sent_after_reconnect: None,
      pubkey,
      handlers: Handlers::default(),
      incoming_broadcast: None,
      dkg_comm: DkgStateMachine::new(),
      partial_threshold_pubkey: None,
      sa_nonce_commitments: Vec::with_capacity(0),
    }
  }
}
#[derive(Debug)]
struct LongTermSigningKeys {
  /// public verification key of the group
  group_key: GroupKey,
  /// private signing key share
  secret_key: frost_dalek::keygen::SecretKey,
}

/// Contains all FROST-related stuff of one party
struct FROST {
  /// Is only Some during DKG
  participant_public: Option<Participant>,
  participant_secret: Option<Coefficients>,
  params: Option<frost_dalek::Parameters>,
  /// Only needed to keep state for first round because 2nd round is last round. Must use some kind of sync mechanism
  /// because the first message is a simulated broadcast, which might be delivered out of order
  /// FIXME the whole idea of keeping the DKG state per-participant in NodeInfo was crappy from the start
  /// Do it only in one place
  dkg_state: watch::Receiver<Arc<DkgStateMachine2>>,
  dkg_state_notify: watch::Sender<Arc<DkgStateMachine2>>,
  /// `secret_key` for partial signatures and `group_key` for aggregated signature verification
  /// keeps the latest keys and provides notifications
  lt_signing_keys: watch::Receiver<Option<LongTermSigningKeys>>,
  /// make new keys available
  lt_signing_keys_notify: watch::Sender<Option<LongTermSigningKeys>>,
  /// our secret hiding and binding nonces and their commitments
  /// (Is a unwrapped SecretCommitmentShareList to avoid an extra layer of Option<>)
  secret_nonces: Vec<precomputation::CommitmentShare>,

  // the following fields are SA-specific TODO: factor out
  /// public commitments of this peer. Only contains elements on the signature aggregator node; is empty for all others
  sa_nonce_commitments: Vec<(RistrettoPoint, RistrettoPoint)>,
  /// notify the client interface task that preprocessing is finished
  sa_nonce_commitments_updated: Arc<Notify>,
  /// SA - not stored but regenerated once we collect the sigs
  /// Otherwise we would have to store the message AND a reference to it across multiple handler calls
  //  sig_aggregator: Option<SignatureAggregator<signature::Initial<'static>>>,
  sa_msg: Option<Vec<u8>>,
  /// set of nodes taking part in the current signing op
  sa_participating_nodes: HashSet<ID>,
  /// partial signatures received so far
  sa_partial_sigs: BTreeMap<ID, Sign1PartialThresholdSig>,
  /// obtain/wait for generated threshold signature
  sa_signature: watch::Receiver<Result<ThresholdSignature, ThresholdSigningError>>,
  /// publish new threshold signature
  sa_signature_notify: watch::Sender<Result<ThresholdSignature, ThresholdSigningError>>,
}

pub type PeerMap = BTreeMap<ID, NodeInfo>;
/// used in function declarations expecting a lock guard
trait PeerMapGuard: std::ops::Deref<Target = PeerMap> {}
impl PeerMapGuard for RwLockReadGuard<'_, PeerMap> {}
impl PeerMapGuard for RwLockWriteGuard<'_, PeerMap> {}

/// Models this local peer (represents "us")
pub struct Node {
  id: ID,
  local_addr: RwLock<std::string::String>,
  /// the local long-term channel secret key file
  seckey: Vec<u8>,
  /// the local long-term channel public key file (onlyused to write a new key)
  pubkey: Vec<u8>,
  /// map ID to NodeInfo (only remote peers)
  peers: RwLock<PeerMap>, // a bit overkill, let's pretend we don't know how IDs look like...
  // see https://github.com/tokio-rs/tokio/blob/master/examples/tinydb.rs for how to unwrap and change the data
  // interface to external clients
  local_client_addr: RwLock<Option<std::string::String>>,
  /// triggers a shutdown
  shutdown_tx: watch::Sender<bool>,
  /// provides a future which completes once a shutdown is requested
  shutdown_rx: watch::Receiver<bool>,
  frost: RwLock<FROST>,
  message_validator: Box<dyn MessageValidator + Send + Sync>,
}
impl Node {
  pub fn new(
    id: ID, local_addr: String, seckey: Vec<u8>, pubkey: Vec<u8>, peers: PeerMap, local_client_addr: Option<String>, message_validator: Box<dyn MessageValidator + Send + Sync>,
  ) -> Result<Arc<Self>, ValueError> {
    if id == 0 {
      return Err(ValueError::Inconsistent { msg: "'id' must not be 0" });
    }
    if peers.contains_key(&id) {
      #[rustfmt::skip]
      return Err(ValueError::Inconsistent { msg: "'peers' contains own 'id' as key",});
    }

    let (shutdown_tx, shutdown_rx) = watch::channel::<bool>(false);
    let (lt_signing_keys_notify, lt_signing_keys) = watch::channel(None);
    let (dkg_state_notify, dkg_state) = watch::channel(Arc::new(DkgStateMachine2::Stopped));
    let (sa_signature_notify, sa_signature) = watch::channel(Err(ThresholdSigningError::NoneInitiated));
    let frost = RwLock::new(FROST {
      participant_public: None,
      participant_secret: None,
      params: None,
      dkg_state,
      dkg_state_notify,
      lt_signing_keys,
      lt_signing_keys_notify,
      secret_nonces: Vec::with_capacity(0),
      sa_nonce_commitments: Vec::with_capacity(0),
      sa_nonce_commitments_updated: Arc::new(Notify::new()),
      sa_msg: None,
      sa_participating_nodes: HashSet::with_capacity(peers.len()),
      sa_partial_sigs: BTreeMap::new(),
      sa_signature,
      sa_signature_notify,
    });
    let node = Node {
      id,
      local_addr: RwLock::new(local_addr),
      seckey,
      pubkey,
      peers: RwLock::new(peers),
      local_client_addr: RwLock::new(local_client_addr),
      shutdown_tx,
      shutdown_rx,
      frost,
      message_validator,
    };
    Ok(Arc::new(node))
  }

  /// Generates new communication channel keys used internally to protect communication among nodes, replacing the ones
  /// possibly present in the given files
  pub fn new_channel_keypair() -> (PublicKey, SecretKey) {
    NoiseChannel::generate_keypair()
  }

  /// initiates a shutdown
  pub fn shutdown(self: &Arc<Self>) {
    info!("{}: Shutting down...", self.id);
    self.shutdown_tx.send(true).expect("Bug: All Receivers are dropped");
  }

  /// returns the number of known nodes
  async fn get_n(self: &Arc<Self>) -> ID {
    let map = self.peers.read().await;
    Self::get_n_with_lock(&map)
  }
  fn get_n_with_lock(map: &impl PeerMapGuard) -> ID {
    let n = map.len() + 1;
    ID::try_from(n).expect("#participants n exceeds limit")
  }

  /// Completes when this node is fully connected and thus ready to serve requests
  /// This is only meant for test synchronization (and is therefore public) as it essentially performs busy-waiting
  pub async fn fully_connected(self: &Arc<Self>) {
    let mut connected; // busy-waiting
    loop {
      connected = true;
      {
        let map = self.peers.read().await;
        for (_id, peerinfo) in map.iter() {
          if let Some(channel) = &peerinfo.channel {
            if channel.is_closed() {
              connected = false;
              break;
            }
          } else {
            connected = false;
            break;
          }
        }
      }
      if connected {
        return;
      } else {
        time::sleep(time::Duration::from_millis(100)).await;
      }
    }
  }

  /// enables or disables processing for the specified peer IDs
  async fn set_handler_dkg_1_participant(self: &Arc<Self>, remote_ids: impl Iterator<Item = ID>, func: &BoxedHandlerFn) {
    let mut map = self.peers.write().await;
    for id in remote_ids {
      map.get_mut(&id).expect(&*format!("Peer {} not known", id)).handlers.dkg_1_participant = Some(func.clone());
    }
  }

  /// Send a single message to a single peer
  fn unicast_to(id: &ID, peerinfo: &NodeInfo, msg: P2PMessage) {
    if let Some(channel) = &peerinfo.channel {
      let res = channel.send(msg);
      if res.is_err() {
        warn!("Error sending unicast msg to {}: {}", id, res.unwrap_err());
      }
    } else {
      warn!("No channel to {}", id);
    }
  }
  /// Sends a sequence of messages to all peers: peer 0 gets message 0, peer 1 gets msg 1, ...
  /// Expects the already locked peermap of `self`
  fn unicast_sequence(peermap: &RwLockReadGuard<PeerMap>, msgs: impl Iterator<Item = P2PMessage>) {
    let mut num_peers_left = peermap.len();

    for ((id, peerinfo), msg) in peermap.iter().zip(msgs) {
      num_peers_left -= 1;
      Self::unicast_to(id, peerinfo, msg);
    }
    assert_eq!(num_peers_left, 0); // msgs iterator might stop first, which is a bug
  }
  /// Sends the same message to all connected peers via unicast
  async fn unicast_to_all(self: &Arc<Self>, msg: P2PMessage) {
    debug!("Peer {} unicast '{}...' to all", self.id, debug_msg_string(&msg));
    let peermap = self.peers.read().await;

    Self::unicast_sequence(&peermap, peermap.keys().map(|_| msg.clone()));
  }

  /// Encapsulates `msg` as a broadcats message and sends it.
  /// Requires the node to be running and connected
  async fn broadcast_with_lock(self: &Arc<Self>, peermap: &impl PeerMapGuard, msg: P2PDataMsg) {
    debug!("Peer {} broadcasting '{}...'", self.id, debug_msg_string(&msg));
    let msg: P2PMessage = Broadcast { src_id: 0, payload: msg }.into();

    for (id, peerinfo) in peermap.iter() {
      if let Some(channel) = &peerinfo.channel {
        let res = channel.send(msg.clone());
        if res.is_err() {
          warn!("Error broadcasting msg {:?}: {}", &msg, res.unwrap_err());
        }
      } else {
        warn!("No channel to {}", id);
      }
    }
  }
  /// Encapsulates `msg` as a broadcats message and sends it.
  /// Requires the node to be running and connected
  async fn broadcast(self: &Arc<Self>, msg: P2PDataMsg) {
    let peermap = self.peers.read().await;
    self.broadcast_with_lock(&peermap, msg).await;
  }
  /// Deadlocks iff caller holds lock for self.peers
  async fn acknowledge_broadcast(self: &Arc<Self>, source_id: ID, msg: P2PDataMsg) {
    debug!("Peer {} ACKs broadcast (sender={}) '{}...'", self.id, source_id, debug_msg_string(&msg));
    let map = self.peers.read().await;
    let msg: P2PMessage = Broadcast { src_id: source_id, payload: msg }.into();

    for (id, peerinfo) in map.iter() {
      if *id != source_id {
        if let Some(channel) = &peerinfo.channel {
          let res = channel.send(msg.clone());
          if res.is_err() {
            warn!("Error ACKing broadcast msg {}: {}", debug_msg_string(&msg), res.unwrap_err());
          }
        } else {
          warn!("No channel to {}", id);
        }
      }
    }
  }

  async fn handle_broadcast(self: &Arc<Self>, remote_id: &ID, msg: &Broadcast) {
    let sender_id = if msg.src_id == 0 {
      self.acknowledge_broadcast(*remote_id, msg.payload.clone()).await;
      *remote_id
    } else {
      msg.src_id
    };
    // this function must be Send-able
    let fut = {
      assert_ne!(sender_id, 0);
      debug!("Handling broadcast transmitted from {} via {}", sender_id, remote_id);
      let mut map = self.peers.write().await;
      let n_1 = map.len();
      let peer = map.get_mut(&sender_id).unwrap();
      match peer.incoming_broadcast.as_mut() {
        Some(incoming_broadcast) => {
          if incoming_broadcast.payload == msg.payload {
            incoming_broadcast.received_from.insert(*remote_id);
            assert_ne!(incoming_broadcast.received_from.len(), 1);
            debug!("Handling broadcast ({} via {}): copies received: {}/{}", sender_id, remote_id, incoming_broadcast.received_from.len(), n_1);
          } else {
            panic!("Incoming broadcast '{:?}' during ongoing broadcast '{:?}'!", msg, incoming_broadcast.payload);
          }
        }
        None => {
          peer.incoming_broadcast = Some(IncomingBroadcast::new(msg.payload.clone(), *remote_id, n_1));
          debug!("Handling 1st broadcast ({} via {}): copies received: {}/{}", sender_id, remote_id, peer.incoming_broadcast.as_ref().unwrap().received_from.len(), n_1);
        }
      };
      // in case n=2 a broadcast is done as soon as we got a first message
      match peer.incoming_broadcast.as_mut() {
        Some(incoming_broadcast) => {
          if incoming_broadcast.received_from.len() == n_1 {
            // quorum reached
            peer.incoming_broadcast = None;
            match &msg.payload {
              // hand over to handler for this peer
              P2PDataMsg::Dkg1Participant(_) => Some(self.handle_data_message(&sender_id, &msg.payload)),
              _ => {
                warn!("Received unexpected broadcast {:?}, dropping", &msg.payload);
                None
              }
            }
          } else {
            None
          }
        }
        _ => None,
      }
    };
    if fut.is_some() {
      fut.unwrap().await;
    }
  }

  async fn dkg_obtain_locks<'a>(self: &'a Arc<Self>, s: DkgStateMachine2) -> (RwLockWriteGuard<'a, FROST>, RwLockWriteGuard<'a, PeerMap>) {
    let mut receiver = {
      let lock = self.frost.write().await;
      lock.dkg_state.clone()
    };
    let mut keep_waiting = true;
    while keep_waiting {
      keep_waiting = {
        if std::mem::discriminant(&s) == std::mem::discriminant(&*receiver.borrow()) {
          false // reached state
        } else {
          true // wait
        }
      };
      if keep_waiting {
        debug!("DKG: Peer {} dkg_obtain_locks for {:?}, waiting", self.id, s);
        receiver.changed().await.unwrap();
      }
    }

    let maplock = self.peers.write().await; // when locking both, always lock peermap first to avoid deadlock
    let frostlock = self.frost.write().await;
    (frostlock, maplock)
  }
  // MINOR: how to pass enum variants without constructing them? Or better move the locking into the state machine...
  async fn dkg_obtain_locks_after_round1_done<'a>(self: &'a Arc<Self>) -> (RwLockWriteGuard<'a, FROST>, RwLockWriteGuard<'a, PeerMap>) {
    let mut receiver = {
      let lock = self.frost.write().await;
      lock.dkg_state.clone()
    };
    let mut keep_waiting = true;
    while keep_waiting {
      keep_waiting = {
        match receiver.borrow().as_ref() {
          DkgStateMachine2::CollectingSecretShares(_) => false,
          _ => true,
        }
      };
      if keep_waiting {
        debug!("DKG: Peer {} dkg_obtain_locks after round 1, waiting", self.id);
        receiver.changed().await.unwrap();
      }
    }
    let maplock = self.peers.write().await; // when locking both, always lock peermap first to avoid deadlock
    let frostlock = self.frost.write().await;
    (frostlock, maplock)
  }

  /// An external client requested to start DKG, so tell that the other nodes
  /// Ideally, we would like to allow the others to verify this request, but for this the external client would have to
  /// broadcast to the others.
  /// Completes as soon as DKG completes (for this peer)
  async fn process_dkg_init_from_client(self: &Arc<Self>, init: DkgInit) -> watch::Receiver<Option<LongTermSigningKeys>> {
    // MINOR do proper locking in case we have not only one client
    let mut receiver = {
      let frost = self.frost.read().await;
      frost.lt_signing_keys_notify.send(None).unwrap(); // reset channel
      frost.lt_signing_keys.clone()
    };
    let msg = init.clone();
    self.unicast_to_all(msg.into()).await;
    self.handle_dkg_init(&self.id, &init).await; // FIXME exit on errors (currently different to paper)

    receiver.changed().await.unwrap();
    let keep_waiting = { receiver.borrow().is_none() };
    if keep_waiting {
      receiver.changed().await.unwrap();
    }
    receiver
  }
  /// process a DkgInit msg: start the DKG phase and communication state machine for each node
  async fn handle_dkg_init(self: &Arc<Self>, _remote_id: &ID, msg: &DkgInit) {
    let (mut frost, mut peermap) = self.dkg_obtain_locks(DkgStateMachine2::Stopped).await;
    info!("Init DKG phase, t={}", msg.t);
    // perform the first DKG step on this node: compute commitments and secret coefficients; broadcast public parts
    let params = frost_dalek::Parameters { n: Self::get_n_with_lock(&peermap), t: msg.t as u32 };
    let (participant, coeffs) = Participant::new(&params, self.id as u32);
    let p = participant.clone();
    frost.participant_public = Some(participant);
    frost.participant_secret = Some(coeffs);
    frost.params = Some(params);
    let msg: P2PDataMsg = Dkg1Participant::from(p).into();
    self.broadcast_with_lock(&peermap, msg).await;
    for (id, peerinfo) in peermap.iter_mut() {
      let res = peerinfo.dkg_comm.process(DkgEvent::DkgInit);
      if res.is_err() {
        panic!("DKG comm. FSM for {} is out of sync: {}", id, res.unwrap_err());
      }
    }

    frost.dkg_state_notify.send(Arc::new(DkgStateMachine2::CollectingParticipants)).unwrap();
  }
  /// Process broadcast commitments and POK
  async fn handle_dkg_1_participant(self: &Arc<Self>, remote_id: &ID, msg: &Dkg1Participant) {
    let (frost, mut peermap) = self.dkg_obtain_locks(DkgStateMachine2::CollectingParticipants).await;
    debug!("DKG: Peer {} received commitments from {}", self.id, remote_id);
    let frost_participant: Participant = msg.into_with(*remote_id);
    let res = frost_participant.proof_of_secret_key.verify(remote_id, &frost_participant.public_key().unwrap());
    if res.is_err() {
      panic!("Peer {} is misbehaving, its zero-knowledge proof of a_{{i 0}} doesn't verify!", remote_id);
    }

    // store participant for later use
    let res = peermap.get_mut(remote_id).unwrap().dkg_comm.process(DkgEvent::ReceivedParticipant(frost_participant));
    if res.is_err() {
      panic!("DKG comm. FSM for {} is out of sync: {}", remote_id, res.unwrap_err());
    }
    // check whether we have received commitments from all of the nodes
    let mut round_one_done = true;
    for (_id, peer) in peermap.iter() {
      match peer.dkg_comm {
        DkgStateMachine::CollectingOtherParticipants(_) => {}
        _ => {
          round_one_done = false;
          break;
        }
      }
    }

    if round_one_done {
      info!("DKG round 1 done");
      // Round 2: send secret shares
      // build vector of participants for frost_dalek
      let mut other_participants = Vec::<Participant>::with_capacity(peermap.len());
      for (_id, peer) in peermap.iter_mut() {
        let res = peer.dkg_comm.process(DkgEvent::FinishCollectingParticipants);
        if res.is_err() {
          panic!("DKG comm. FSM for {} is out of sync: {}", remote_id, res.unwrap_err());
        }
        let (opt_p, _opt_secshare) = res.unwrap();
        assert!(opt_p.is_some());
        other_participants.push(opt_p.unwrap());
      }
      // compute and distribute secret shares for the other peers
      let dkg_state_res = frost_dalek::DistributedKeyGeneration::<_>::new(frost.params.as_ref().unwrap(), &self.id, frost.participant_secret.as_ref().unwrap(), &mut other_participants);
      if dkg_state_res.is_err() {
        // DistributedKeyGeneration<RoundOne>::new() verifies the NIZK proofs again (or rather, we did it needlessly)
        // The documentation still mentiones `alice.proof_of_secret_key.verify`, presumably for completeness
        // Let's just stick to it, DKG shouldn't be that perfomance-critical anyways
        panic!("Misbehaving peers {:?}: their zero-knowledge proofs of a_{{i 0}} don't verify!", dkg_state_res.unwrap_err());
      }
      let dkg_state_frost = dkg_state_res.unwrap();
      // send secret shares
      let secret_shares_for_peers = dkg_state_frost.their_secret_shares().unwrap();
      assert_eq!(secret_shares_for_peers.len(), peermap.len());
      // Note: we could also look at the index inside the share
      Self::unicast_sequence(&peermap.downgrade(), secret_shares_for_peers.iter().map(|s| Dkg2SecretShare { secret_share: s.into() }.into()));
      frost.dkg_state_notify.send(Arc::new(DkgStateMachine2::CollectingSecretShares(dkg_state_frost))).unwrap();
    }
  }
  /// DKG: We got a temporary secret share for computing our long-term partial secret key share, process it
  async fn handle_dkg_2_secret_share(self: &Arc<Self>, remote_id: &ID, msg: &Dkg2SecretShare) {
    debug!("DKG: Peer {} handling secret share from {}", self.id, remote_id);
    // block till Round 1 is done
    // unfortunately handler may execute out of order, because the first round is initiated by a simulated broadcast
    let (mut frost, mut peermap) = self.dkg_obtain_locks_after_round1_done().await;

    let secret_share: frost_dalek::keygen::SecretShare = (&msg.secret_share).into();
    assert_eq!(secret_share.index, self.id);
    // store it until we've received all
    let res = peermap.get_mut(&remote_id).unwrap().dkg_comm.process(DkgEvent::ReceivedSecretShare(secret_share));
    if res.is_err() {
      panic!("DKG comm. FSM for {} is out of sync: {}", remote_id, res.unwrap_err());
    }

    // check whether we have received secret shares from all of the nodes
    let mut round_two_done = true;
    for (_id, peer) in peermap.iter() {
      match peer.dkg_comm {
        DkgStateMachine::CollectingOtherSecretShares(_) => {}
        _ => {
          round_two_done = false;
          break;
        }
      }
    }

    if round_two_done {
      info!("DKG round 2 done");
      // compute partial key:
      // prepare: build vector of participants for frost_dalek
      let mut my_secret_shares = Vec::<frost_dalek::keygen::SecretShare>::with_capacity(peermap.len());
      for (_id, peer) in peermap.iter_mut() {
        let res = peer.dkg_comm.process(DkgEvent::Finish);
        if res.is_err() {
          panic!("DKG comm. FSM for {} is out of sync: {}", remote_id, res.unwrap_err());
        }
        let (_opt_p, opt_secshare) = res.unwrap();
        assert!(opt_secshare.is_some());
        my_secret_shares.push(opt_secshare.unwrap());
      }
      let mut dkg_state_frost_arc = {
        let state = frost.dkg_state.borrow();
        match state.as_ref() {
          DkgStateMachine2::CollectingSecretShares(_) => state.clone(),
          _ => {
            panic!("BUG: Peer {} in wrong DKG state", self.id);
          }
        }
      };
      // println!("dkg 2 FSM refcount Arc: {}; weak: {}", Arc::strong_count(&dkg_state_frost_arc), Arc::weak_count(&dkg_state_frost_arc));
      // we hold the locks and only release them when we are done here, so it's ok to set the new state now
      // reset channel (and free Arc inside it so that we are the only owner)
      frost.dkg_state_notify.send(Arc::new(DkgStateMachine2::Stopped)).unwrap();
      // We are the only ones with a ref to the state, so we can own and mutate it again without copying
      let ref_to_state = Arc::get_mut(&mut dkg_state_frost_arc).expect("Multiple references still living");
      let dkg_state_frost = match mem::replace(ref_to_state, DkgStateMachine2::Stopped) {
        DkgStateMachine2::CollectingSecretShares(dkg) => dkg,
        _ => panic!("BUG: Peer {} in wrong DKG state", self.id),
      };

      let dkg_state_res = dkg_state_frost.to_round_two(my_secret_shares);

      if let Ok(dkg_state) = dkg_state_res {
        // compute partial pubkeys of other nodes
        let this_participant = frost.participant_public.as_ref().unwrap();
        assert_eq!(this_participant.index, self.id);
        for (id, peerinfo) in peermap.iter_mut() {
          let partial_pubkey = dkg_state.calculate_other_verification_share(id, &this_participant);
          debug!("{} computed partial signing pubkey for {}: {:?}", self.id, id, hex::encode(partial_pubkey.to_bytes()));
          peerinfo.partial_threshold_pubkey = Some(partial_pubkey);
        }

        let key_comp_res = dkg_state.finish(this_participant.public_key().unwrap());
        if let Ok((group_key, secret_key)) = key_comp_res {
          debug!("Completed DKG: group key: {:?}", hex::encode(group_key.to_bytes()));
          let partial_pubkey: IndividualPublicKey = (&secret_key).into();
          debug!("Peer {}: partial signing pubkey: {:?}", self.id, hex::encode(partial_pubkey.to_bytes()));

          frost.lt_signing_keys_notify.send(Some(LongTermSigningKeys { group_key, secret_key })).unwrap();
          frost.participant_public = None;
        } else {
          panic!("Error computing key: {:?}", key_comp_res.unwrap_err());
        }
      } else {
        panic!("Error verifying my secret shares: {:?}", dkg_state_res.unwrap_err());
      }
    }
  }

  async fn generate_new_nonce_commitment_pairs(self: &Arc<Self>, number_of_commitments: usize) -> precomputation::PublicCommitmentShareList {
    let (public_commitments, secret_nonces) = precomputation::generate_commitment_share_lists(&mut OsRng, self.id, number_of_commitments);
    {
      let mut frost = self.frost.write().await;
      if !frost.sa_nonce_commitments.is_empty() {
        warn!("Peer {}: overwriting existing nonces!", self.id);
      }
      frost.secret_nonces = secret_nonces.commitments;
    }
    public_commitments
  }

  /// Convention: The peer initiating the preprocessing phase is the signature aggregator
  /// Thus, the public commitments are sent back to this peer
  async fn handle_preprocess_init(self: &Arc<Self>, remote_id: &ID, msg: &PreprocessInit) {
    let public_commitments = self.generate_new_nonce_commitment_pairs(msg.number_of_commitments).await;
    let commitment_msg: NonceCommitmentList = public_commitments.into();
    let peermap = self.peers.read().await;
    Self::unicast_to(remote_id, &peermap[remote_id], commitment_msg.into());
  }

  /// Self is the signature aggregator, generate and store the commitments locally
  /// Future completes when all peers have provided new commitments
  async fn process_preprocess_init_from_client(self: &Arc<Self>, msg: PreprocessInit) {
    {
      let mut peermap = self.peers.write().await;
      for (id, peer) in peermap.iter_mut() {
        if !peer.sa_nonce_commitments.is_empty() {
          warn!("Peer {}: dropping existing commitments of peer {} due to new preprocessing!", self.id, id);
        }
        peer.sa_nonce_commitments.clear();
      }
    }
    let public_commitments = self.generate_new_nonce_commitment_pairs(msg.number_of_commitments).await;
    let sa_nonce_commitments_updated = {
      let mut frost = self.frost.write().await;
      if !frost.sa_nonce_commitments.is_empty() {
        warn!("Peer {}: overwriting existing commitments!", self.id);
      }
      frost.sa_nonce_commitments = public_commitments.commitments;

      // need to drop lock again to not block processing other stuff
      frost.sa_nonce_commitments_updated.clone()
    };

    let fut = sa_nonce_commitments_updated.notified(); // register for notification
    self.unicast_to_all(msg.into()).await;
    fut.await; // wait on notification (avoids bugs where we immediately get back a stored notification)
  }

  /// stores the commitments from the sending peer for future use
  async fn handle_preprocess_nonce_commitment_list(self: &Arc<Self>, remote_id: &ID, msg: &NonceCommitmentList) {
    trace!("Preprocess: Storing commitments from {}", remote_id);
    let mut peermap = self.peers.write().await;
    assert_eq!(peermap[remote_id].sa_nonce_commitments.len(), 0);
    // MINOR avoid copy:
    peermap.get_mut(remote_id).unwrap().sa_nonce_commitments = msg.commitments.clone();

    let missing_some_commitments = peermap.iter().any(|(_id, peer)| peer.sa_nonce_commitments.is_empty());

    if !missing_some_commitments {
      let frost = self.frost.read().await;
      frost.sa_nonce_commitments_updated.notify_waiters(); // notify only already registered tasks
    }
  }

  /// Creates a new signature aggregator instance
  fn create_new_sa<'m>(
    self: &Arc<Self>, task: SATask, lock: &mut RwLockWriteGuard<FROST>, include_self_as_signer: bool, msg: &'m Vec<u8>,
  ) -> Result<SignatureAggregator<signature::Initial<'m>>, ThresholdSigningError> {
    let aggregator = if let Some(key_material) = &*lock.lt_signing_keys.borrow() {
      if lock.params.is_none() {
        return Err(ThresholdSigningError::NoKeys); // or better: no setup performed?
      }
      let mut aggregator = SignatureAggregator::new(lock.params.unwrap(), key_material.group_key, CONTEXT, &msg[..]);
      if include_self_as_signer {
        if lock.sa_nonce_commitments.is_empty() {
          warn!("Peer {}: no nonce commitments available", self.id);
          return Err(ThresholdSigningError::NoNonces);
        }
        aggregator.include_signer(self.id, lock.sa_nonce_commitments[0], (&key_material.secret_key).into());
      }

      aggregator
    } else {
      return Err(ThresholdSigningError::NoKeys);
    };

    if matches!(task, SATask::Aggregate) {
      lock.sa_nonce_commitments.remove(0); // Ugh. FIXME do this differently. Or do all nonce mgmt here
    }
    Ok(aggregator)
  }

  /// This node was contacted by the client and is therefore the SA - initiate signing on the peers
  /// Return value may contain encountered errors before (-> client's fault) and after collecting (-> our fault) the
  /// partial signatures
  async fn process_sign_init_from_client(self: &Arc<Self>, msg: Vec<u8>) -> Result<watch::Receiver<Result<ThresholdSignature, ThresholdSigningError>>, ThresholdSigningError> {
    info!("Peer {} initiates signing round on request of the client", self.id);
    let mut aggregator = {
      let peermap = self.peers.read().await;
      let mut frost = self.frost.write().await;
      let mut aggregator = self.create_new_sa(SATask::ParticipantList, &mut frost, true, &msg)?;
      if let Some(_) = frost.sa_msg {
        panic!("Concurrent signing operation");
      }
      assert!(frost.sa_msg.is_none());
      assert!(frost.sa_participating_nodes.is_empty());
      assert!(frost.sa_partial_sigs.is_empty());
      frost.sa_msg = Some(msg.clone());
      frost.sa_participating_nodes.insert(self.id);

      for (id, peer) in peermap.iter() {
        if peer.sa_nonce_commitments.is_empty() {
          warn!("Peer {}: out of commitments for peer {}", self.id, id);
          return Err(ThresholdSigningError::NoNonces);
        }
        // don't consume the nonce commitments, we'll need them later during aggregation
        aggregator.include_signer(*id, peer.sa_nonce_commitments[0], peer.partial_threshold_pubkey.as_ref().unwrap().clone());
        frost.sa_participating_nodes.insert(*id);
      }
      aggregator
    };

    let signers_frost = aggregator.get_signers();
    let signers: Vec<Signer> = signers_frost.iter().map(|signer| signer.into()).collect();
    let msg = SignInit { msg, b: signers };
    let partial_sig_res = self.threshold_sign(&msg).await;

    let mut receiver = {
      let frost = self.frost.read().await;
      // reset channel
      frost.sa_signature_notify.send(Err(ThresholdSigningError::NoneInitiated)).unwrap();
      frost.sa_signature.clone()
    };
    self.unicast_to_all(msg.into()).await;
    if let Ok(partial_sig) = partial_sig_res {
      // process own partial signature
      self.handle_sign_1_partial_threshold_sig(&self.id, &(partial_sig.into())).await;
    } else {
      warn!("Local signing error: {}", partial_sig_res.unwrap_err());
    }
    info!("Peer {} waiting for partial signatures", self.id);
    receiver.changed().await.unwrap();
    let keep_waiting = {
      if let Err(ThresholdSigningError::NoneInitiated) = &*receiver.borrow() {
        true
      } else {
        false
      }
    };
    if keep_waiting {
      receiver.changed().await.unwrap();
    }
    Ok(receiver)
  }

  /// Compute a threshold signature for the given message and list of other signers
  async fn threshold_sign(self: &Arc<Self>, msg: &SignInit) -> Result<PartialThresholdSignature, ThresholdSigningError> {
    if !self.message_validator.is_ok_to_sign(&msg.msg[..]) {
      return Err(ThresholdSigningError::RejectedMsg(format!("Peer {}: rejected this message for signing: {}", self.id, hex::encode(&msg.msg[..]))));
    }

    let mut frost = self.frost.write().await;
    if frost.secret_nonces.is_empty() {
      warn!("Peer {}: no more nonces", self.id);
      return Err(ThresholdSigningError::NoNonces);
    }
    let secret_nonce_part = frost.secret_nonces.remove(0);
    let result = {
      if let Some(key_material) = &*frost.lt_signing_keys.borrow() {
        let message_hash = signature::compute_message_hash(CONTEXT, &msg.msg[..]);
        /* Now we could:
        * add serde as dependency to frost_dalek (make SecretCommitmentShareList serializable) and keep index of used nonces
        * manually manage nonce usage <- we are doing this in order to patch frost_dalek as little as possible

        Ugly and bad as hell, and synchronization with the public list is still an issue
         */
        let mut secret_comshares = precomputation::SecretCommitmentShareList { commitments: vec![secret_nonce_part] };
        let signers: Vec<signature::Signer> = msg.b.iter().map(|signer| signer.into()).collect();

        Ok(key_material.secret_key.sign(&message_hash, &key_material.group_key, &mut secret_comshares, 0, &signers).unwrap())
      } else {
        Err(ThresholdSigningError::NoKeys)
      }
    };
    result
  }

  // Node participating in signature generation is requested to supply its partial signature
  async fn handle_sign_init(self: &Arc<Self>, remote_id: &ID, msg: &SignInit) {
    let partial_sig_res = self.threshold_sign(msg).await;
    if let Ok(partial_sig) = partial_sig_res {
      let peermap = self.peers.read().await;
      let partial_sig_msg: Sign1PartialThresholdSig = partial_sig.into();
      Self::unicast_to(remote_id, &peermap[remote_id], partial_sig_msg.into());
    } else {
      warn!("Ignoring signing request due to error {:?}", partial_sig_res.unwrap_err());
    }
  }
  /// Aggregates the partial signatures and, when we have enough, compute the partial signature
  async fn handle_sign_1_partial_threshold_sig(self: &Arc<Self>, remote_id: &ID, msg: &Sign1PartialThresholdSig) {
    info!("Signing: Peer {} received partial sig from {}", self.id, remote_id);
    let mut peermap = self.peers.write().await;
    let mut frost = self.frost.write().await;
    frost.sa_partial_sigs.insert(*remote_id, msg.clone());

    debug!("Peer {}: signature shares {}/{}", self.id, frost.sa_partial_sigs.len(), frost.sa_participating_nodes.len());

    if frost.sa_participating_nodes.len() == frost.sa_partial_sigs.len() {
      // got all needed partial values
      let result = {
        frost.sa_participating_nodes.clear();

        let mut sigs: Vec<PartialThresholdSignature> = frost.sa_partial_sigs.iter().map(|(index, s)| s.into_with(index)).collect();
        frost.sa_partial_sigs.clear();
        let msg = mem::replace(&mut frost.sa_msg, None).unwrap();

        let mut aggregator = self.create_new_sa(SATask::Aggregate, &mut frost, true, &msg).unwrap();

        for (id, peer) in peermap.iter_mut() {
          let big_d_big_e = peer.sa_nonce_commitments.remove(0);
          aggregator.include_signer(*id, big_d_big_e, peer.partial_threshold_pubkey.as_ref().unwrap().clone());
        }
        for partial_sig in sigs.drain(0..) {
          aggregator.include_partial_signature(partial_sig);
        }

        match aggregator.finalize() {
          Err(map) => Err(ThresholdSigningError::AggregatorError(map)), // our errors
          Ok(aggregator) => {
            // their errors
            match aggregator.aggregate() {
              Err(map) => Err(ThresholdSigningError::AggregationError(map)),
              Ok(threshold_signature) => Ok(threshold_signature),
            }
          }
        }
      };

      frost.sa_signature_notify.send(result).unwrap();
    }
  }

  /// Authenticates a remote peer by verifying that it's public key is part of the 'peers' map
  /// If we know it, return Some(id), else None
  pub async fn is_pubkey_known(self: Arc<Self>, remote_pubkey: &[u8]) -> Option<ID> {
    let mut matched_id = None;
    let map = self.peers.read().await;
    for (id, peerinfo) in map.iter() {
      if peerinfo.pubkey == *remote_pubkey {
        trace!("{}: Comparing with public key {} of peer {}", hex::encode(&self.seckey[..3]), hex::encode(&peerinfo.pubkey), id);
        if matched_id.is_some() {
          panic!("Found accepted public key {} twice: {} and {}", hex::encode(remote_pubkey), id, matched_id.unwrap());
        }
        matched_id = Some(*id);
      }
    }
    matched_id
  }
  // Rc instead of Arc would also work, but stick to Arc to make supporting multiple threads easier later on
  /// Handles an incoming P2P connection
  async fn handle_handshake(self: &Arc<Self>, stream: TcpStream) -> Result<(), Box<dyn Error>> {
    let addr = stream.peer_addr().unwrap_or_else(|_| "0.0.0.0:0".parse().unwrap());
    let channel_hs = NoiseChannel::<Handshaking>::new(None, stream);
    let s = self.clone();
    let (id, channel) = channel_hs
      .handshake(
        &self.seckey,
        Arc::new(move |k| {
          let s2 = s.clone();
          Box::pin(Self::is_pubkey_known(s2, k))
        }),
      )
      .await?;
    info!("Performed handshake with peer {} at {}", id, &addr);

    self.transport_on_channel(id, P2PChannel::new(channel)).await;
    // all senders dropped, exiting
    Ok(())
  }

  /// server-side P2P
  async fn listen(self: &Arc<Self>) {
    // addr must stay valid while bind() future is being evaluated, so copy it because mutex is not Send-able
    let listener = {
      let addr = self.local_addr.read().await;
      let l = TcpListener::bind(&*addr).await.expect("Could not bind to address");
      println!("Listening on {}", &addr);
      l
    };

    let mut doing_shutdown = self.shutdown_rx.clone();

    loop {
      tokio::select! {
        connresult = listener.accept() => {
      let s = self.clone();
      let (stream, _) = connresult.unwrap();
      tokio::spawn(async move {
        let res = s.handle_handshake(stream).await;
        if res.is_err() {
          println!("Error handling connection: {}", res.unwrap_err());
        }
      });
      }
      _ = doing_shutdown.changed() => {
        trace!("{}: Shutting down listener", self.id);
        return;}
      }
    }
  }

  /// client-side P2P
  /// set up the initial connections to all peers
  async fn connect_to_peers(self: &Arc<Self>) -> Vec<tokio::task::JoinHandle<()>> {
    let map = self.peers.read().await;
    let mut futures = Vec::new();

    for (id, peerinfo) in map.iter().filter(|(&id, _)| id > self.id) {
      let addr = peerinfo.addr.clone();
      let s = self.clone();
      let remote_pubkey = peerinfo.pubkey.clone();
      let id = *id;
      let handle = tokio::spawn(async move {
        info!("Connecting to peer {} at {}", id, &addr);
        let chan = P2PChannel::connect_to(&s.seckey, &addr, &remote_pubkey).await.expect("Error during first connection setup");
        s.transport_on_channel(id, chan).await;
      });
      futures.push(handle);
    }
    futures
  }

  /// Map a P2PMessage to a handler (function), which consumes this message
  /// Hands off message processing to the appropriate handler function for this peer
  async fn handle_message(self: Arc<Self>, remote_id: ID, msg: P2PMessage) {
    tokio::spawn(async move {
      // handle messages concurrently, since the handlers may block
      match msg {
        P2PMessage::Control(msg) => self.handle_control_message(&remote_id, &msg).await,
        P2PMessage::Data(msg) => self.handle_data_message(&remote_id, &msg).await,
      }
    });
  }
  async fn handle_control_message(self: &Arc<Self>, remote_id: &ID, msg: &P2PControlMsg) {
    debug!("Peer {}: from {} handle control msg {:?}...", self.id, remote_id, debug_msg_string(msg));
    let dkg_init_msg;
    let broadcast_msg;
    let preprocess_init_msg;

    let (fut_option, msg) = {
      let peer = &self.peers.read().await[&remote_id];
      match msg {
        P2PControlMsg::DkgInit(msg) => {
          if let Some(handler) = &peer.handlers.dkg_init {
            dkg_init_msg = msg;
            // Need to clone the handler because we can't hold the map mutex
            (Some(handler.clone()), Some(dkg_init_msg as &dyn ProcessableMsg))
          } else {
            (None, None)
          }
        }
        P2PControlMsg::Broadcast(msg) => {
          if let Some(handler) = &peer.handlers.broadcast {
            broadcast_msg = msg;
            (Some(handler.clone()), Some(broadcast_msg as &dyn ProcessableMsg))
          } else {
            warn!("Missing handler for broadcast msgs!");
            (None, None)
          }
        }
        P2PControlMsg::PreprocessInit(msg) => {
          if let Some(handler) = &peer.handlers.preprocess_init {
            preprocess_init_msg = msg;
            (Some(handler.clone()), Some(preprocess_init_msg as &dyn ProcessableMsg))
          } else {
            warn!("Missing handler for PreprocessInit msgs!");
            (None, None)
          }
        }
      }
    };
    if let Some(fut) = fut_option {
      fut(self, &remote_id, msg.unwrap()).await;
    }
  }
  async fn handle_data_message(self: &Arc<Self>, remote_id: &ID, msg: &P2PDataMsg) {
    debug!("Peer {}: from {} handle data msg {}...", self.id, remote_id, debug_msg_string(msg));
    let dkg_1_participant_msg;
    let dkg_2_secret_share_msg;
    let nonce_commitment_list_msg;
    let sign_init_msg;
    let sign_1_partial_threshold_sig_msg;

    // a bit complex because we need to drop map before we await the handler's completion
    let (fut_option, msg) = {
      let map = self.peers.read().await;
      let peer = map.get(&remote_id).unwrap();
      match msg {
        P2PDataMsg::Dkg1Participant(msg) => {
          dkg_1_participant_msg = msg; // trick to increase the lifetime
          if let Some(handler) = &peer.handlers.dkg_1_participant {
            (Some(handler.clone()), Some(dkg_1_participant_msg as &dyn ProcessableMsg))
          } else {
            (None, None)
          }
        }
        P2PDataMsg::Dkg2SecretShare(msg) => {
          dkg_2_secret_share_msg = msg;
          if let Some(handler) = &peer.handlers.dkg_2_secret_share {
            (Some(handler.clone()), Some(dkg_2_secret_share_msg as &dyn ProcessableMsg))
          } else {
            (None, None)
          }
        }
        P2PDataMsg::NonceCommitmentList(msg) => {
          if let Some(handler) = &peer.handlers.nonce_commitment_list {
            nonce_commitment_list_msg = msg;
            (Some(handler.clone()), Some(nonce_commitment_list_msg as &dyn ProcessableMsg))
          } else {
            warn!("Missing handler for NonceCommitmentList msgs!");
            (None, None)
          }
        }
        P2PDataMsg::SignInit(msg) => {
          if let Some(handler) = &peer.handlers.sign_init {
            sign_init_msg = msg;
            (Some(handler.clone()), Some(sign_init_msg as &dyn ProcessableMsg))
          } else {
            warn!("Missing handler for NonceCommitmentList msgs!");
            (None, None)
          }
        }
        P2PDataMsg::Sign1PartialThresholdSig(msg) => {
          if let Some(handler) = &peer.handlers.sign_1_partial_threshold_sig {
            sign_1_partial_threshold_sig_msg = msg;
            (Some(handler.clone()), Some(sign_1_partial_threshold_sig_msg as &dyn ProcessableMsg))
          } else {
            warn!("Missing handler for NonceCommitmentList msgs!");
            (None, None)
          }
        }
      }
    };

    if let Some(fut) = fut_option {
      fut(self, &remote_id, msg.unwrap()).await;
    }
  }

  async fn try_recover_connection(self: &Arc<Self>, remote_id: ID) -> Option<Result<P2PChannel, Box<dyn Error>>> {
    if self.id < remote_id {
      warn!("Peer {} trying to recover connection to peer {} ...", self.id, remote_id);
      let res = {
        let map = self.peers.read().await;
        let addr = map[&remote_id].addr.clone();
        let remote_pubkey = map[&remote_id].pubkey.clone();
        P2PChannel::connect_to(&self.seckey, &addr, &remote_pubkey).await
      };
      println!("reconnecting done!");
      if let Ok(chan) = res {
        warn!("Peer {} recovered disconnected from peer {}", self.id, remote_id);
        Some(Ok(chan))
      } else {
        let err = res.unwrap_err();
        warn!("Peer {} failed to re-establish connection to {}: {}", self.id, remote_id, err.as_ref());
        Some(Err(err))
      }
    } else {
      None
    }
  }

  /// Store a queue to send stuff on this channel to the node with the given id
  /// Returns the receiving end of this channel
  async fn get_to_be_sent_stream(self: &Arc<Self>, id: ID) -> stream::Fuse<UnboundedReceiverStream<P2PMessage>> {
    let (sender, receiver) = mpsc::unbounded_channel();
    let mut map = self.peers.write().await;
    if map[&id].channel.is_some() {
      warn!("Channel for {} already present, overwriting", &id);
    }
    // if we already had a connection with queued mesages, re-use the queue
    if let Some(stream) = mem::replace(&mut map.get_mut(&id).unwrap().to_be_sent_after_reconnect, None) {
      assert!(map[&id].to_be_sent_after_reconnect.is_none());
      println!("using existing cache/stream");
      stream
    } else {
      map.get_mut(&id).unwrap().channel = Some(sender);
      UnboundedReceiverStream::new(receiver).fuse()
    }
  }

  /// Communication endpoint for the peers: processes incoming messages and perform sends when requested
  /// Runs as long as this node runs.
  async fn transport_on_channel(self: &Arc<Self>, remote_id: ID, channel: P2PChannel) {
    // TODO better way of organizing responsibility for connection setup than: smallerid -> biggerid
    // TODO communicate shutdown to peer to allow graceful shutdown there
    let mut receiver = self.get_to_be_sent_stream(remote_id).await;
    let mut doing_shutdown = self.shutdown_rx.clone();
    let mut msg_channel = channel;

    loop {
      tokio::select! {
        result = msg_channel.read_msg() => {
          debug!("Peer {} received on channel from {}", self.id, remote_id);
          if let Ok(msg) = result {
            let s = self.clone();
            s.handle_message(remote_id, msg).await;
          } else {
            warn!("Peer {} got disconnected from peer {}: {}", self.id, remote_id, result.unwrap_err());
            let opt = self.try_recover_connection(remote_id).await;
            if let Some(res) = opt {
              if let Ok(chan) = res {
                msg_channel = chan;
                continue;
              }
            } else {
              println!("waiting for other peer to reconnect to us");
            }
            return;
          }
        },
        Some(msg) = receiver.next() => {
          // receive from internal queue of messages to be sent
          debug!("Peer {}->{} sending msg {}... on channel", self.id, remote_id, debug_msg_string(&msg));
            let send_res = {
              let send_res = msg_channel.write_msg(&msg).await;
              if let Err(err) = send_res {
                warn!("Couldn't send msg '{}' to peer {}: {} ", debug_msg_string(&msg), remote_id, err);
                Err(())
              } else {
                Ok(())
              }
            };
            if send_res.is_err() {
              warn!("Couldn't send message to peer {}", remote_id);
              let (reconnect_responsible, reconnected) = {
                if let Some(res) = self.try_recover_connection(remote_id).await {
                  if let Ok(chan) = res {
                    msg_channel = chan;
                    (true, true)
                  } else {
                    (true, false)
                  }
                } else { // not our turn to initiate the connection, wait for handshake
                  (false, false)
                }
              };
              if !reconnect_responsible {
                let mut map = self.peers.write().await;
                map.get_mut(&remote_id).unwrap().to_be_sent_after_reconnect = Some(receiver);
                return; // we will be invoked again if the remote peer handshakes with us
              }
              if reconnected {
                if let Err(e) = msg_channel.write_msg(&msg).await {
                  panic!("Couldn't send msg '{}', dropping it: {} ", debug_msg_string(&msg), e);
                }
                println!("could finally send msg after reconnect");
              } else {
                panic!("reconnect failed");
              }
          }
        },
        _ = doing_shutdown.changed() => {trace!("{}: Shutting down transport task", self.id);
          return;
        },
      }
    }
  }

  // adapted from https://docs.rs/hyper/0.14.7/hyper/body/fn.to_bytes.html
  //  pub async fn limited_till_newline<T: hyper::body::HttpBody + std::marker::Unpin>(body: T, limit: usize) -> Result<Bytes, T::Error> {
  //    futures_util::pin_mut!(body);
  //
  //    // If there's only 1 chunk, we can just return Buf::to_bytes()
  //    let mut first = if let Some(buf) = body.data().await {
  //      buf?
  //    //      let res =  buf?;
  //    //      if res.remaining() >= limit{
  //    //        res[..limit]
  //    //      }else{
  //    //        res
  //    //      }
  //    } else {
  //      return Ok(Bytes::new());
  //    };
  //
  //    let second = if let Some(buf) = body.data().await {
  //      buf?
  //    } else {
  //      return Ok(first.copy_to_bytes(first.remaining()));
  //    };
  //
  //    // With more than 1 buf, we gotta flatten into a Vec first.
  //    let cap = cmp::min(limit, first.remaining() + second.remaining() + body.size_hint().lower() as usize);
  //    let mut vec = Vec::with_capacity(cap);
  //    //    let mut mystr = String::new();
  //    // let bnytes_read = first.chain(second).reader().bytes().take_while(|&b| b.unwrap() != b'\n').take(limit).read_line(mystr);
  //    let _bnytes_read = first.chain(second).take(limit).reader().lines().next();
  //
  //    //    vec.put(d);
  //    //    vec.put(second);
  //    while let Some(buf) = body.data().await {
  //      vec.put(buf?);
  //    }
  //
  //    Ok(vec.into())
  //  }

  /// process an HTTP request from a client
  async fn handle_client(self: &Arc<Self>, req: Request<Body>) -> Result<Response<Body>, hyper::Error> {
    let mut response = Response::new(Body::empty()); // Infallible

    match (req.method(), req.uri().path()) {
      (&Method::GET, "/") => {
        *response.body_mut() = Body::from("POST data to /sign to get a signature for it");
      }
      (&Method::GET, "/n") => {
        let msg = client::message::NumParticipantsMsg { n: self.get_n().await };
        *response.body_mut() = Body::from(serde_json::to_string(&msg).unwrap());
      }
      (&Method::GET, "/fully_connected") => {
        self.fully_connected().await;
        *response.status_mut() = StatusCode::OK;
        *response.body_mut() = Body::from("true");
      }
      (&Method::GET, "/group_key") => {
        let frost = self.frost.read().await;
        {
          if let Some(key_material) = &*frost.lt_signing_keys.borrow() {
            *response.status_mut() = StatusCode::OK;
            let response_msg: client::message::GroupKeyMsg = (&key_material.group_key).into();
            *response.body_mut() = Body::from(serde_json::to_string(&response_msg).unwrap());
          } else {
            *response.status_mut() = StatusCode::BAD_REQUEST;
            *response.body_mut() = Body::from("No group key exists - perform DKG first!");
          }
        };
      }
      (&Method::POST, "/dkg") => {
        let q = req.uri().query();
        if q.is_none() {
          *response.status_mut() = StatusCode::BAD_REQUEST;
          *response.body_mut() = Body::from("Pass the threshold as a querystring!");
        } else {
          let res = serde_qs::from_str(q.unwrap());
          if res.is_err() {
            *response.status_mut() = StatusCode::BAD_REQUEST;
            *response.body_mut() = Body::from("Querystring should be like ?t=42");
          } else {
            let msg: DkgInit = res.unwrap();
            if msg.t < 1 || msg.t > self.get_n().await {
              *response.status_mut() = StatusCode::BAD_REQUEST;
              *response.body_mut() = Body::from("Threshold must be in [1, n]");
            } else {
              let receiver = self.process_dkg_init_from_client(msg).await; // Completes when DKG is done
              {
                if let Some(key_material) = &*receiver.borrow() {
                  *response.status_mut() = StatusCode::OK;
                  let response_msg: client::message::GroupKeyMsg = (&key_material.group_key).into();
                  *response.body_mut() = Body::from(serde_json::to_string(&response_msg).unwrap());
                } else {
                  *response.status_mut() = StatusCode::INTERNAL_SERVER_ERROR;
                  *response.body_mut() = Body::from("DKG did not complete successfully");
                }
              };
            }
          }
        }
      }
      (&Method::POST, "/preprocess") => {
        let q = req.uri().query();
        if q.is_none() {
          *response.status_mut() = StatusCode::BAD_REQUEST;
          *response.body_mut() = Body::from("Expecting query as querystring");
        } else {
          let parse_res = serde_qs::from_str(q.unwrap());
          if parse_res.is_err() {
            *response.status_mut() = StatusCode::BAD_REQUEST;
            *response.body_mut() = Body::from("Querystring should be like ?n=42");
          } else {
            let msg: PreprocessInit = parse_res.unwrap();
            if msg.number_of_commitments != 0 {
              self.process_preprocess_init_from_client(msg).await;
            }
            *response.status_mut() = StatusCode::OK;
            *response.body_mut() = Body::from("");
          }
        }
      }
      (&Method::GET, "/remaining_nonces") => {
        // return number of remaining nonce pairs
        let frost = self.frost.read().await;
        if !frost.sa_nonce_commitments.is_empty() {
          // at the SA, number of secret and public commitments should match
          assert_eq!(frost.sa_nonce_commitments.len(), frost.secret_nonces.len());
        }
        *response.status_mut() = StatusCode::OK;
        *response.body_mut() = Body::from(serde_json::to_string(&frost.secret_nonces.len()).unwrap());
      }
      (&Method::POST, "/sign") => {
        // TODO
        //let body = req.into_body();
        //let mut buffer = BytesMut::with_capacity(10);
        // body.into_future().read_buf(&mut buffer).await?;
        //let message = s.collect::<Vec<u8>>().await; .take(32768)
        let q = req.uri().query();
        if q.is_none() {
          *response.status_mut() = StatusCode::BAD_REQUEST;
          *response.body_mut() = Body::from("Expecting query as querystring");
        } else {
          let parse_res = serde_qs::from_str(q.unwrap());
          if parse_res.is_err() {
            *response.status_mut() = StatusCode::BAD_REQUEST;
            *response.body_mut() = Body::from("Querystring should be like ?msg=messageToBeSigned");
          } else {
            let m: client::message::SigningRequestMsg = parse_res.unwrap();

            match self.process_sign_init_from_client(m.msg.into_bytes()).await {
              Ok(sign_result_recv) => {
                let sign_result = &*sign_result_recv.borrow();
                if let Ok(threshold_signature) = sign_result {
                  let response_msg: client::message::ThresholdSignature = threshold_signature.into();

                  *response.status_mut() = StatusCode::OK;
                  *response.body_mut() = Body::from(serde_json::to_string(&response_msg).unwrap());
                } else {
                  *response.status_mut() = StatusCode::INTERNAL_SERVER_ERROR;
                  *response.body_mut() = Body::from(format!("Signing did not complete successfully: {}", sign_result.as_ref().unwrap_err()));
                }
              }
              Err(err) => {
                *response.status_mut() = StatusCode::BAD_REQUEST;
                *response.body_mut() = Body::from(format!("Could not start signing: {}", err));
              }
            }
          }
        }
      }
      _ => {
        *response.status_mut() = StatusCode::NOT_FOUND;
      }
    };
    Ok(response)
  }

  /// returns the service interface address from the config, if available and valid
  async fn get_interface_addr(self: &Arc<Self>) -> Option<SocketAddr> {
    // add scope so that we don't hold the lock till the end
    let local_client_addr = { (self.local_client_addr.read().await).clone() };

    if local_client_addr.is_none() {
      return None; // interface not configured and thus apparently not required
    }
    let result = util::dns::resolve(&local_client_addr.unwrap()).await;
    if result.is_err() {
      return None;
    }
    Some(result.unwrap())
  }

  /// offer HTTP interface for clients
  async fn listen_for_clients(self: &Arc<Self>) {
    let service_closure = |req, s: Arc<Node>| async move { s.handle_client(req).await };
    let interface_service = make_service_fn(|_conn| {
      let sel = self.clone();
      async move { Ok::<_, Infallible>(service_fn(move |req| service_closure(req, sel.clone()))) }
    });
    let addr = self.get_interface_addr().await;
    if addr.is_none() {
      eprintln!("No valid interface address configured, not starting HTTP server.");
      return;
    }
    println!("HTTP interface on {:?}.", addr.unwrap());
    let server = Server::bind(&addr.unwrap()).serve(interface_service);
    let mut shutdown_rx = self.shutdown_rx.clone();
    let graceful_server = server.with_graceful_shutdown(async {
      shutdown_rx.changed().await.expect("Bug: sender was dropped");
      trace!("{}: Shutting down interface", self.id);
    });

    if let Err(e) = graceful_server.await {
      eprintln!("HTTP Server error: {}", e);
    }
  }

  /// start this node and block forever
  pub async fn run(self: &Arc<Self>) {
    let s = self.clone(); // this clones the Arc but not self
    let task_listen = tokio::spawn(async move {
      s.listen().await;
    });
    let tasks_connect = self.connect_to_peers().await;
    let s = self.clone();
    let task_client = tokio::spawn(async move {
      s.listen_for_clients().await;
    });

    let (res_listen, res_connect, res_client) = tokio::join!(task_listen, futures::future::join_all(tasks_connect), task_client);

    let mut do_panic = false;
    if res_listen.is_err() {
      println!("Error listening: {}", res_listen.unwrap_err());
      do_panic = true;
    }
    for err in res_connect.iter().filter(|res| res.is_err()) {
      println!("Error connecting: {}", err.as_ref().unwrap_err());
      do_panic = true;
    }
    if res_client.is_err() {
      eprintln!("Error listening for HTTP clients: {}", res_client.unwrap_err());
      do_panic = true;
    }
    if do_panic {
      panic!("due to previous error");
    }
  }
}

#[cfg(test)]
mod tests {
  use super::*;
  use crate::client;
  use crate::util::logging;
  use crate::util::test_setup::*;
  use hyper::body::HttpBody;

  use std::convert::TryInto;
  use tracing_subscriber::filter::LevelFilter;

  #[tokio::test]
  async fn node_setup_comm() {
    logging::init();
    let test_nr = 1;
    let node1 = create_node(test_nr, 1);
    let node2 = create_node(test_nr, 2);
    let node3 = create_node(test_nr, 3);
    let (t1, t2, t3) = spawn_nodes(&node1, &node2, &node3);

    let s = tokio::spawn(async move {
      node1.fully_connected().await;
      info!("node 1 fully connected");
      node2.fully_connected().await;
      info!("node 2 fully connected");
      node3.fully_connected().await;
      info!("node 3 fully connected");
      // TODO
      // shutdown nodes first before we could panic in assertion
      node1.shutdown();
      node2.shutdown();
      node3.shutdown();
    });

    let (r1, r2, r3, rs) = tokio::join!(t1, t2, t3, s);
    assert!(r1.is_ok());
    assert!(r2.is_ok());
    assert!(r3.is_ok());
    assert!(rs.is_ok());
  }

  #[tokio::test]
  async fn node_setup_http_interface_get_n() {
    logging::init();
    let test_nr = 2;
    let node1 = create_node(test_nr, 1);
    let node2 = create_node(test_nr, 2);
    let node3 = create_node(test_nr, 3);

    let (t1, t2, t3) = spawn_nodes(&node1, &node2, &node3);
    let s = tokio::spawn(async move {
      node1.fully_connected().await;
      node2.fully_connected().await;
      node3.fully_connected().await;
      let client = client::Client::new(get_interface_address(test_nr, 1)).await.expect("Error initializing client");
      let result = client.get_n().await;
      // shutdown nodes first before we could panic in assertion
      node1.shutdown();
      node2.shutdown();
      node3.shutdown();
      info!("shut down");
      assert!(result.is_ok(), "Client result: {:?}", result);
      assert_eq!(result.unwrap(), ID::from(NUM_PEERS));
    });

    let (r1, r2, r3, rs) = tokio::join!(t1, t2, t3, s);
    assert!(r1.is_ok());
    assert!(r2.is_ok());
    assert!(r3.is_ok());
    assert!(rs.is_ok());
  }

  #[tokio::test]
  async fn broadcast() {
    logging::init();
    let test_nr = 3;
    let node1 = create_node(test_nr, 1);
    let node2 = create_node(test_nr, 2);
    let node3 = create_node(test_nr, 3);

    let params = frost_dalek::Parameters { n: 3, t: 2 };
    let (participant, _coeffs) = Participant::new(&params, 1);

    // test sending broadcast from 1 to 2 and 3
    let broadcast_payload = Dkg1Participant { commitments: participant.commitments, proof_of_secret_key: participant.proof_of_secret_key.into() };
    let broadcast_payload_copy2 = broadcast_payload.clone();
    let broadcast_payload_copy3 = broadcast_payload.clone();
    let broadcast_msg: P2PDataMsg = broadcast_payload.into();

    let n1_msg = broadcast_msg.clone();

    let n1_for_send = node1.clone();
    let n2_for_send = node2.clone();
    let n3_for_send = node3.clone();
    let t1_sender = tokio::spawn(async move {
      n1_for_send.fully_connected().await;
      n2_for_send.fully_connected().await;
      n3_for_send.fully_connected().await;
      n1_for_send.broadcast(n1_msg).await;
    });
    let n1_for_shutdown = node1.clone();
    let n2_for_shutdown = node2.clone();
    let n3_for_shutdown = node3.clone();
    // node 2
    let (node2_tx_handler_called, mut node2_rx_handler_called) = watch::channel(false);
    let node2_tx_handler_called = Arc::new(node2_tx_handler_called);

    let func2: BoxedHandlerFn = Arc::new(move |_x, y, z| {
      let n1_sd = n1_for_shutdown.clone(); // bah.
      let n2_sd = n2_for_shutdown.clone();
      let n3_sd = n3_for_shutdown.clone();
      let tx = node2_tx_handler_called.clone();
      let broadcast_payload = broadcast_payload_copy2.clone(); // future must be Send-able but ProcessableMsg is not
      let msg: &Dkg1Participant = z.cast().unwrap();
      Box::pin(async move {
        // shutdown nodes first before we could panic in assertion
        n1_sd.shutdown();
        n2_sd.shutdown();
        n3_sd.shutdown();
        assert_eq!(*y, 1); // check sender_id
        assert_eq!(*msg, broadcast_payload);
        tx.send(true).unwrap();
      })
    });
    node2.set_handler_dkg_1_participant((1..3 + 1).filter(|&x| x != 2), &func2).await;

    // node 3
    let (node3_tx_handler_called, mut node3_rx_handler_called) = watch::channel(false);
    let node3_tx_handler_called = Arc::new(node3_tx_handler_called);
    let func3: BoxedHandlerFn = Arc::new(move |_x, y, z| {
      let tx = node3_tx_handler_called.clone();
      let broadcast_payload = broadcast_payload_copy3.clone();
      let msg: &Dkg1Participant = z.cast().unwrap();
      Box::pin(async move {
        assert_eq!(*y, 1); // check sender_id
        assert_eq!(*msg, broadcast_payload);
        tx.send(true).unwrap();
      })
    });
    node3.set_handler_dkg_1_participant((1..3 + 1).filter(|&x| x != 3), &func3).await;

    let (t1, t2, t3) = spawn_nodes(&node1, &node2, &node3);

    let (r1, r2, r3, r1_sender) = tokio::join!(t1, t2, t3, t1_sender);
    assert!(r1.is_ok());
    assert!(r2.is_ok());
    assert!(r3.is_ok());
    assert!(r1_sender.is_ok());
    // expect that handlers were executed
    assert!(node2_rx_handler_called.changed().await.is_ok());
    assert!(*node2_rx_handler_called.borrow());
    assert!(node3_rx_handler_called.changed().await.is_ok());
    assert!(*node3_rx_handler_called.borrow());
  }

  #[tokio::test]
  async fn node_dkg() {
    logging::init();
    let test_nr = 4;
    let node1 = create_node(test_nr, 1);
    let node2 = create_node(test_nr, 2);
    let node3 = create_node(test_nr, 3);

    let (t1, t2, t3) = spawn_nodes(&node1, &node2, &node3);
    let s = tokio::spawn(async move {
      node1.fully_connected().await;
      node2.fully_connected().await;
      node3.fully_connected().await;
      let client = client::Client::new(get_interface_address(test_nr, 1)).await.expect("Error initializing client");
      let mut response = client.post("/dkg?t=2").await.expect("error query");

      assert!(response.status().is_success());
      let body: &mut Body = response.body_mut();
      let groupkey_msg_from_1 = body.data().await.expect("Option empty").expect("Result is an error");
      // TODO timing might be unfortunate
      // get and check group keys from 2 and 3
      let client = client::Client::new(get_interface_address(test_nr, 2)).await.expect("Error initializing client");
      let mut response = client.get("/group_key").await.expect("error query");
      //assert!(response.status().is_success()); // don't assert state; do shutdown first and check for equality then
      let groupkey_msg_from_2 = response.body_mut().data().await.expect("Option empty").expect("Result is an error");

      let client = client::Client::new(get_interface_address(test_nr, 3)).await.expect("Error initializing client");
      let mut response = client.get("/group_key").await.expect("error query");
      let groupkey_msg_from_3 = response.body_mut().data().await.expect("Option empty").expect("Result is an error");

      node1.shutdown();
      node2.shutdown();
      node3.shutdown();

      assert_eq!(groupkey_msg_from_1, groupkey_msg_from_2);
      assert_eq!(groupkey_msg_from_2, groupkey_msg_from_3);
    });

    let (r1, r2, r3, rs) = tokio::join!(t1, t2, t3, s);
    assert!(r1.is_ok());
    assert!(r2.is_ok());
    assert!(r3.is_ok());
    assert!(rs.is_ok());
  }
  #[tokio::test]
  async fn node_signing_preprocessing() {
    logging::init();
    let test_nr = 5;
    let node1 = create_node(test_nr, 1);
    let node2 = create_node(test_nr, 2);
    let node3 = create_node(test_nr, 3);

    let (t1, t2, t3) = spawn_nodes(&node1, &node2, &node3);
    let s = tokio::spawn(async move {
      node1.fully_connected().await;
      node2.fully_connected().await;
      node3.fully_connected().await;

      let client = client::Client::new(get_interface_address(test_nr, 1)).await.expect("Error initializing client");
      let mut response = client.post("/preprocess?n=13").await.expect("error query");
      assert!(response.status().is_success());
      let body: &mut Body = response.body_mut();
      assert!(body.data().await.is_none()); // empty Body

      let number_of_nonces_1 = client_request_from_interface(get_interface_address(test_nr, 1), Method::GET, "/remaining_nonces".to_string()).await;
      let number_of_nonces_2 = client_request_from_interface(get_interface_address(test_nr, 2), Method::GET, "/remaining_nonces".to_string()).await;
      let number_of_nonces_3 = client_request_from_interface(get_interface_address(test_nr, 3), Method::GET, "/remaining_nonces".to_string()).await;

      assert_eq!(number_of_nonces_1, b"13"[..]);
      assert_eq!(number_of_nonces_1, number_of_nonces_2);
      assert_eq!(number_of_nonces_1, number_of_nonces_3);

      node1.shutdown();
      node2.shutdown();
      node3.shutdown();
    });

    let (r1, r2, r3, rs) = tokio::join!(t1, t2, t3, s);
    assert!(r1.is_ok());
    assert!(r2.is_ok());
    assert!(r3.is_ok());
    assert!(rs.is_ok());
  }

  #[tokio::test]
  async fn thresholdsigning() {
    logging::init();
    let test_nr = 6;
    let node1 = create_node(test_nr, 1);
    let node2 = create_node(test_nr, 2);
    let node3 = create_node(test_nr, 3);

    let (t1, t2, t3) = spawn_nodes(&node1, &node2, &node3);
    let s = tokio::spawn(async move {
      node1.fully_connected().await;
      node2.fully_connected().await;
      node3.fully_connected().await;

      // KeyGen
      let client = client::Client::new(get_interface_address(test_nr, 1)).await.expect("Error initializing client");
      let mut response = client.post("/dkg?t=2").await.expect("error query");

      assert!(response.status().is_success());
      let body: &mut Body = response.body_mut();
      let groupkey_msg_from_1 = body.data().await.expect("Option empty").expect("Result is an error");

      let group_key_res = serde_json::from_slice(&groupkey_msg_from_1[..]);
      assert!(group_key_res.is_ok());
      let group_key: client::message::GroupKeyMsg = group_key_res.unwrap();
      let group_key: GroupKey = group_key.try_into().unwrap();

      // Preprocessing
      let mut response = client.post("/preprocess?n=3").await.expect("error query");
      assert!(response.status().is_success()); // as soon as we get a response preprocessing is done
      let body: &mut Body = response.body_mut();
      assert!(body.data().await.is_none()); // empty Body

      // Threshold signing
      let message = "test - A message to be signed...".to_string();
      let m = client::message::SigningRequestMsg { msg: message.clone() };
      let querystring = format!("/sign?{}", serde_qs::to_string(&m).unwrap());
      let mut response = client.post(querystring).await.expect("error query");
      assert!(response.status().is_success());
      let body: &mut Body = response.body_mut();
      let msg = body.data().await.expect("Option empty").expect("Result is an error");

      let response_msg_res = serde_json::from_slice(&msg);
      assert!(response_msg_res.is_ok());

      let my_sig: client::message::ThresholdSignature = response_msg_res.unwrap();
      let sig: ThresholdSignature = my_sig.into();

      let message_hash = signature::compute_message_hash(CONTEXT, &message.as_bytes()[..]);
      let verification_result = sig.verify(&group_key, &message_hash);
      assert!(verification_result.is_ok());

      node1.shutdown();
      node2.shutdown();
      node3.shutdown();
    });

    let (r1, r2, r3, rs) = tokio::join!(t1, t2, t3, s);
    assert!(r1.is_ok());
    assert!(r2.is_ok());
    assert!(r3.is_ok());
    assert!(rs.is_ok());
  }

  // TODO: factor this out into a seperate file, because it intends to tests the client
  #[tokio::test]
  async fn client() {
    logging::init();
    let test_nr = 7;
    let node1 = create_node(test_nr, 1);
    let node2 = create_node(test_nr, 2);
    let node3 = create_node(test_nr, 3);

    let (t1, t2, t3) = spawn_nodes(&node1, &node2, &node3);
    let s = tokio::spawn(async move {
      node1.fully_connected().await;
      node2.fully_connected().await;
      node3.fully_connected().await;

      // KeyGen
      let client = client::Client::new(get_interface_address(test_nr, 1)).await.expect("Error initializing client");
      let group_key = {
        match client.initiate_dkg(&2).await {
          Ok(gk) => gk,
          Err(err) => panic!("DKG error: {}", err),
        }
      };

      // Preprocessing
      match client.initiate_preprocessing(1).await {
        Ok(()) => {}
        Err(err) => panic!("Preprocess error: {}", err),
      }

      // Threshold signing
      let message = "test - A message to be signed...".to_string();
      let message_hash = signature::compute_message_hash(CONTEXT, &message.as_bytes()[..]);
      let threshold_sig = {
        match client.initiate_signing(message).await {
          Ok(sig) => sig,
          Err(err) => panic!("Signing error: {}", err),
        }
      };

      let verification_result = threshold_sig.verify(&group_key, &message_hash);
      assert!(verification_result.is_ok());

      node1.shutdown();
      node2.shutdown();
      node3.shutdown();
    });

    let (r1, r2, r3, rs) = tokio::join!(t1, t2, t3, s);
    assert!(r1.is_ok());
    assert!(r2.is_ok());
    assert!(r3.is_ok());
    assert!(rs.is_ok());
  }

  #[tokio::test]
  async fn multisign() {
    // Since tests run in parallel, we may have to init logging or not -> setting the level per test is not reliable
    logging::init_with_level(LevelFilter::ERROR); // last step would print a warning otherwise, so change the default
    let test_nr = 8;
    let node1 = create_node(test_nr, 1);
    let node2 = create_node(test_nr, 2);
    let node3 = create_node(test_nr, 3);

    let (t1, t2, t3) = spawn_nodes(&node1, &node2, &node3);
    let s = tokio::spawn(async move {
      node1.fully_connected().await;
      node2.fully_connected().await;
      node3.fully_connected().await;

      // KeyGen
      let client = client::Client::new(get_interface_address(test_nr, 1)).await.expect("Error initializing client");
      let group_key = {
        match client.initiate_dkg(&2).await {
          Ok(gk) => gk,
          Err(err) => panic!("DKG error: {}", err),
        }
      };

      // Preprocessing
      match client.initiate_preprocessing(4).await {
        Ok(()) => {}
        Err(err) => panic!("Preprocess error: {}", err),
      }

      // Threshold signing
      for msg_nr in 1..4 + 1 {
        debug!("multisign msg {}", msg_nr);
        let message = format!("test: default validator requires prefix 'test'. This is msg number {}...", msg_nr);
        let message_hash = signature::compute_message_hash(CONTEXT, &message.as_bytes()[..]);
        let threshold_sig = {
          match client.initiate_signing(message).await {
            Ok(sig) => sig,
            Err(err) => panic!("Signing error: {}", err),
          }
        };

        let verification_result = threshold_sig.verify(&group_key, &message_hash);
        assert!(verification_result.is_ok());
      }
      // the next signature request should fail because we've consumed all nonces/commitments
      let message = "test - A message to be signed...".to_string();
      let res = client.initiate_signing(message).await;
      assert!(res.is_err());

      node1.shutdown();
      node2.shutdown();
      node3.shutdown();
    });

    let (r1, r2, r3, rs) = tokio::join!(t1, t2, t3, s);
    assert!(r1.is_ok());
    assert!(r2.is_ok());
    assert!(r3.is_ok());
    assert!(rs.is_ok());
  }

  #[tokio::test(flavor = "multi_thread", worker_threads = 3)]
  async fn dkg_threaded() {
    logging::init();
    let test_nr = 9;
    let node1 = create_node(test_nr, 1);
    let node2 = create_node(test_nr, 2);
    let node3 = create_node(test_nr, 3);

    let (t1, t2, t3) = spawn_nodes(&node1, &node2, &node3);
    let s = tokio::spawn(async move {
      node1.fully_connected().await;
      node2.fully_connected().await;
      node3.fully_connected().await;

      let client = client::Client::new(get_interface_address(test_nr, 1)).await.expect("Error initializing client");
      let group_key_1_from_dkg = {
        match client.initiate_dkg(&2).await {
          Ok(gk) => gk,
          Err(err) => panic!("DKG error: {}", err),
        }
      };
      let group_key_1_from_query = {
        match client.get_group_key().await {
          Ok(gk) => gk,
          Err(err) => panic!("DKG error: {}", err),
        }
      };
      let group_key_2_from_dkg = {
        match client.initiate_dkg(&1).await {
          Ok(gk) => gk,
          Err(err) => panic!("DKG error: {}", err),
        }
      };
      let group_key_2_from_query = {
        match client.get_group_key().await {
          Ok(gk) => gk,
          Err(err) => panic!("DKG error: {}", err),
        }
      };

      node1.shutdown();
      node2.shutdown();
      node3.shutdown();
      assert_eq!(group_key_1_from_dkg, group_key_1_from_query);
      assert_eq!(group_key_2_from_dkg, group_key_2_from_query);
      assert_ne!(group_key_1_from_query, group_key_2_from_query);
    });

    let (r1, r2, r3, rs) = tokio::join!(t1, t2, t3, s);
    assert!(r1.is_ok());
    assert!(r2.is_ok());
    assert!(r3.is_ok());
    assert!(rs.is_ok(), "Test failed");
  }
}
