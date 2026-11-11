use std::convert::TryInto;
use std::error::Error;
use std::fmt;

use bytes::Bytes;
use futures::future;
use hyper::body::HttpBody;
use hyper::client::conn;
use hyper::http::Uri;
use hyper::{Body, Method, Response, StatusCode};
use serde_qs;
use tokio::io::ErrorKind;
use tokio::net::TcpStream;
use tokio::sync::Mutex;
use tracing::debug; // info trace warn error

use frost_dalek::keygen::GroupKey;
use frost_dalek::signature::ThresholdSignature;

use crate::channel::message::*;
use crate::node::common::*;
use crate::util;
pub mod message;

#[derive(Debug)]
pub enum RequestError {
  HTTP(StatusCode, String, Bytes),
}
impl fmt::Display for RequestError {
  fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
    match &*self {
      RequestError::HTTP(status, query, body) => write!(f, "HTTP error: {}: {} {:?}", status, query, body),
    }
  }
}
impl std::error::Error for RequestError {
  fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
    None
  }
}

/// A client (in the outside world) which interacts with the distributed system via an HTTP interface
pub struct Client {
  /// channel to send requests on
  channel: Mutex<conn::SendRequest<Body>>,
  /// to host to use in HTTP header
  host: String,
  /// if false, work such as setting up a connection/clearing internal buffers might be done before an actual request
  allow_precise_measurements: bool,
}

impl Client {
  pub async fn new<S: Into<String>>(addr: S) -> Result<Self, Box<dyn Error>> {
    // not using the higher-level APIs from hyper/tower so that we can easily switch to/between TLS, Noise, ...
    let addr = &addr.into();

    let stream_result = util::tcp::connect(&addr).await;
    let stream = stream_result.unwrap(); // panic if we don't have a connection
    let (request_sender, connection) = conn::Builder::new().handshake::<TcpStream, Body>(stream).await?;

    tokio::spawn(async move {
      // tell us as soon as there are errors
      if let Err(e) = connection.await {
        eprintln!("Error in HTTP connection: {}", e);
      }
    });

    let uri = Uri::builder().authority(&addr[..]).build()?;
    let host = uri.host(); // extract hostname
    if host.is_none() {
      return Err(Box::new(std::io::Error::new(ErrorKind::Other, "Bad hostname")));
    }

    Ok(Client { channel: Mutex::new(request_sender), host: host.unwrap().to_string(), allow_precise_measurements: false })
  }

  /// enable/disable more precise measurements
  pub fn allow_precise_measurements(&mut self, new_state: bool) {
    self.allow_precise_measurements = new_state;
  }

  /// Creates an HTTP Request builder with the appropriate HTTP headers already set
  fn new_request_builder(&self) -> hyper::http::request::Builder {
    hyper::Request::builder().header("Host", self.host.clone())
  }

  /// Wait till connection is ready for a request
  /// This is required by hyper and ensures that benchmarks don't measure local HTTP client artifacts
  pub async fn ready(&self) -> Result<(), hyper::Error> {
    let mut request_sender = self.channel.lock().await;
    // see last couple of lines in https://github.com/rust-lang/wg-async-foundations/pull/191/files/c6aed66e0ffa9712ceb252dd49a914efa7840d58
    future::poll_fn(|cx| request_sender.poll_ready(cx)).await?;
    Ok(())
  }

  /// Try to send the given request to the server.
  /// If `client.read().await` is not called beforehand, this may fail due to
  /// May not suceed because the local "connection is not ready" (error comming from hyper) TODO figure out what the problem is exactly
  pub async fn send_request<S: AsRef<str>>(&self, m: Method, pathqueryfragment_uri: S) -> Result<Response<Body>, Box<dyn Error>> {
    let mut query_new_storage: String;
    let query_ptr = if !pathqueryfragment_uri.as_ref().starts_with('/') {
      query_new_storage = String::with_capacity(pathqueryfragment_uri.as_ref().len() + 1);
      query_new_storage.push('/');
      query_new_storage.push_str(pathqueryfragment_uri.as_ref());
      &query_new_storage
    } else {
      pathqueryfragment_uri.as_ref()
    };
    debug!("Requesting {} {}", m, query_ptr);
    let request = self.new_request_builder().method(m).uri(query_ptr).body(Body::empty())?;
    if !self.allow_precise_measurements {
      self.ready().await.expect("HTTP connection error");
    }

    Ok(self.channel.lock().await.send_request(request).await?)
  }

  /// Sends a GET request to `pathqueryfragment_uri` and returns the result
  pub async fn get<S: AsRef<str>>(&self, pathqueryfragment_uri: S) -> Result<Response<Body>, Box<dyn Error>> {
    self.send_request(Method::GET, pathqueryfragment_uri).await
  }

