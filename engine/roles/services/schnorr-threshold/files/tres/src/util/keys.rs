use std::error::Error;
use std::fs;
use std::fs::File;
use std::io::Read;
use std::path::Path;

use frost_dalek::keygen::GroupKey;

pub fn write_group_key(path: &Path, pubkey: GroupKey) -> Result<(), Box<dyn Error>> {
  fs::write(&path, pubkey.to_bytes())?;
  Ok(())
}

pub fn read_group_key(path: &Path) -> Result<GroupKey, Box<dyn Error>> {
  let mut data: [u8; 32] = [0; 32];
  let mut file = File::open(path)?;
  file.read_exact(&mut data)?;

  match GroupKey::from_bytes(data) {
    Ok(gk) => Ok(gk),
    Err(err) => panic!("Bad public key: {:?}", err),
  }
}
