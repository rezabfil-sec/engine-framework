use std::io;
use std::time::Duration;
use tokio::io::ErrorKind;
use tokio::net::{TcpStream, ToSocketAddrs};

pub async fn connect<A: ToSocketAddrs + std::fmt::Display>(addr: &A) -> io::Result<TcpStream> {
  let mut result = Err(std::io::Error::new(ErrorKind::Other, "Could not connect"));
  let num_retries = 8;

  for i in 1..num_retries {
    result = TcpStream::connect(&addr).await;
    if result.is_err() {
      tokio::time::sleep(Duration::from_millis(500 * u64::pow(2, i))).await; // give back control now
      eprintln!("Err connecting to {:#}: {}. Try {}/{}", &addr, (&result).as_ref().unwrap_err(), i, num_retries);
      if i == num_retries - 1 {
        eprintln!("Giving up connecting to {}!", &addr);
      }
    } else {
      break;
    }
  }
  result
}