  /// Sends a POST request to `pathqueryfragment_uri` and returns the result
  pub async fn post<S: AsRef<str>>(&self, pathqueryfragment_uri: S) -> Result<Response<Body>, Box<dyn Error>> {
    self.send_request(Method::POST, pathqueryfragment_uri).await
  }

  /// Obtains the number "n" of participants in the system
  pub async fn get_n(&self) -> Result<ID, Box<dyn Error>> {
    let query = "/n";
    let mut response = self.get(&query).await?;

    let body: &mut Body = response.body_mut();
    let body_data = body.data().await.unwrap_or_else(|| Ok(Bytes::from("<<Empty Body>>")))?;

    if !response.status().is_success() {
      return Err(Box::new(RequestError::HTTP(response.status(), query.to_string(), body_data)));
    }

    let msg: message::NumParticipantsMsg = serde_json::from_slice(&body_data[..])?;
    Ok(msg.n)
  }

  /// Start a new phase of distributed key generation
  pub async fn initiate_dkg(&self, t: &ID) -> Result<GroupKey, Box<dyn Error>> {
    let msg = DkgInit { t: *t };
    let mut query = serde_qs::to_string(&msg)?;
    query.insert_str(0, "/dkg?");
    let mut response = self.post(&query).await?;

    let body: &mut Body = response.body_mut();
    debug!("DKG: waiting for response...");
    let body_data = body.data().await.unwrap_or_else(|| Ok(Bytes::from("<<Empty Body>>")))?;

    if !response.status().is_success() {
      return Err(Box::new(RequestError::HTTP(response.status(), query, body_data)));
    }

    let group_key: message::GroupKeyMsg = serde_json::from_slice(&body_data[..])?;
    let group_key: GroupKey = group_key.try_into().unwrap();
    Ok(group_key)
  }
  /// Start preprocessing: generate and publish a number of nonces to alolow single round signing later on
  pub async fn initiate_preprocessing(&self, number_of_commitments: usize) -> Result<(), Box<dyn Error>> {
    let msg = PreprocessInit { number_of_commitments };
    let mut query = serde_qs::to_string(&msg)?;
    query.insert_str(0, "/preprocess?");

    let mut response = self.post(&query).await?;
    if !response.status().is_success() {
      return Err(Box::new(RequestError::HTTP(response.status(), query, Bytes::from("<<Empty Body by default>>"))));
    }

    let body: &mut Body = response.body_mut();
    assert!(body.data().await.is_none()); // empty Body

    Ok(())
  }

  /// Start a new threshold signing phase to obtain a signature for a message
  pub async fn initiate_signing(&self, message: String) -> Result<ThresholdSignature, Box<dyn Error>> {
    let msg = message::SigningRequestMsg { msg: message };

    let mut query = serde_qs::to_string(&msg)?;
    query.insert_str(0, "/sign?");
    let mut response = self.post(&query).await?;

    let body: &mut Body = response.body_mut();
    let body_data = body.data().await.unwrap_or_else(|| Ok(Bytes::from("<<Empty Body>>")))?;

    if !response.status().is_success() {
      return Err(Box::new(RequestError::HTTP(response.status(), query, body_data)));
    }

    let parsed_signature: crate::client::message::ThresholdSignature = serde_json::from_slice(&body_data)?;
    let sig: ThresholdSignature = parsed_signature.into();
    Ok(sig)
  }

  /// Queries the currrent long-term public signature verification key
  pub async fn get_group_key(&self) -> Result<GroupKey, Box<dyn Error>> {
    let query = "group_key";
    let mut response = self.get(query).await?;

    let body: &mut Body = response.body_mut();
    let body_data = body.data().await.unwrap_or_else(|| Ok(Bytes::from("<<Empty Body>>")))?;

    if !response.status().is_success() {
      return Err(Box::new(RequestError::HTTP(response.status(), query.to_string(), body_data)));
    }

    let group_key: message::GroupKeyMsg = serde_json::from_slice(&body_data[..])?;
    let group_key: GroupKey = group_key.try_into().unwrap();
    Ok(group_key)
  }

  /// Completes when the contacted peer is fully connected and ready to serve requests
  pub async fn peer_fully_connected(&self) -> Result<(), Box<dyn Error>> {
    let query = "/fully_connected";
    let mut response = self.get(&query).await?;

    let body: &mut Body = response.body_mut();
    let body_data = body.data().await.unwrap_or_else(|| Ok(Bytes::from("<<Empty Body>>")))?;

    if !response.status().is_success() {
      return Err(Box::new(RequestError::HTTP(response.status(), query.to_string(), body_data)));
    }

    assert_eq!(&body_data[..], b"true");
    Ok(())
  }
}
