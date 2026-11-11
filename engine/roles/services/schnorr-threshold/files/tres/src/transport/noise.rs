use std::error::Error;

use async_trait::async_trait;
use snow;
use tokio::io;
use tokio::io::AsyncWriteExt;
use tokio::net::TcpStream;
use tracing::{debug, trace, warn}; // info warn error

use crate::noise::packet::*;
use crate::transport::*;
mod packet;

/// protocol name
/// X: responder does not know key of initiator, it will get this Xmitted (transmitted)
/// K: initiator knows key of responder
/// 25519: Curve25519 keypair (for DH)
/// AES256 with GCM
static PARAMS: &'static str = "Noise_XK_25519_AESGCM_SHA256";
/// maximum size of a NOISE message. See http://noiseprotocol.org/noise.html#message-format
/// This is only a limit on the level of NOISE, higher layers may have higher limits
pub(crate) const MAX_SIZE_MSG: usize = 65535;
/// length of authentication data in Noise.
/// snow::constants also has this constant but is private and there is no interface to get it...
const NOISE_TAGLEN: usize = 16;
/// maximum size of a payload sent via Noise
const MAX_PAYLOAD_SIZE: usize = MAX_SIZE_MSG - NOISE_TAGLEN;
const RECEIVE_BUF_MAX_CAPACITY: usize = MAX_SIZE_MSG + packet::SIZE_LEN_FIELD;

// stuff like this is experimental. see https://github.com/rust-lang/rfcs/issues/2035 and
// https://github.com/rust-lang/rust/issues/41517
//trait SomeDuplexStream = tokio::io::AsyncReadExt + tokio::io::AsyncWriteExt;

/// typestate pattern: first handshake, then payload comm
/// Currently NOT thread-safe, but should be easy to do (tokio TcpStream split or ready)
#[derive(Debug)]
pub struct NoiseChannel<S: ChannelState> {
  stream: TcpStream,
  /// receive buffer, always has capacity RECEIVE_BUF_MAX_CAPACITY
  rxbuf: Box<[u8; RECEIVE_BUF_MAX_CAPACITY]>,
  /// number of bytes received so far
  rxbuf_index: usize,
  txbuf: Box<[u8; RECEIVE_BUF_MAX_CAPACITY]>,
  /// the state we are in
  state: S,
}

impl<S: ChannelState> NoiseChannel<S> {
  /// Sends a NOISE packet
  async fn write_pkt(&mut self, pkt: NoisePacket) -> std::io::Result<()> {
    let data = pkt.to_bytes();
    //debug!("Writing NoisePacket with {} bytes to {:?}", data.len(), self.stream.peer_addr());
    self.stream.write_all(&data[..data.len()]).await?;
    Ok(())
  }
  /// Receives a NOISE packet
  /// This future may be dropped and restarted later again
  async fn read_pkt(&mut self) -> Result<NoisePacket, io::Error> {
    // if self.rxbuf_index != 0 {
    //   debug!("{:p} read_pkt dropped and restarted, buf_index: {}", self, self.rxbuf_index);
    // }

    let (pkt, _) = loop {
      let result = NoisePacket::parse(&self.rxbuf[..self.rxbuf_index]);
      if result.is_ok() {
        let (pkt, len_parsed) = result.unwrap();
        //debug!("{:p} Received NoisePacket with {} bytes from {:?}, buf_index: {}", self, len_parsed, self.stream.peer_addr(), self.rxbuf_index);
        assert_eq!(self.rxbuf_index, len_parsed);
        self.rxbuf_index = 0;
        break (pkt, len_parsed);
      } else {
        let num_bytes_needed = match result.unwrap_err() {
          ConversionError::NeedMoreData { num_bytes } => num_bytes,
          _ => panic!("Bug!"),
        };

        self.stream.readable().await?;
        let res = self.stream.try_read(&mut self.rxbuf[self.rxbuf_index..self.rxbuf_index + num_bytes_needed]);
        match res {
          Ok(0) => return Err(io::Error::new(io::ErrorKind::UnexpectedEof, "read half is closed")),
          Ok(n) => {
            self.rxbuf_index += n;
            //debug!("{:p} Noise read_pkt: buf_index: {}, read: {}, num_bytes_needed: {}.", self, self.rxbuf_index, n, num_bytes_needed);
            assert!(n <= num_bytes_needed);
          }
          Err(ref e) if e.kind() == io::ErrorKind::WouldBlock => {
            continue;
          }
          Err(e) => {
            return Err(e);
          }
        }
      }
    };
    Ok(pkt)
  }

