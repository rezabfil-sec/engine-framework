use std::env::args;
use std::error::Error;
use std::fmt;
use std::fs::File;
use std::io::Write;
use std::path::PathBuf;

use tracing::error; // trace debug info warn

use std::path::Path;
use std::time::{Duration, Instant};
use structopt::StructOpt;

use std::net::SocketAddr;
use std::thread::sleep;
use rand::Rng;
use tokio::net::{TcpListener, TcpSocket, TcpStream};
use anyhow::{anyhow, Result, Context};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use bls::threshold_bls::party_i::PartialSignature;
use bls::basic_bls::BLSSignature;
use futures::{Stream, Sink, stream::FusedStream, channel::mpsc, SinkExt, StreamExt};
use bls::threshold_bls;
use crate::bls_psign_ext::psign_ext;

mod p2p_noise;
mod bls_psign_ext;
mod p2p;

#[derive(Debug, StructOpt)]
#[structopt(about = "treb: Tamper-Resistant signaturE service Benchmark: performance measurements")]
struct CliArgs {
    /// CSV file to store the results in. Will be truncated and created if nonexistent.
    #[structopt(parse(from_os_str), short)]
    resultsfile: PathBuf,
    /// iteration count
    #[structopt(short, index = 1)]
    iterations: usize,
    /// to perform dkg or not
    #[structopt(short, index = 2)]
    with_dkg: bool,
    #[structopt(subcommand)]
    command: Command,
}

#[derive(Debug, StructOpt)]
enum Command {
    Sign {
        service_addr: String,
        msg_len: usize,
        phonebook: String,
        presetup_sleep: Option<u64>,
        postsetup_sleep: Option<u64>,
    },
}

fn run() -> Result<i32, Box<dyn Error>> {

    // heap alloc in case we return an Error
    let args = CliArgs::from_args();

    let rt = tokio::runtime::Runtime::new().unwrap();
    Ok(rt.block_on(async {
        let mut bench = Benchmark::new(args);

        bench.run().await
    }))
}

fn main() {
    std::process::exit(match run() {
        Ok(exitcode) => exitcode,
        Err(err) => {
            eprintln!("Setup error: {:?}", err);
            1
        }
    });
}

struct Benchmark {
    /// timing data
    results: Vec<Duration>,
    resultsfile: PathBuf,
    aspect: Aspect,
    with_dkg: bool,
}
/// Runs a benchmark and stores the result
impl Benchmark {
    fn new(args: CliArgs) -> Self {
        let aspect = match args.command {
            Command::Sign { service_addr, msg_len , phonebook, presetup_sleep,postsetup_sleep} => Aspect::Sign(MeasureSign::new(&args.iterations, service_addr, msg_len, phonebook, presetup_sleep, postsetup_sleep)),
        };
        let resultsfile = args.resultsfile;
        let with_dkg = args.with_dkg;
        Self { results: Vec::with_capacity(args.iterations), resultsfile, aspect, with_dkg}
    }

    async fn run(&mut self) -> i32 {

        // prepare
        if self.with_dkg {
            match &mut self.aspect {
                Aspect::Sign(s) => s.prepare().await,
            }
        }
        for i in 0..self.results.capacity() {
            tokio::time::sleep(Duration::from_millis(1)).await;
            let duration = match &mut self.aspect {
                Aspect::Sign(p) => p.run_one_iteration().await,
            };
            self.results.push(duration);
        }

        self.write_to_file(&self.resultsfile);
        0
    }

    fn write_to_file(&self, filename: &Path) {
        let mut f = File::create(filename).expect("Error opening file for writing");
        writeln!(f, "is_ok,run_id,duration_ns").expect("Error writing data");

        let mut is_ok_iter = match &self.aspect {
            Aspect::Sign(s) => s.is_ok_iter(),
        };

        for (run_id, timing) in self.results.iter().enumerate() {
            let is_ok = is_ok_iter.next().expect("Error: inconsistent length of result data!");
            writeln!(f, "{},{},{}", is_ok, run_id, timing.as_nanos()).expect("Error writing data");
        }
    }
}

enum Aspect {
    Sign(MeasureSign),
}
impl fmt::Display for Aspect {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match &*self {
            Aspect::Sign(_) => write!(f, "sign"),
        }
    }
}

struct MeasureSign {
    results: Vec<Result<Vec<u8>, Box<dyn Error>>>,
    request_addr: SocketAddr,
    message: Vec<u8>,
    phonebook: String,
    presetup_sleep: Option<u64>,
    postsetup_sleep: Option<u64>,
}
impl MeasureSign {
    fn new(iteration_count: &usize, service_addr: String, msg_len: usize, phonebook: String, presetup_sleep: Option<u64>, postsetup_sleep: Option<u64>) -> Self {
        let request_addr = service_addr.parse::<SocketAddr>().unwrap();

        const CHARSET: &[u8] = b"0123456789";
        let mut rng = rand::thread_rng();

        let message_string: String = (0..2*msg_len)
            .map(|_| {
                let idx = rng.gen_range(0,CHARSET.len());
                CHARSET[idx] as char
            })
            .collect();

        let msg_vec = hex::decode(message_string).unwrap();

        let mut message: Vec<u8> = vec![((msg_len.clone() >> 8) as u8), ((msg_len & 0xff) as u8)];
        message.extend_from_slice(&msg_vec);  //append message to length field
        Self { results: Vec::with_capacity(*iteration_count), request_addr, message, phonebook, presetup_sleep, postsetup_sleep }
    }

