use std::net::SocketAddr;

use anyhow::Context;
use futures::{future::BoxFuture, FutureExt};

use tokio::{
    io::{AsyncReadExt, AsyncWriteExt, ReadHalf, WriteHalf},
    net::TcpStream,
    time::{sleep, Duration},
};

static ESTABLISH_CONNECTION_NUM_RETRIES: u8 = 5;

/// Read next message from socket.
pub async fn read_next_msg(socket_read: &mut ReadHalf<TcpStream>) -> Option<Vec<u8>> {
    // get msg length
    let mut msg_length_buf = vec![0; 4];
    let msg_length = match socket_read.read_exact(&mut msg_length_buf).await {
        Ok(_) => u32::from_le_bytes(msg_length_buf.try_into().unwrap()),
        Err(_) => {
            return None;
        }
    };
    // get msg
    let mut msg_buf = vec![0; msg_length as usize];
    match socket_read.read_exact(&mut msg_buf).await {
        Ok(_) => Some(msg_buf),
        Err(_) => None,
    }
}

/// Send message over socket.
pub async fn send_msg(socket_write: &mut WriteHalf<TcpStream>, msg: &Vec<u8>) {
    let msg_length = msg.len() as u32;
    socket_write.write(&msg_length.to_le_bytes()).await.unwrap();
    socket_write.write(msg).await.unwrap();
}

/// Connect to peer. Retry for ESTABLISH_CONNECTION_NUM_RETRIES if connection fails.
pub async fn connect_recursive(
    addr: SocketAddr,
) -> anyhow::Result<(ReadHalf<TcpStream>, WriteHalf<TcpStream>)> {
    pub fn get_retry_delay(num_retry: u8) -> Duration {
        Duration::from_secs(2 ^ num_retry as u64)
    }
    fn connect_recursive(
        addr: SocketAddr,
        num_retry: u8,
    ) -> BoxFuture<'static, anyhow::Result<TcpStream>> {
        // This is necessary due to rust not allowing recursive futures
        async move {
            if num_retry < ESTABLISH_CONNECTION_NUM_RETRIES + 1 {
                match TcpStream::connect(&addr).await {
                    Err(_) => {
                        //println!("Error connecting to {}: {:?}. Retrying ...", addr, e);
                        sleep(get_retry_delay(num_retry)).await;
                        connect_recursive(addr, num_retry + 1).await
                    }
                    Ok(socket) => Ok(socket),
                }
            } else {
                Err(anyhow::anyhow!(
                    "Could not open connection to {} after {} retries.",
                    addr,
                    num_retry
                ))
            }
        }
        .boxed()
    }
    connect_recursive(addr, 0)
        .map(|tcp_stream| tcp_stream.map(tokio::io::split))
        .await
}

/// Open connection to peer. Calls connect_recursive.
pub async fn open_connection(
    self_index: u16,
    addr: SocketAddr,
) -> anyhow::Result<(ReadHalf<TcpStream>, WriteHalf<TcpStream>)> {
    let socket = connect_recursive(addr).await;

    match socket {
        Ok((socket_read, mut socket_write)) => {
            send_msg(&mut socket_write, &u16::to_le_bytes(self_index).to_vec()).await;
            Ok((socket_read, socket_write))
        }
        Err(err) => Err(err).context(format!("Self: {}", self_index)),
    }
}
