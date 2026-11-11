use std::convert::TryInto;
use std::fmt;
use std::io::{Cursor, ErrorKind, Read};
use std::vec;

use byteorder::{NetworkEndian, ReadBytesExt, WriteBytesExt};

///  the size of the length field: number of bytes per u16
pub(crate) const SIZE_LEN_FIELD: usize = core::mem::size_of::<u16>();

#[derive(Debug, PartialEq, Clone)]
pub struct NoisePacket {
  /// the length of the following data (in bytes)
  /// not a field in this struct but part of the packet
  // len: u16,
  /// (encrypted and authenticated) payload, which is a message in the NOISE protocol
  payload: Vec<u8>,
}

#[derive(Debug)]
pub enum ConversionError {
  NeedMoreData { num_bytes: usize },
  PayloadTooLong,
}
impl fmt::Display for ConversionError {
  fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
    match *self {
      ConversionError::NeedMoreData { num_bytes } => write!(f, "Need at least {} more bytes to parse", num_bytes),
      ConversionError::PayloadTooLong => write!(f, "Payload must fit into 65535 bytes!"),
    }
  }
}
impl std::error::Error for ConversionError {
  fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
    None
  }
}

impl NoisePacket {
  pub fn new(payload: &[u8]) -> Result<Self, ConversionError> {
    let len: u16 = payload.len() as u16;

    if usize::from(len) != payload.len() {
      return Err(ConversionError::PayloadTooLong);
    }
    Ok(NoisePacket { payload: payload.to_vec() })
  }

  pub fn get_payload(&self) -> &Vec<u8> {
    &self.payload
  }

  /// Parse the data into a packet, also return number of consumed bytes
  pub fn parse(data: &[u8]) -> Result<(NoisePacket, usize), ConversionError> {
    let mut reader = Cursor::new(&data); // Cursor provides a Seek-able view
    let len_result = reader.read_u16::<NetworkEndian>();
    if len_result.is_err() {
      assert_eq!(len_result.unwrap_err().kind(), ErrorKind::UnexpectedEof);
      if data.len() == 0 {
        return Err(ConversionError::NeedMoreData { num_bytes: SIZE_LEN_FIELD });
      } else {
        assert_eq!(data.len(), 1);
        return Err(ConversionError::NeedMoreData { num_bytes: 1 });
      }
    }
    let len = usize::from(len_result.unwrap());
    if data.len() >= len + SIZE_LEN_FIELD {
      // if data.len() > len + SIZE_LEN_FIELD {
      //   debug!("Got more data {} than needed: {}", data.len(), len + SIZE_LEN_FIELD);
      // }

      let mut payload = vec![0; len];
      reader.read_exact(&mut payload).expect("never panics");

      return Ok((NoisePacket { payload }, len + SIZE_LEN_FIELD));
    }

    assert!((data.len() as isize) < (len + SIZE_LEN_FIELD) as isize);
    let bytes_needed = (((len + SIZE_LEN_FIELD) as isize) - (data.len() as isize)) as usize;
    Err(ConversionError::NeedMoreData { num_bytes: bytes_needed })
  }

  pub fn to_bytes(mut self) -> Vec<u8> {
    let mut data = Vec::with_capacity(SIZE_LEN_FIELD + self.payload.len());
    data.write_u16::<NetworkEndian>(self.payload.len().try_into().expect("Bug!")).unwrap();
    data.append(&mut self.payload);
    data
  }
}

#[cfg(test)]
mod tests {
  use super::*;
  #[test]
  fn parse() {
    let len = 256; // equals to BE 0x01 0x00
    let mut data = vec![0x01, 0x00]; // length (and payload) as bytes
    let payload: Vec<u8> = vec![42; len];
    data.append(&mut payload.clone());

    assert_eq!(data.len(), SIZE_LEN_FIELD + len);

    let (pkt, num_consumed_bytes) = NoisePacket::parse(&data).expect("No error should occur!");

    assert_eq!(num_consumed_bytes, SIZE_LEN_FIELD + len);
    assert_eq!(pkt.payload.len(), len);
    assert_eq!(pkt.get_payload(), &pkt.payload);
    assert_eq!(pkt.get_payload(), &payload);
  }

  #[test]
  fn to_bytes() {
    let len = 258; // equals to BE 0x01 0x02
    let payload: Vec<u8> = vec![42; len];

    let mut serialized_good = vec![0x01, 0x02];
    serialized_good.append(&mut payload.clone());

    let pkt = NoisePacket::new(&payload).expect("No error should occur!");
    assert_eq!(pkt.to_bytes(), serialized_good);
  }

  #[test]
  fn to_bytes_then_parse_is_identity() {
    let len = 258;
    let payload: Vec<u8> = vec![42; len];
    let pkt = NoisePacket::new(&payload).expect("No error should occur!");
    let pkt_clone = pkt.clone();

    let mut serialized = pkt.to_bytes();
    // possible garbage at the end should be ignored during parsing
    let len_garbage = 47;
    let garbage: Vec<u8> = vec![123; len_garbage];
    serialized.append(&mut garbage.clone());

    let (pkt_parsed, num_consumed_bytes) = NoisePacket::parse(&serialized).expect("No error should occur!");

    assert_eq!(num_consumed_bytes, SIZE_LEN_FIELD + len);
    assert_eq!(serialized.len(), SIZE_LEN_FIELD + len + len_garbage);
    assert_eq!(serialized[num_consumed_bytes..], garbage);
    assert_eq!(pkt_parsed, pkt_clone);
  }

  fn assert_need_more_data_err(result: Result<(NoisePacket, usize), ConversionError>, num_bytes_expected: usize) {
    if let Err(ConversionError::NeedMoreData { num_bytes }) = result {
      assert_eq!(num_bytes, num_bytes_expected);
    } else {
      assert!(false);
    }
  }

  #[test]
  fn parse_chunks() {
    let len = 16; // equals to BE 0x00 0x10
    let payload: Vec<u8> = vec![42; len];

    let mut serialized = vec![0x00, 0x10];
    serialized.append(&mut payload.clone());

    // possible garbage at the end should be ignored during parsing
    let len_garbage = 47;
    let garbage: Vec<u8> = vec![123; len_garbage];
    serialized.append(&mut garbage.clone());

    assert_need_more_data_err(NoisePacket::parse(&serialized[..1]), 1); // length field is 2 B
    assert_need_more_data_err(NoisePacket::parse(&serialized[..2]), len); // expect length
    assert_need_more_data_err(NoisePacket::parse(&serialized[..2 + 3]), len - 3); // expect length
    assert_need_more_data_err(NoisePacket::parse(&serialized[..2 + len - 1]), 1);
  }
}