  /// Close the connection and this channel
  pub async fn shutdown(&mut self) -> io::Result<()> {
    self.stream.shutdown().await
  }
}

#[derive(Debug)]
pub struct Handshaking {
  remote_key: Option<PublicKey>,
}
#[derive(Debug)]
pub struct Transporting {
  noise_session: snow::TransportState,
}

impl NoiseChannel<Handshaking> {
  /// Creates a new NoiseChannel in the Handshaking state to a remote peer (authenticated with a given public key)
  ///
  /// if a remote_key is given, we initiated the connection
  pub fn new(remote_key: Option<PublicKey>, stream: TcpStream) -> Self {
    NoiseChannel { stream, rxbuf: Box::new([0u8; RECEIVE_BUF_MAX_CAPACITY]), rxbuf_index: 0, txbuf: Box::new([0u8; RECEIVE_BUF_MAX_CAPACITY]), state: Handshaking { remote_key } }
  }

  /// this function generates a new public/private keypair and returns it
  pub fn generate_keypair() -> (PublicKey, SecretKey) {
    let key = snow::Builder::new(PARAMS.parse().unwrap()).generate_keypair().unwrap();
    (key.public, key.private)
  }
}

use core::future::Future;
use std::pin::Pin;
use std::sync::Arc;

/// gets a PublicKey and should output Some(value) if the key is ok and None if it's not
pub type PeerVerifier<T> = Arc<dyn for<'a> Fn(&'a [u8]) -> Pin<Box<dyn Future<Output = Option<T>> + 'a + Send>> + Send + Sync>;

#[async_trait]
pub trait ChannelState {}
#[async_trait]
impl ChannelState for Handshaking {}
impl NoiseChannel<Handshaking> {
  /// Performs the NOISE handshake with the remote peer
  /// `verify_peer`: verifies that the public key of the remote peer is ok. If verification is successful, this shall
  /// return Some value, which is later returned besides the actual transport channel.
  /// If verification does NOT succeed this function shall return None.
  pub async fn handshake<T>(mut self, ownkey: &SecretKey, verify_peer: PeerVerifier<T>) -> Result<(T, NoiseChannel<Transporting>), Box<dyn Error>> {
    #[rustfmt::skip]
    let builder = snow::Builder::new(PARAMS.parse()?).prologue(PARAMS.as_bytes()).local_private_key(&ownkey);
    #[rustfmt::skip]
    let mut handshake = if self.state.remote_key.is_some() {
      debug!("{} is initiator, remote pubkey {}", hex::encode(&ownkey[..3]), hex::encode(&self.state.remote_key.clone().unwrap()));
      builder.remote_public_key(&self.state.remote_key.as_ref().unwrap()).build_initiator()?
    } else {
      debug!("{} is responder", hex::encode(&ownkey[..3]));
      builder.build_responder()?
    };

    while !handshake.is_handshake_finished() {
      if handshake.is_my_turn() {
        // Send Handshake message
        #[rustfmt::skip] // don't split up chain when formatting code
        let num_bytes: usize = handshake.write_message(&[], &mut *self.txbuf).expect("No payload, so it never fails");

        trace!("{} sending payload: {}", hex::encode(&ownkey[..3]), hex::encode(&self.txbuf[..num_bytes]));
        self.write_pkt(NoisePacket::new(&self.txbuf[..num_bytes])?).await?;
      } else {
        trace!("{} receiving", hex::encode(&ownkey[..3]));
        // Receive Handshake message
        let pkt = self.read_pkt().await?;
        let temp = pkt.get_payload();
        #[rustfmt::skip]
        trace!("{} received payload {} of len {}",hex::encode(&ownkey[..3]),hex::encode(&temp), &temp.len());

        let size_additional_data = handshake.read_message(&temp, &mut *self.rxbuf)?;
        assert_eq!(size_additional_data, 0); // we are not sending any user payload during the handshake
      }
    }
    // the initiator already authenticated the responder, but check with our peer map nevertheless
    let remote_key = match handshake.get_remote_static() {
      Some(key) => key,
      None => panic!("Expected to know the pubkey now!"),
    };

    let verify_result = verify_peer.clone()(remote_key).await;
    let pubkey_accepted: bool = verify_result.is_some();

    if !pubkey_accepted {
      panic!("Could not verify public key {}", hex::encode(&remote_key));
    }

    let transport = handshake.into_transport_mode()?;
    Ok((verify_result.unwrap(), NoiseChannel { stream: self.stream, rxbuf: self.rxbuf, rxbuf_index: self.rxbuf_index, txbuf: self.txbuf, state: Transporting { noise_session: transport } }))
  }
}
#[async_trait]
impl ChannelState for Transporting {}

