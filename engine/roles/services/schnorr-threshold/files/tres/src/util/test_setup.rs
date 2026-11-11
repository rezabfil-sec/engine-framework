// Collection of functions useful to set up tests
use std::collections::BTreeMap;
use std::sync::Arc;

use bytes::Bytes;
use hyper::body::HttpBody;
use hyper::{Body, Method};
use lazy_static::lazy_static;
use tokio::task::JoinHandle;

use crate::client;
use crate::node::common::*;
use crate::node::validator::*;
use crate::node::*;

pub const NUM_PEERS: u8 = 3;

lazy_static! {
  // SECKEYS[i] corresponds to PUBKEYS[i]
  static ref SECKEYS: [Vec<u8>; NUM_PEERS as usize] = [
  hex::decode("0ebbcc80f25ebcf3c9b6833ced9f2be673da5bd5fee1c6d1d4608373caf9d27a").unwrap(),
  hex::decode("8312ab48a22492d7ec6f74e8d621e58db295741cd3e507ad5cab036b2e6f6f5f").unwrap(),
  hex::decode("931db756ce3fc3fc9a89a0f024454a6ad48b2facff62730b691fc468c5b060a8").unwrap(),
  ];
  static ref PUBKEYS: [Vec<u8>; NUM_PEERS as usize] = [
  hex::decode("48b0c6509029efd5822baf6cac8ad4df38bbab92cf19344b24b0125ab69a7f40").unwrap(),
  hex::decode("0f9896bb7daa3451f248a0cc3b4774b121c70251f3108dfc6dda9d594071ba5e").unwrap(),
  hex::decode("1317e10f8f4a7da7d74eaa116cdd6a2552f4fe0247214bdd86c61ebf3a1b791a").unwrap(),
  ];
}

/// yes, this is ugly but should be enough for this tests
/// 600x is for the P2P connections, 601x for the control/management interface
pub fn get_p2p_address(test_nr: u8, id: u8) -> String {
  assert!(id <= 9);
  //assert!(test_nr <= 590);
  let firstpart = 60 + test_nr;
  format!("localhost:{}0{}", firstpart, id)
}
pub fn get_interface_address(test_nr: u8, id: u8) -> String {
  assert!(id <= 9);
  //assert!(test_nr <= 590);
  let firstpart = 60 + test_nr;
  format!("localhost:{}1{}", firstpart, id)
}

/// returns the peers of the given node (specified by node id)
pub fn get_peers(test_nr: u8, i: u8) -> PeerMap {
  assert!(i != 0);
  assert!(i <= 3);

  let mut map = BTreeMap::new();
  for id in 1..(NUM_PEERS + 1) {
    if i != id {
      let addr = get_p2p_address(test_nr, id);
      let responder_peer_info = NodeInfo::new(addr, PUBKEYS[usize::from(id - 1)].clone());
      map.insert(ID::from(id), responder_peer_info);
    }
  }
  map
}

/// test_nr is needed to allow running tests in parallel
pub fn create_node(test_nr: u8, id: u8) -> Arc<Node> {
  let peers = get_peers(test_nr, id);
  let p2p_addr = get_p2p_address(test_nr, id);
  let interface_addr = get_interface_address(test_nr, id);
  let id_u = usize::from(id - 1);
  Node::new(ID::from(id), p2p_addr, SECKEYS[id_u].clone(), PUBKEYS[id_u].clone(), peers, Some(interface_addr), TestMessageValidator::new()).expect("Error initializing node")
}

pub fn spawn_nodes(node1: &Arc<Node>, node2: &Arc<Node>, node3: &Arc<Node>) -> (JoinHandle<()>, JoinHandle<()>, JoinHandle<()>) {
  let n1 = node1.clone(); // again, take a new reference
  let t1 = tokio::spawn(async move {
    n1.run().await;
  });
  let n2 = node2.clone();
  let t2 = tokio::spawn(async move {
    n2.run().await;
  });
  let n3 = node3.clone();
  let t3 = tokio::spawn(async move {
    n3.run().await;
  });
  (t1, t2, t3)
}

/// Send a GET/POST request to the given address and yield the result
/// Expects that the response has a body and panics otherwise
pub async fn client_request_from_interface<S: AsRef<str>>(addr: S, m: Method, query: S) -> Bytes {
  let client = client::Client::new(addr.as_ref()).await.expect("Error initializing client");
  let mut response = client.send_request(m, query.as_ref()).await.expect("error query");

  assert!(response.status().is_success());
  let body: &mut Body = response.body_mut();
  body.data().await.expect("Option empty").expect("Result is an error")
}
