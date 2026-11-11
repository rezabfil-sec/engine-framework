use std::error::Error;
use std::result::Result;
use std::sync::Arc;

use tracing::{debug, info, warn}; // trace error

use crate::channel::message::P2PMessage;
use crate::noise::{self, NoiseChannel, Transporting};
use crate::transport::noise::*;
use crate::transport::{PublicKey, SecretKey};
use crate::util;
use crate::util::logging::debug_msg_string;

pub mod message;

/// Transport channel for `P2PMessage`s, using an underlying Noide channel for confidential and authenticated transport
#[derive(Debug)]
pub struct P2PChannel {
  transport: NoiseChannel<Transporting>,
  /// receive buffer. can't use a BytesMut here because snow requires a &mut [u8]
  buf: Vec<u8>,
  /// cursor
  end_in_buf: usize,
}

impl P2PChannel {
  /// A protected P2P channel. Pre-allocates a payload buffer big enough for not fragmented P2P messages.
  pub fn new(transport: NoiseChannel<Transporting>) -> Self {
    Self { transport, buf: vec![0; noise::MAX_SIZE_MSG], end_in_buf: 0 }
  }

  async fn are_pubkeys_equal(a: &[u8], b: PublicKey) -> Option<()> {
    if b == a {
      Some(())
    } else {
      None
    }
  }

  /// create a P2PChannel to a specific address
  pub async fn connect_to(own_seckey: &SecretKey, addr: &str, remote_pubkey: &PublicKey) -> Result<P2PChannel, Box<dyn Error>> {
    let stream = util::tcp::connect(&addr).await?;
    info!("Connected to {}", &addr);
    let good_remote_pubkey = remote_pubkey.clone();
    let channel_hs = NoiseChannel::<Handshaking>::new(Some(remote_pubkey.to_vec()), stream);

    let verify_peer: PeerVerifier<()> = Arc::new(move |remote_key_to_verify| {
      let good_remote_pubkey = good_remote_pubkey.clone();
      Box::pin(Self::are_pubkeys_equal(&remote_key_to_verify, good_remote_pubkey))
    });

    let res = channel_hs.handshake::<()>(own_seckey, verify_peer).await;

    if let Ok((_, chan)) = res {
      info!("Completed handshake to {}", &addr);
      return Ok(P2PChannel::new(chan));
    } else {
      let err = res.unwrap_err();
      warn!("P2P Handshake error: {}", err);
      return Err(err);
    }
  }

  /// Read exactly one P2P message
  /// This future may be dropped and restarted later again (Note: this is also required for all futures called here)
  pub async fn read_msg(&mut self) -> Result<P2PMessage, Box<dyn Error + Send + Sync>> {
    let msg = loop {
      if self.buf.len() - self.end_in_buf < noise::MAX_SIZE_MSG {
        debug!("Resizing buf from {} to {}", self.buf.len(), self.end_in_buf + noise::MAX_SIZE_MSG);
        self.buf.resize(self.end_in_buf + noise::MAX_SIZE_MSG, 0);
      }

      let len = self.transport.read_into(&mut self.buf[self.end_in_buf..]).await?;
      self.end_in_buf += len;

      let parse_result = { P2PMessage::parse(&self.buf[..self.end_in_buf]) };
      match parse_result {
        Err(nom::Err::Incomplete(_needed)) => {
          // noise layer already guarantees that we get not more than needed
        }
        Ok(parsed_msg) => {
          self.end_in_buf = 0;
          assert_eq!(parsed_msg.0.len(), 0); // no remaining unparsed bytes
          break Ok(parsed_msg.1);
        }
        _ => {
          panic!("Error parsing msg from secure channel: {}", parse_result.unwrap_err());
        }
      }
    };
    self.buf.clear();
    msg
  }

  pub async fn write_msg(&mut self, msg: &P2PMessage) -> std::io::Result<()> {
    let serialized = msg.to_bytes();
    if let Ok(bytes) = serialized {
      self.transport.write(&bytes).await?
    } else {
      let e = serialized.unwrap_err();
      panic!("Couldn't serialize msg '{}': {} ", debug_msg_string(&msg), &e);
    }
    Ok(())
  }
}

