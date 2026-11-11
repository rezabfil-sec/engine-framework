use std::collections::HashMap;
use std::fmt;

#[derive(Debug)]
pub enum ValueError {
  Inconsistent { msg: &'static str },
}
impl fmt::Display for ValueError {
  fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
    match *self {
      ValueError::Inconsistent { msg } => write!(f, "Inconsistent value(s): {}", msg),
    }
  }
}
impl std::error::Error for ValueError {
  fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
    match *self {
      _ => None,
    }
  }
}

/// Error type for communicating the result of the asynchronous signing operation via tokio's channel
/// TODO messy: mixes client feedback with internal error passing
#[derive(Debug)]
pub enum ThresholdSigningError {
  /// No signing operation was initiated
  NoneInitiated,
  /// missing private threshold signing key
  NoKeys,
  /// No more secret nonces (or commitments to them) available
  NoNonces,
  /// message not acceptable
  RejectedMsg(String),
  /// report faults of aggregator
  AggregatorError(HashMap<u32, &'static str>),
  /// report misbehaviour for each client
  AggregationError(HashMap<u32, &'static str>),
}
impl fmt::Display for ThresholdSigningError {
  fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
    match &*self {
      ThresholdSigningError::NoneInitiated => write!(f, "No signing operation was initiated, thus no signature here."),
      ThresholdSigningError::NoKeys => write!(f, "No threshold signing keys available!"),
      ThresholdSigningError::NoNonces => write!(f, "Don't have any nonces - do preprocessing first!"),
      ThresholdSigningError::RejectedMsg(msg) => write!(f, "Rejected this message for signing. Reason: {}", msg),
      ThresholdSigningError::AggregatorError(map) => write!(f, "Aggregator failed: {:?}", map),
      ThresholdSigningError::AggregationError(map) => write!(f, "Failed to aggregate shares: {:?}", map),
    }
  }
}
impl std::error::Error for ThresholdSigningError {
  fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
    match *self {
      _ => None,
    }
  }
}