impl NoiseChannel<Transporting> {
  /// Reads a message. The maximum size is limited by NOISE. A single message sent with "write(msg)" is guaranteed to be
  /// received as a single message via "let msg = read()", as long as it fits in one Noise message.
  pub async fn read(&mut self) -> Result<&[u8], Box<dyn Error>> {
    let pkt = self.read_pkt().await?;
    let len = self.state.noise_session.read_message(&pkt.get_payload(), &mut *self.rxbuf)?;
    trace!("Read noise '{}'", String::from_utf8_lossy(&self.rxbuf[..len]));
    Ok(&self.rxbuf[..len])
  }

  /// Receives and decrypts a message into the provided buffer, returning the length of the written data
  pub async fn read_into(&mut self, buf: &mut [u8]) -> Result<usize, Box<dyn Error + Send + Sync>> {
    let pkt = self.read_pkt().await?;
    let len = self.state.noise_session.read_message(&pkt.get_payload(), buf)?;
    trace!("Read noise '{}'", String::from_utf8_lossy(&buf[..len]));
    Ok(len)
  }

  /// There was a very weird compiler error with calling node::transport_on_channel() in spawned tasks:
  /// the trait `std::marker::Send` is not implemented for `dyn StdError`
  /// in a tokio::select! with more than 2 branches: await occurs here, with `mut output` maybe used later
  /// using only 2 branches in the select! was ok...
  /// Don't know where this `mut output` comes from (doesn't appear in my codebase) but the error only occurs if the
  /// async expression in a select! branch contains the "Error" type, which apparently might live beyond an await in the
  /// select! branch's handler
  /// Maybe related: https://github.com/rust-lang/rust/issues/57017
  /// So just print the error and drop it.
  pub async fn read_option(&mut self) -> Option<&[u8]> {
    let res = self.read().await;
    if res.is_err() {
      warn!("Error reading from secure channel: {}", res.unwrap_err());
      None
    } else {
      Some(res.unwrap())
    }
  }

  /// Get the current nonce value. Only for Debugging
  pub fn sending_nonce(&self) -> u64 {
    self.state.noise_session.sending_nonce()
  }
  pub fn receiving_nonce(&self) -> u64 {
    self.state.noise_session.receiving_nonce()
  }

  /// Writes a message and completes when all data has been written
  /// Fragmnts the data if necessary
  pub async fn write(&mut self, msg: &[u8]) -> std::io::Result<()> {
    let mut written_so_far = 0;

    trace!("Noise sending {} bytes", msg.len());

    while written_so_far != msg.len() {
      let chunksize = if msg.len() - written_so_far > MAX_PAYLOAD_SIZE { MAX_PAYLOAD_SIZE } else { msg.len() - written_so_far };

      let len = self.state.noise_session.write_message(&msg[written_so_far..written_so_far + chunksize], &mut *self.txbuf).expect("Message fragmentation is buggy!");
      let pkt = NoisePacket::new(&self.txbuf[..len]).expect("Payload too big (not appropriately fragmented)!");
      trace!("Write noise '{}'", String::from_utf8_lossy(&msg));
      self.write_pkt(pkt).await?;
      written_so_far += chunksize;
    }
    Ok(())
  }
}

#[cfg(test)]
pub(crate) mod tests {
  use super::*;
  use crate::node::common::ID;
  use lazy_static::lazy_static;
  // MINOR: finally figure out how to switch the RNG for the tests
  //  use snow::resolvers::{CryptoResolver, DefaultResolver};
  //  use snow::{
  //    params::{CipherChoice, DHChoice, HashChoice},
  //    types::{Cipher, Dh, Hash, Random},
  //  };
  use crate::util;
  use tokio::net::TcpListener;

  lazy_static! {
    pub static ref RESPONDER_SECRET: Vec<u8> = hex::decode("0ebbcc80f25ebcf3c9b6833ced9f2be673da5bd5fee1c6d1d4608373caf9d27a").unwrap();
    pub static ref RESPONDER_PUBLIC: Vec<u8> = hex::decode("48b0c6509029efd5822baf6cac8ad4df38bbab92cf19344b24b0125ab69a7f40").unwrap();
    pub static ref INITIATOR_SECRET: Vec<u8> = hex::decode("8312ab48a22492d7ec6f74e8d621e58db295741cd3e507ad5cab036b2e6f6f5f").unwrap();
    pub static ref INITIATOR_PUBLIC: Vec<u8> = hex::decode("0f9896bb7daa3451f248a0cc3b4774b121c70251f3108dfc6dda9d594071ba5e").unwrap();
  }
  const UNUSED_ID: ID = 17;