#[cfg(test)]
mod tests {
  use super::*;
  use std::time::Duration;

  use crate::channel::message::{NonceCommitmentList, P2PControlMsg, P2PDataMsg, PreprocessInit};
  use crate::noise::tests::{initiator_handshake, responder_handshake, INITIATOR_SECRET, RESPONDER_PUBLIC};
  use crate::util::logging;
  use curve25519_dalek::ristretto::RistrettoPoint;
  use rand::distributions::{Distribution, Uniform};
  use rand::rngs::OsRng;
  use rand::rngs::SmallRng;
  use rand::SeedableRng;
  use tokio::sync::mpsc;
  use tokio::time;

  #[tokio::test]
  async fn transport() {
    logging::init();
    // for separation, use different IP as the other tests
    let resp = tokio::spawn(async move {
      let transport = {
        let res = responder_handshake("localhost:42100").await;
        assert!(res.is_ok());
        res.unwrap()
      };

      let mut chan = P2PChannel::new(transport);

      let m = PreprocessInit { number_of_commitments: 42 };
      let res = chan.write_msg(&m.into()).await;
      assert!(res.is_ok());
    });

    let init = tokio::spawn(async move {
      let transport = {
        let res = initiator_handshake("localhost:42100").await;
        assert!(res.is_ok());
        res.unwrap()
      };

      let mut chan = P2PChannel::new(transport);
      let res = chan.read_msg().await;
      match res.unwrap() {
        P2PMessage::Control(m) => match m {
          P2PControlMsg::PreprocessInit(m) => assert_eq!(m.number_of_commitments, 42),
          _ => assert!(false),
        },
        _ => assert!(false),
      }
    });
    let (a, b) = tokio::join!(resp, init);
    assert!(a.is_ok());
    assert!(b.is_ok());
  }

  #[tokio::test]
  async fn transport_fragmented() {
    logging::init();
    // for separation, use different IP as the other tests
    let resp = tokio::spawn(async move {
      let transport = {
        let res = responder_handshake("localhost:42101").await;
        assert!(res.is_ok());
        res.unwrap()
      };

      let mut chan = P2PChannel::new(transport);
      let gen_point = || RistrettoPoint::random(&mut OsRng);
      let p: Vec<(RistrettoPoint, RistrettoPoint)> = (0..2000).map(|_i| (gen_point(), gen_point())).collect();

      let m = NonceCommitmentList { commitments: p };
      let res = chan.write_msg(&m.into()).await;
      assert!(res.is_ok());
    });

    let init = tokio::spawn(async move {
      let transport = {
        let res = initiator_handshake("localhost:42101").await;
        assert!(res.is_ok());
        res.unwrap()
      };

      let mut chan = P2PChannel::new(transport);
      let res = chan.read_msg().await;
      match res.unwrap() {
        P2PMessage::Data(m) => match m {
          P2PDataMsg::NonceCommitmentList(m) => assert_eq!(m.commitments.len(), 2000),
          _ => assert!(false),
        },
        _ => assert!(false),
      }
    });
    let (a, b) = tokio::join!(resp, init);
    assert!(a.is_ok());
    assert!(b.is_ok());
  }

  /// produces stuff to send and places it in the send queue
  async fn enqueue_messages(seed: u64, num_messages: usize, msg_queue_in: mpsc::Sender<P2PMessage>) {
    let mut prng = SmallRng::seed_from_u64(seed);
    let len_vector_range = Uniform::from(10..1000);
    let data = [0u8; 64];
    let somepoint = RistrettoPoint::from_uniform_bytes(&data);
    let gen_point = || somepoint.clone();

    for _i in 0..num_messages {
      let len = len_vector_range.sample(&mut prng);
      let p: Vec<(RistrettoPoint, RistrettoPoint)> = (0..len).map(|_i| (gen_point(), gen_point())).collect();
      // TODO investigate interesting bug: PRNG state affected by assertion
      // printing the length shows the right length, but on the receiver side the PRNG would require a DIFFERENT length
      // (= would have a different state with the same seed).
      // BUT when asserting the correct length here, the receiver's PRNG comes up with the correct length. WTF?
      // This was consistent over a clean rebuild...
      // Maybe some loop optimization gone wrong?
      assert_eq!(p.len(), len);
      //println!("len: {}", p.len());
      let m = NonceCommitmentList { commitments: p };

      if let Err(_) = msg_queue_in.send(m.into()).await {
        eprintln!("receiver part of send queue dropped");
        return;
      }
    }
  }