    async fn prepare(&self) {
        tokio::time::sleep(Duration::from_millis(self.presetup_sleep.unwrap())).await;
        keygen_client_recv(self.phonebook.clone()).await;
        tokio::time::sleep(Duration::from_millis(self.postsetup_sleep.unwrap())).await;
    }

    async fn run_one_iteration(&mut self ) -> Duration {
        println!("Starting one sign iteration");

        let now_before = Instant::now();
        let res = request_sig_from_aggregator_service(self.request_addr.clone(), self.message.clone()).await;
        let now_after = Instant::now();

        if let Err(ref err) = res {
            error!("Signing error: {}", err)
        }

        self.results.push(res);

        now_after.duration_since(now_before)
    }

    fn is_ok_iter<'s>(&'s self) -> Box<dyn Iterator<Item = bool> + 's> {
        Box::new(self.results.iter().map(|x| x.is_ok()))
    }
}

async fn request_sig_from_aggregator_service(
    request_addr: SocketAddr,
    msg: Vec<u8>,
) -> Result<Vec<u8>, Box<dyn Error>> {
    let now_before_2 = Instant::now();
    //open tcp connection to sign+aggregator service
    let mut socket = TcpSocket::new_v4().unwrap();
    let mut tcp_stream = socket.connect(request_addr).await.context("connecting to aggregator service")?;

    //send msg
    tcp_stream.write_all(&msg).await.context("sending message to aggregator service")?;

    //receive sig from signing+aggregator service
    let mut len_field: Vec<u8> = vec![0; 2];    //buffer for 16b length field
    tcp_stream.read_exact(&mut len_field).await.context("receiving signature length field")?;
    let len = (((len_field[0] as usize) << 8) + (len_field[1] as usize));
    if len > 65535 { return panic!("received message len too long: {} B", len); }

    let mut msg_buf: Vec<u8> = vec![0; len];
    tcp_stream.read_exact(&mut msg_buf).await.context("receiving signature")?;
    // println!("Sign : {:?}",hex::encode(msg_buf.clone()));
    tcp_stream.shutdown();

    let now_after_2 = Instant::now();
    let diff = now_after_2.duration_since(now_before_2);
    println!("Time taken: {:?}",diff);
    Ok(msg_buf)
}

async fn keygen_request(
    phonebook_path: String,
) -> Result<()> {
    let msg_str = "0000";
    let msg = hex::decode(msg_str)?;

    let phonebook = p2p_noise::p2pNoiseAE::read_phonebook(phonebook_path)?;

    for peer in phonebook.iter() {
        let peer_clone = peer.clone();
        let msg_clone = msg.clone();
        let peer_addr = peer_clone.addr;
        let dkg_listen_port = peer_addr.port()+100;
        let dkg_listen_addr = SocketAddr::new(peer_addr.ip(), dkg_listen_port);

        let mut socket = TcpSocket::new_v4().unwrap();
        let mut tcp_stream = socket.connect(dkg_listen_addr).await.context("connecting to keygen service")?;

        //send msg to initiate dkg
        tcp_stream.write_all(&msg_clone).await.context("sending message to keygen service")?;
        println!("Peer: {}", dkg_listen_addr);
    }

    Ok(())
}

async fn keygen_client_recv(
    phonebook_path: String,
) -> Result<()>{
    let phonebook = p2p_noise::p2pNoiseAE::read_phonebook(phonebook_path)?;

    let msg_str = "0000";
    let msg = hex::decode(msg_str)?;

    let (mut psigs_tx, mut psigs_rx) = futures::channel::mpsc::channel(phonebook.len());

    let peer_count = phonebook.len();

    //contact all peers and request signature
    for peer in phonebook.iter() {
        let peer_clone = peer.clone();
        let msg_clone = msg.clone();
        let mut psigs_tx_clone = psigs_tx.clone();
        let peer_addr = peer_clone.addr;
        let dkg_listen_port = peer_addr.port()+100;
        let dkg_listen_addr = SocketAddr::new(peer_addr.ip(), dkg_listen_port);

        tokio::spawn(async move {
            //open TCP connection
            println!("Starting spawn");
            let mut tcp_stream: TcpStream;
            let mut socket = TcpSocket::new_v4().unwrap();
            match socket.connect(dkg_listen_addr).await {
                Ok(tcp_str) => {
                    tcp_stream = tcp_str;
                }
                Err(e) => {
                    println!("Error while trying to connect to to peer #{}: {}", peer_clone.ID, e);
                    return;
                }
            };

            //send msg
            match tcp_stream.write_all(&msg_clone).await {
                Ok(_) => {}
                Err(e) => {
                    println!("error sending msg to peer #{}", peer_clone.ID);
                }
            }

            //receive responses
            let mut response: Vec<u8> = vec![0; 2];    //buffer for 16b length field
            match tcp_stream.read_exact(&mut response).await {
                Ok(_) => {}
                Err(e) => {
                    println!("error receiving response from peer #{}", peer_clone.ID);
                    return;
                }
            }
            println!("Response received: {:?}", response);

            match psigs_tx_clone.send(response).await {
                Ok(_) => {}
                Err(e) => {println!("partial signature mpsc closed with: {}", e);}
            }
        });
    }

    let mut response_count = 0;
    while let Some(response) = psigs_rx.next().await {
        response_count += 1;
        if response_count == peer_count {
            // All peers finished dkg
            break;
        }
        //timeCheckAndStore += check_add_start.elapsed();
    }

    println!("Completed dkg");
    Ok(())
}
