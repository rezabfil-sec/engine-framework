use std::error::Error;
use std::net::SocketAddr;
use tokio::net;

/// resolves the host part of the given address "hostpart:42" and returns the corresponding address "ip:42"
pub async fn resolve(addr: &str) -> Result<SocketAddr, Box<dyn Error>> {
  let soaddr = net::lookup_host(addr).await?.next();
  if soaddr.is_none() {
    return Err(format!("Failed to look up host in addr '{}'!", addr).into());
  }
  Ok(soaddr.unwrap())
}
