/// Checks that the message to be signed is indeed acceptable/this node is willing to sign it
pub trait MessageValidator {
  fn is_ok_to_sign(&self, message: &[u8]) -> bool;
}

/// Provides a default `MessageValidator` accepting all messages which start with "test"
pub struct TestMessageValidator {}

impl TestMessageValidator {
  pub fn new() -> Box<Self> {
    Box::new(TestMessageValidator {})
  }
}

impl MessageValidator for TestMessageValidator {
  fn is_ok_to_sign(&self, message: &[u8]) -> bool {
    message.starts_with(&b"test"[..])
  }
}