  // async closures are not yet supported, so do the check in a separate function
  // TODO refactor to remove UNUSED_ID
  async fn is_initiator(remote_key: &[u8]) -> Option<ID> {
    if INITIATOR_PUBLIC.clone() == remote_key {
      Some(UNUSED_ID)
    } else {
      None
    }
  }
  async fn is_responder(remote_key: &[u8]) -> Option<ID> {
    if RESPONDER_PUBLIC.clone() == remote_key {
      Some(UNUSED_ID)
    } else {
      None
    }
  }

  pub async fn responder_handshake(addr: &str) -> Result<NoiseChannel<Transporting>, Box<dyn Error>> {
    let listener = TcpListener::bind(addr).await.expect("Could not bind to address");
    let (stream, _) = listener.accept().await.unwrap();
    let channel = NoiseChannel::<Handshaking>::new(None, stream);
    // type annotation due to compiler quirk: expected type `FnOnce<(&Vec<u8>,)>` found type `FnOnce<(&Vec<u8>,)>`
    //let is_initiator_check = ;
    match channel.handshake(&RESPONDER_SECRET, Arc::new(move |remote_key: &[u8]| Box::pin(is_initiator(remote_key)))).await {
      Ok((id, chan)) => {
        assert_eq!(id, UNUSED_ID);
        Ok(chan)
      }
      Err(err) => Err(err),
    }
  }

  pub async fn initiator_handshake(addr: &str) -> Result<NoiseChannel<Transporting>, Box<dyn Error>> {
    let stream = util::tcp::connect(&addr).await?;
    let channel = NoiseChannel::<Handshaking>::new(Some(RESPONDER_PUBLIC.clone()), stream);

    match channel.handshake(&INITIATOR_SECRET, Arc::new(move |remote_key: &[u8]| Box::pin(is_responder(remote_key)))).await {
      Ok((id, chan)) => {
        assert_eq!(id, UNUSED_ID);
        Ok(chan)
      }
      Err(err) => Err(err),
    }
  }

  // https://docs.rs/tokio/1.5.0/tokio/io/struct.DuplexStream.html
  #[tokio::test]
  async fn keygen_before_handshake() {
    //  let (responder_public, responder_secret) = NoiseChannel::generate_keypair();
    //  let (initiator_public, initiator_secret) = NoiseChannel::generate_keypair();
    // for separation, use different IP as the other tests
    let resp = tokio::spawn(async move {
      let res = responder_handshake("localhost:3100").await;
      assert!(res.is_ok());
    });

    let init = tokio::spawn(async move {
      let res = initiator_handshake("localhost:3100").await;
      assert!(res.is_ok());
    });
    let (a, b) = tokio::join!(resp, init);
    assert!(a.is_ok());
    assert!(b.is_ok());
  }

  #[tokio::test]
  async fn protected_message_transmission() {
    let resp_session_hdl = tokio::spawn(async move {
      let mut session = {
        // have use other port because tests are run in parallel by default
        let res = responder_handshake("localhost:3101").await;
        assert!(res.is_ok());
        res.unwrap()
      };
      {
        let res = session.write(b"foobar").await;
        assert!(res.is_ok());
      }
      {
        let res = session.read().await;
        println!("{:?}", res);
        assert!(res.is_ok());
        let buf = res.unwrap();
        assert_eq!(buf, b"this is init sending");
      }
      {
        let res = session.write(b"msgthree").await;
        assert!(res.is_ok());
      }
      {
        let res = session.write(b"lastmessage").await;
        assert!(res.is_ok());
      }
    });

    let init_session_hdl = tokio::spawn(async move {
      let mut session = {
        let res = initiator_handshake("localhost:3101").await;
        assert!(res.is_ok());
        res.unwrap()
      };
      {
        let res = session.write(b"this is init sending").await;
        assert!(res.is_ok());
      }
      {
        let buf_res = session.read().await;
        assert!(buf_res.is_ok());
        assert_eq!(buf_res.unwrap(), b"foobar");
      }
      {
        let buf_res = session.read().await;
        assert!(buf_res.is_ok());
        assert_eq!(buf_res.unwrap(), b"msgthree");
      }
      {
        let buf_res = session.read().await;
        assert!(buf_res.is_ok());
        assert_eq!(buf_res.unwrap(), b"lastmessage");
      }
    });

    let (a, b) = tokio::join!(resp_session_hdl, init_session_hdl);
    assert!(a.is_ok());
    assert!(b.is_ok());
  }
}