  /// actually sends messages from the send queue and receives messages from the peer channel
  async fn recv_and_check_messages(seed: u64, num_messages: usize, mut msg_queue_out: mpsc::Receiver<P2PMessage>, mut channel: P2PChannel, rx: bool, tx: bool) {
    let mut prng = SmallRng::seed_from_u64(seed);
    let len_vector_range = Uniform::from(10..1000);

    let mut num_received = 0;
    let mut num_sent = 0;
    let mut interval = time::interval(Duration::from_micros(30));

    let data = [0u8; 64];
    let somepoint = RistrettoPoint::from_uniform_bytes(&data);

    loop {
      tokio::select! {
        result = channel.read_msg() => {
          if rx {
            num_received += 1;
            let expected_len = len_vector_range.sample(&mut prng);
            match result.unwrap() {
              P2PMessage::Data(m) => match m {
                P2PDataMsg::NonceCommitmentList(m) => {
                  assert_eq!(m.commitments.len(), expected_len);
                  for (a, b) in m.commitments {
                    assert_eq!(a, somepoint);
                    assert_eq!(b, somepoint);
                  }
                },
                _ => assert!(false),
              },
            _ => assert!(false),
            }
          }
        },
        _ = interval.tick() => {}, // interrupt read_msg() to find bugs there
        Some(msg) = msg_queue_out.recv() => {
          if tx{
            num_sent += 1;
            channel.write_msg(&msg).await.unwrap(); // unwrap better than assert because it also prints the error
          }
        },
      }
      if (num_received == num_messages || !rx) & (num_sent == num_messages || !tx) {
        return;
      }
    }
  }

  /// This was used to find a race condition during Noise message reception where the receiver future was dropped in a
  /// tokio::select! and thus left an inconsitent state when invoked again. This only occurs for the "correctly"
  /// interleaving indirect calls to NoiseChannel::read_pkt() via P2PChannel::read_msg() and therefore not always
  #[tokio::test(flavor = "multi_thread", worker_threads = 4)]
  async fn protected_p2p_channel() {
    logging::init();
    let num_messages: usize = 100;

    let responder_tx_seed: u64 = 1;
    let initiator_tx_seed: u64 = 3;

    // for separation, use different IP as the other tests
    let resp = tokio::spawn(async move {
      let transport = {
        let res = responder_handshake("localhost:42102").await;
        assert!(res.is_ok());
        res.unwrap()
      };
      let chan = P2PChannel::new(transport);

      // queue of arbitrary size
      let (sender, receiver): (mpsc::Sender<P2PMessage>, mpsc::Receiver<P2PMessage>) = mpsc::channel(42);
      let producer = tokio::spawn(async move {
        enqueue_messages(responder_tx_seed, num_messages, sender).await;
      });
      let consumer = tokio::spawn(async move {
        recv_and_check_messages(initiator_tx_seed, num_messages, receiver, chan, true, true).await;
      });

      let (a, b) = tokio::join!(producer, consumer);
      assert!(a.is_ok());
      assert!(b.is_ok());
    });

    let init = tokio::spawn(async move {
      let chan = P2PChannel::connect_to(&INITIATOR_SECRET, "localhost:42102", &RESPONDER_PUBLIC).await.expect("channel err");

      let (sender, receiver): (mpsc::Sender<P2PMessage>, mpsc::Receiver<P2PMessage>) = mpsc::channel(42);
      let producer = tokio::spawn(async move {
        enqueue_messages(initiator_tx_seed, num_messages, sender).await;
      });
      let consumer = tokio::spawn(async move {
        recv_and_check_messages(responder_tx_seed, num_messages, receiver, chan, true, true).await;
      });

      let (a, b) = tokio::join!(producer, consumer);
      assert!(a.is_ok());
      assert!(b.is_ok());
    });

    let (a, b) = tokio::join!(resp, init);
    assert!(a.is_ok());
    assert!(b.is_ok());
  }
}
