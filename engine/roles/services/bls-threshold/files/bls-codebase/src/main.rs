#![allow(non_snake_case)]

use clap::{Parser, Subcommand};
use anyhow::{anyhow, Result, Context, Error};
use snow::Keypair;
use bls;
use round_based::Msg;
use curv;
use hex;
use tokio::runtime;
use std::process::exit;
use bls::basic_bls::BLSSignature;
use curv::elliptic::curves::traits::{ECPoint, ECScalar};
use curv::elliptic::curves::bls12_381::g2::{FE as FE2};
use curv::elliptic::curves::bls12_381::g2::GE as GE2;
use bls::threshold_bls;
use clap::builder::Str;
use futures::{Stream, Sink, stream::FusedStream, channel::mpsc, SinkExt, StreamExt};
use serde::{de::DeserializeOwned, Serialize, Deserialize};
use tracing::error;
use std::net::SocketAddr;
use bls::threshold_bls::party_i::PartialSignature;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::{TcpListener, TcpSocket, TcpStream};
use crate::bls_psign_ext::psign_ext;
use crate::mpsc::SendError;
use std::time::{Duration, Instant};
use std::mem;
use std::{thread, time};
use std::borrow::BorrowMut;
use std::cell::RefCell;
use std::rc::Rc;
use std::sync::{Arc, Mutex};
use futures::{channel::mpsc::{Sender, Receiver}};

mod p2p_noise;
mod bls_psign_ext;
mod p2p;

#[derive(Parser)]
struct Cli {
    ///number of threads to use
    threads: Option<usize>,

    #[clap(subcommand)]
    command: Commands
}

#[derive(Subcommand)]
enum Commands {
    /// generate key pairs for the p2p noise network
    p2p_keygen {
        ///csv file with: {peer_ID, ip:port}
        hosts_file: String,

        ///output file for generated phonebook
        output_file: String,

        ///directory in which to put private key files
        privkey_dir: String,
    },

    keygen {
        ///phonebook file path
        phonebook: String,

        ///p2p identity file path
        p2p_id: String,

        ///bls key file output path
        output_path: String,

        ///threshold
        t: u16,

        ///sleep time before initiating p2p connections, in milliseconds
        preconn_sleep: u64,

        ///sleep time after initiating all connections, in milliseconds
        postconn_sleep: u64,
    },

    keygen_centralized {
        ///number of nodes
        n: u16,

        ///threshold
        t: u16,

        ///keys output directory
        keydir: String,

        ///turn off file writing
        noWrite: Option<bool>,
    },

    ///sign a message using the protocol provided by multi-party-bls, with AE
    sign {
        ///phonebook file path
        phonebook: String,

        ///p2p identity file path
        p2p_id: String,

        ///bls key file path
        bls_keys: String,

        ///message (digest) to sign (hex)
        message: String,
    },

    ///signing service for handling continuous signing request
    sign_service_ext {
        ///p2p identity file path
        identity_path: String,

        ///bls key file path
        bls_keys: String,

        ///wait time for dkg completion
        dkg_sleep: Option<u64>,
    },

    ///sending request to peers and combining the partial signatures
    sign_request_ext {
        t: u16,
        n: u16,
        ///needed to get verification keys
        bls_key_path: String,
        phonebook_path: String,
        ///in hex
        msg: String,
    },

    ///signing service with aggregator for continuous request
    sign_agg_service {
        ///address to listen on for requests
        listen_addr: String,
        p2p_id: String,
        bls_key_path: String,
        phonebook_path: String,
        ///wait time for dkg completion
        dkg_sleep: Option<u64>,
    },

    ///request signature from signing and aggregation service
    sign_agg_request {
        service_addr: String,
        msg: String,
    },

    verify {
        ///public key (hex encoded)
        public_key: String,

        ///signature (hex encoded)
        signature: String,

        ///message (hex encoded)
        message: String,
    },

    read_identity {
        path: String,
    },

    read_phonebook {
        path: String
    },
}

fn main() {
    let cli = Cli::parse();

    // Build async runtime
    let mut runtime = runtime::Builder::new_multi_thread();

    runtime.enable_all();

    if let Some(t) = cli.threads {
        runtime.worker_threads(t);
    }

    let runtime = match runtime.build() {
        Ok(r) => r,
        Err(e) => {
            error!("Failed to build async runtime: {}", e);
            exit(1)
        }
    };

    // Execute requested command
    let result = runtime.block_on(async move {
        match cli.command {
            Commands::p2p_keygen {hosts_file, output_file, privkey_dir} => {
                p2p_noise::p2pNoiseAE::generateP2pKeys(hosts_file, output_file, privkey_dir)
            },
            Commands::keygen { phonebook, p2p_id, output_path, t, preconn_sleep, postconn_sleep } => {
                //start keygen
                let t_start_keygen = Instant::now();

                keygen(phonebook, p2p_id, output_path, t, preconn_sleep, postconn_sleep).await?;
                let t_keygen = t_start_keygen.elapsed();
                println!("main: DKG completed in: {:?}", t_keygen);
                Ok(())
            },
            Commands::keygen_centralized { n, t, keydir, noWrite } => {
                let mut writeFiles = true;
                if let Some(b) = noWrite {
                    writeFiles = false;
                }
                let start_time = Instant::now();
                keygen_centralized(n, t, keydir, writeFiles).await?;
                let elapsed_time = start_time.elapsed();
                println!("Centralized KG completed in: {:?}", elapsed_time);
                Ok(())
            },
            Commands::sign { phonebook, p2p_id, bls_keys, message } => {
                let message = hex::decode(message)?;

                //establish network
                let (p2p_noise_ae, in_stream, out_sink) = connect_p2p(phonebook, p2p_id, 0).await.context("connecting p2p")?;

                let local_key = read_bls_keys(bls_keys).await?;

                //start signing
                let sig = bls_sign(in_stream, out_sink, message, p2p_noise_ae.local_id(), p2p_noise_ae.n(), local_key).await?;

                println!("Signature: {:?}", sig);

                Ok(())
            },
            Commands::sign_service_ext {identity_path, bls_keys, dkg_sleep} => {
                //value recommended = 120000
                if let Some(ds) = dkg_sleep {
                    tokio::time::sleep(Duration::from_millis(ds)).await;
                }
                let identity = p2p_noise::p2pNoiseAE::read_identity(identity_path)?;
                let keys = read_bls_keys(bls_keys).await?;
                bls_sign_service_ext(keys, identity.listen_addr).await?;
                Ok(())
            },
            Commands::sign_request_ext { t, n, bls_key_path, phonebook_path, msg } => {
                let msg_vec = hex::decode(msg)?;
                let keys = read_bls_keys(bls_key_path).await?;
                let phonebook = p2p_noise::p2pNoiseAE::read_phonebook(phonebook_path)?;
                let sig = request_sig_ext(t, n, keys.vk_vec, phonebook, msg_vec).await?;
                Ok(())
            },
            Commands::sign_agg_service { listen_addr, p2p_id, bls_key_path, phonebook_path, dkg_sleep} => {
                //value recommended = 120000
                if let Some(ds) = dkg_sleep {
                    tokio::time::sleep(Duration::from_millis(ds)).await;
                }
                let rx_addr = listen_addr.parse::<SocketAddr>()?;
                let psig_sig_p2pid = p2p_noise::p2pNoiseAE::read_identity(p2p_id)?;
                let bls_key = read_bls_keys(bls_key_path).await?;
                let phonebook = p2p_noise::p2pNoiseAE::read_phonebook(phonebook_path)?;
                sign_and_aggregate_service(bls_key, psig_sig_p2pid.listen_addr, rx_addr, phonebook).await?;
                Ok(())
            },
            Commands::sign_agg_request { service_addr, msg } => {
                let start_time = Instant::now();
                let addr = service_addr.parse::<SocketAddr>()?;
                let msg_vec = hex::decode(msg)?;
                let sig = request_sig_from_aggregator_service(addr, msg_vec).await?;
                let elapsed_time = start_time.elapsed();
                println!("Signature: {}, in {:?}", hex::encode(sig), elapsed_time);
                Ok(())
            },
            Commands::verify { public_key, signature, message } => {
                let validity = verify(public_key, signature, message)?;
                if validity {
                    println!("Signature is valid");
                } else {
                    println!("Signature is invalid");
                }
                Ok(())
            },
            Commands::read_identity {path} => {
                println!("identity: {:?}", p2p_noise::p2pNoiseAE::read_identity(path)?);
                Ok(())
            },
            Commands::read_phonebook {path} => {
                println!("phonebook: {:?}", p2p_noise::p2pNoiseAE::read_phonebook(path)?);
                Ok(())
            },
        }
    });


    if let Err(e) = result {
        error!("Error: {}", e);
        println!("Error!: {}", e);
        exit(1);
    }
}

/// i is round-based index !!
async fn keygen(
    phonebook: String,
    p2p_id: String,
    output_path: String,
    t: u16,
    preconn_sleep: u64,
    postconn_sleep:u64,
) -> Result<(), anyhow::Error> {
    let identity = p2p_noise::p2pNoiseAE::read_identity(p2p_id.clone()).context("reading noise identity file")?;
    let mut dkg_listen_address = identity.listen_addr;
    let dkg_listen_port = dkg_listen_address.port()+100;

    dkg_listen_address.set_port(dkg_listen_port);

    //open tcp socket to listen for signature+aggregation requests
    let service_listener = TcpListener::bind(dkg_listen_address).await?;

    //accept incoming connection for request
    let (mut socket, _) = service_listener.accept().await.unwrap();
    println!("keygen: incoming keygen request!");
    let mut buf: Vec<u8> = vec![0; 2];
    match socket.read_exact(&mut buf).await {
        Ok(2) => {}
        Ok(n) => {
            println!("less than 2 bytes received??");
        }
        Err(e) => {
            return Err(anyhow!("error receiving msg!"));
        }
    }

    let (p2p_noise_ae, in_stream, out_sink) = connect_p2p(phonebook.clone(), p2p_id.clone(), preconn_sleep.clone()).await.context("connecting p2p")?;

    //wait for p2p network to build up
    tokio::time::sleep(Duration::from_millis(postconn_sleep.clone())).await;

    let n = p2p_noise_ae.n();
    let i = (p2p_noise_ae.local_id() + 1);

    let t_start_keygen = Instant::now();
    keygen_serv(in_stream, out_sink, n, t, i, output_path).await?;
    let t_keygen = t_start_keygen.elapsed();
    println!("client DKG completed in: {:?}", t_keygen);

    // send a response to indicate completion of dkg
    let msg_str = "1111";
    let msg = hex::decode(msg_str)?;
    match socket.write_all(&msg).await {
        Ok(_) => {}
        Err(e) => {
            println!("error sending response to client!");
        }
    }
    Ok(())
}

async fn keygen_serv(
    mut in_stream: impl Stream<Item = std::result::Result<Msg<threshold_bls::state_machine::keygen::ProtocolMessage>, anyhow::Error>> + FusedStream + Unpin,
    mut out_sink: impl Sink<Msg<threshold_bls::state_machine::keygen::ProtocolMessage>, Error = mpsc::SendError> + Unpin,
    n: u16,
    t: u16,
    i: u16,
    output_path: String,
) -> Result<()> {
    //run keygen protocol
    let keygen = bls::threshold_bls::state_machine::keygen::Keygen::new(i, t, n)?;
    let keygen_output = match round_based::AsyncProtocol::new(keygen, in_stream, out_sink).run().await {
        Ok(r) => {r}
        Err(e) => {return Err(anyhow!("error executing key generation protocol"))}
    };

    //serialize key to json and write to file
    let local_key_json = serde_json::to_vec(&keygen_output)?;
    tokio::fs::write(output_path, local_key_json).await?;

    //print public key
    let public_key = curv::elliptic::curves::traits::ECPoint::pk_to_key_slice(&keygen_output.public_key());
    println!("public key: {:?}", hex::encode(public_key));

    Ok(())
}

async fn keygen_centralized(
    n: u16,
    t:u16,
    keydir: String,
    writeFiles: bool,
) -> Result<()> {
    if t > n {
        return Err(anyhow!("t: {} must be smaller than n: {}", t, n));
    }

    //generate new random keypair
    let sk = FE2::new_random();
    let pk = GE2::generator() * &sk;

    //calculate Shamir Secret Sharing
    //the following 4 lines are adapted from VerifiableSS::share(...) in https://github.com/ZenGo-X/curv/blob/master/src/cryptographic_primitives/secret_sharing/feldman_vss.rs
    let poly = curv::cryptographic_primitives::secret_sharing::feldman_vss::VerifiableSS::<GE2>::sample_polynomial(t as usize, &sk);
    let index_vec: Vec<usize> = (1..=(n as usize)).collect();
    let secret_shares = curv::cryptographic_primitives::secret_sharing::feldman_vss::VerifiableSS::<GE2>::evaluate_polynomial(&poly, &index_vec);
    let sss = curv::cryptographic_primitives::secret_sharing::feldman_vss::ShamirSecretSharing { threshold: t as usize, share_count: n as usize};

    //calculate vks
    let mut vks = vec![];
    for i in 0..(n as usize) {
        let ec_point: GE2 = ECPoint::generator();
        let pk = ec_point.scalar_mul(&secret_shares[i].get_element());
        vks.push(pk);
    }

    if !writeFiles {
        return Ok(());
    }

    //construct LocalKeys
    let mut localkeys = vec![];
    for i in 0..(n as usize) {
        localkeys.push(threshold_bls::state_machine::keygen::LocalKey {
            shared_keys: threshold_bls::party_i::SharedKeys {
                index: i,
                params: sss.clone(),
                vk: pk.clone(),
                sk_i: secret_shares[i].clone()
            },
            vk_vec: vks.clone(),
            i: (i + 1) as u16,
            t: t,
            n: n
        })
    }

    //write key files
    std::fs::create_dir_all(keydir.clone())?;
    for i in 0..(n as usize) {
        let localkey_json = serde_json::to_vec(&localkeys[i])?;
        std::fs::write(format!("{}/{}", keydir.clone(), i), localkey_json)?;
    }

    Ok(())
}

async fn bls_sign(
    mut in_stream: impl Stream<Item = std::result::Result<Msg<threshold_bls::state_machine::sign::ProtocolMessage>, anyhow::Error>> + FusedStream + Unpin,
    mut out_sink: impl Sink<Msg<threshold_bls::state_machine::sign::ProtocolMessage>, Error = mpsc::SendError> + Unpin,
    msg: Vec<u8>,
    i: u16,
    n: u16,
    local_key: threshold_bls::state_machine::keygen::LocalKey,
) -> Result<BLSSignature> {

    //run signing protocol
    let signing = threshold_bls::state_machine::sign::Sign::new(msg, i, n, local_key).context("construct signing initial state")?;
    let sig = match round_based::AsyncProtocol::new(signing, in_stream, out_sink).run().await {
        Ok((_, s)) => {s}
        Err(_) => { return Err(anyhow!("error executing signing protocol"));}
    };

    let public_key = curv::elliptic::curves::traits::ECPoint::pk_to_key_slice(&sig.clone().sigma);
    println!("Signature: {}", hex::encode(public_key));

    Ok(sig)
}

async fn bls_sign_service_ext(
    bls_keys: bls::threshold_bls::state_machine::keygen::LocalKey,
    listen_addr: SocketAddr,
) -> Result<()> {

    //open TCP socket to listen for signing requests
    let listener = TcpListener::bind(listen_addr).await?;

    //accept connection, spawn task to generate signature and send back to requester
    loop {
        let (mut socket, _) = listener.accept().await.unwrap();
        println!("incoming signing request connection!");

        let keyCopy = bls_keys.clone();
        tokio::spawn(async move {
            //receive msg from requester, first two bytes indicate length
            let mut buflen: Vec<u8> = vec![0; 2];
            socket.read_exact(&mut buflen).await;
            let len = (((buflen[0] as usize) << 8) + (buflen[1] as usize));

            let mut buf: Vec<u8> = vec![0; len];
            match socket.read_exact(&mut buf).await {
                Ok(len) => {}
                Ok(n) => {
                    println!("other size received");
                    return;
                }
                Err(e) => {
                    println!("error receiving msg!");
                    return;
                }
            }

            //generate signature
            let (sig, _) = psign_ext::psign(keyCopy, &buf);

            //send signature to requester (with 16 bit length field)
            let sig_ser = serde_json::to_vec(&sig).unwrap();
            let mut len_be: Vec<u8> = vec![((sig_ser.len() >> 8) as u8), ((sig_ser.len() & 0xff) as u8)];    //16b length in big endian (network byte order)
            len_be.extend_from_slice(&sig_ser);  //append message to length field
            match socket.write_all(&len_be).await {
                Ok(_) => {}
                Err(e) => {
                    println!("error sending partial signature to requester!");
                }
            }
        });
    }

    Ok(())
}

// initiated by agg, has list of all peers, sends req to each of them, collects partial signs and at the end aggregates them,
// and sends that final sign to agg
async fn request_sig_ext(
    t: u16,
    n: u16,
    verification_keys: Vec<curv::elliptic::curves::bls12_381::g2::GE>,
    phonebook: Vec<p2p_noise::p2pNoisePeer>,
    msg: Vec<u8>,
) -> Result<BLSSignature>{
    //mpsc queue for received partial signatures
    let (mut psigs_tx, mut psigs_rx) = futures::channel::mpsc::channel(phonebook.len());
    let mut msg_backup = msg.clone();

    //contact all peers and request signature
    for peer in phonebook.iter() {

        let peer_clone = peer.clone();
        let msg_clone = msg.clone();
        let mut psigs_tx_clone = psigs_tx.clone();
        tokio::spawn(async move {
            //open TCP connection
            let mut tcp_stream: TcpStream;
            let mut socket = TcpSocket::new_v4().unwrap();
            match socket.connect(peer_clone.addr).await {
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

            //receive sig from peer
            let mut len_field: Vec<u8> = vec![0; 2];    //buffer for 16b length field
            match tcp_stream.read_exact(&mut len_field).await {
                Ok(_) => {}
                Err(e) => {
                    println!("error receiving partial signature (length field) from peer #{}", peer_clone.ID);
                    return;
                }
            }
            let len = (((len_field[0] as usize) << 8) + (len_field[1] as usize));
            if len > 65535 {    //TODO: ???
                println!("received message len too long: {} B", len);
                return;
            }
            let mut msg_buf: Vec<u8> = vec![0; len];
            match tcp_stream.read_exact(&mut msg_buf).await {
                Ok(_) => {}
                Err(e) => {
                    println!("error receiving partial signature from peer #{}: {}", peer_clone.ID, e);
                    return;
                }
            }

            //deserialize partial signature & input to mpsc
            let psig = match serde_json::from_slice::<PartialSignature>(&msg_buf) {
                Ok(sig) => {sig}
                Err(e) => {
                    println!("error deserializing partial signature");
                    return;
                }
            };
            match psigs_tx_clone.send(psig).await {
                Ok(_) => {}
                Err(e) => {println!("partial signature mpsc closed with: {}", e);}
            }
        });
    }

    // remove the size bytes before signature combining
    msg_backup.drain(0..2);

    //combine received signatures
    let msg_point = bls_psign_ext::psign_ext::msg_to_point(&msg_backup);
    let mut aggregator = bls_psign_ext::psign_ext::new(t, n, verification_keys);
    //let mut timeCheckAndStore = Duration::from_millis(0);
    while let Some(psig) = psigs_rx.next().await {
        //let check_add_start = Instant::now();
        match aggregator.check_add_psig(psig, msg_point.clone()) {
            Ok(false) => {}
            Ok(true) => {break;}
            Err(e) => {println!("error adding partial signature: {}", e);}
        }
        //timeCheckAndStore += check_add_start.elapsed();
    }

    //let time_sendReceiveCheckAndStore = start_network.elapsed();

    //let startCombine = Instant::now();
    let signResult = aggregator.combine();
    //let timeCombine = startCombine.elapsed();

    //println!("request_sigs_ext measured times: sendReceiveCheckAdd: {:?}, checkAndStore: {:?}, combine: {:?}", time_sendReceiveCheckAndStore, timeCheckAndStore, timeCombine);

    return signResult;
}

// Aggregator first starts its own signing service, then listens for requests from client
async fn sign_and_aggregate_service(
    bls_keys: bls::threshold_bls::state_machine::keygen::LocalKey,
    listen_addr_sig_req: SocketAddr,
    listen_addr_sig_aggr_service: SocketAddr,
    phonebook: Vec<p2p_noise::p2pNoisePeer>,
) -> Result<()> {

    let bls_keys_cpy = bls_keys.clone();
    //start partial signing service
    tokio::spawn(async move {
        let id = bls_keys_cpy.i();
        match bls_sign_service_ext(bls_keys_cpy, listen_addr_sig_req).await {
            Ok(_) => {}
            Err(e) => {println!("partial signing service #{} error: {}", id, e);}
        }
    });

    //open tcp socket to listen for signature+aggregation requests
    let service_listener = TcpListener::bind(listen_addr_sig_aggr_service).await?;

    // ...
    loop {
        //accept incoming connection for request
        let (mut socket, _) = service_listener.accept().await.unwrap();
        println!("aggregator: incoming signing request connection!");

        let key_copy = bls_keys.clone();
        let phonebook_cpy = phonebook.clone();
        tokio::spawn(async move {
            //receive message to be signed, first two bytes indicate length
            let mut buflen: Vec<u8> = vec![0; 2];
            match socket.read_exact(&mut buflen).await {
                Ok(_) => {}
                Err(e) => {
                    println!("error receiving message length");
                    return;
                }
            }
            let len = (((buflen[0] as usize) << 8) + (buflen[1] as usize));

            let mut buf: Vec<u8> = vec![0; len];
            match socket.read_exact(&mut buf).await {
                Ok(len) => {}
                Ok(n) => {
                    println!("message of different length received");
                    return;
                }
                Err(e) => {
                    println!("sign_and_aggregate_service: error receiving msg!");
                    return;
                }
            }
            buflen.extend_from_slice(&buf);
            //generate signature by requesting and aggregating partial signatures
            let sig = match request_sig_ext(key_copy.t(), key_copy.n(), key_copy.vk_vec.clone(), phonebook_cpy, buflen).await {
                Ok(sig) => {sig}
                Err(e) => {
                    println!("signature generation error: {}", e);
                    //write error string back to requester
                    match socket.write_all(e.to_string().as_bytes()).await {
                        Ok(_) => {}
                        Err(e) => {println!("error sending error back to requester: {}", e);}
                    }
                    return;
                }
            };

            //send signature back to requester
            let sig_bytes = curv::elliptic::curves::traits::ECPoint::pk_to_key_slice(&sig.sigma);
            let mut len_be: Vec<u8> = vec![((sig_bytes.len() >> 8) as u8), ((sig_bytes.len() & 0xff) as u8)];    //16b length in big endian (network byte order)
            len_be.extend_from_slice(&sig_bytes);  //append message to length field
            match socket.write_all(&len_be).await {
                Ok(_) => {}
                Err(e) => {println!("failed to send signature back to requester: {}", e);}
            }

            //close client connection

        });
    }

    Ok(())
}

//Client requesting signature, has the agg ip address and msg to be signed
async fn request_sig_from_aggregator_service(
    request_addr: SocketAddr,
    msg: Vec<u8>,
) -> Result<Vec<u8>> {
    //open tcp connection to sign+aggregator service
    let mut socket = TcpSocket::new_v4().unwrap();
    let mut tcp_stream = socket.connect(request_addr).await.context("connecting to aggregator service")?;

    //send msg
    tcp_stream.write_all(&msg).await.context("sending message to aggregator service")?;

    //receive sig from signing+aggregator service

    let mut len_field: Vec<u8> = vec![0; 2];    //buffer for 16b length field
    tcp_stream.read_exact(&mut len_field).await.context("receiving signature length field")?;
    let len = (((len_field[0] as usize) << 8) + (len_field[1] as usize));
    if len > 65535 {    //TODO: ???
        return Err(anyhow!("received message len too long: {} B", len));
    }

    let mut msg_buf: Vec<u8> = vec![0; len];
    tcp_stream.read_exact(&mut msg_buf).await.context("receiving signature")?;

    Ok(msg_buf)
}

fn verify(
    public_key: String,
    signature: String,
    msg: String,
) -> Result<bool> {

    //decode keys from hex
    let public_key = hex::decode(public_key).context("public key is not valid hex encoded string")?;
    let signature = hex::decode(signature).context("signature key is not valid hex encoded string")?;
    let msg = hex::decode(msg).context("message not valid hex encoded string")?;

    //deserialize signature and pubkey to points on curves
    let signature = curv::elliptic::curves::bls12_381::g1::GE::from_bytes(&signature)
        .map_err(|e| anyhow!("signature is not valid g1 point: {:?}", e))?;
    let public_key = curv::elliptic::curves::bls12_381::g2::GE::from_bytes(&public_key)
        .map_err(|e| anyhow!("public key is not valid g2 point: {:?}", e))?;

    //verify signature with pubkey
    let valid = BLSSignature { sigma: signature }.verify(&msg, &public_key);

    Ok(valid)
}

async fn connect_p2p<T>(
    phonebook_path: String,
    noise_keypair_path: String,
    pre_conn_wait_millis: u64,
) -> Result<(
    p2p_noise::p2pNoiseAE,
    impl Stream<Item = std::result::Result<Msg<T>, anyhow::Error>> + FusedStream + Unpin,
    impl Sink<Msg<T>, Error = mpsc::SendError> + Unpin,
)> where T: Serialize + DeserializeOwned + Send + 'static, {

    let pre_conn_sleep_dur = Duration::from_millis(pre_conn_wait_millis);

    //read files
    let phonebook = p2p_noise::p2pNoiseAE::read_phonebook(phonebook_path).context("reading noise phonebook file")?;
    let identity = p2p_noise::p2pNoiseAE::read_identity(noise_keypair_path).context("reading noise identity file")?;

    //set up p2p network
    let (noiseAE, mut in_stream, mut out_sink) = p2p_noise::p2pNoiseAE::init_p2p(
        identity.listen_addr.to_string(),
        phonebook,
        identity.ID,
        snow::Keypair { private: identity.privkey, public: identity.pubkey },
        pre_conn_sleep_dur,
    ).await.context("call to init_p2p")?;

    Ok((noiseAE, in_stream, out_sink))
}

async fn read_bls_keys(path: String) -> Result<threshold_bls::state_machine::keygen::LocalKey> {
    let secret = tokio::fs::read(path).await.context("read file with local secret key")?;
    let secret = serde_json::from_slice(&secret).context("deserialize local secret key")?;

    Ok(secret)
}

#[cfg(test)]
mod tests {
    use std::thread::sleep;
    use std::time::Duration;
    use super::*;

    #[test]
    fn test_keygen() {
        // Build async runtime
        let mut runtime = tokio::runtime::Builder::new_multi_thread();

        runtime.enable_all();

        /*
        if let Some(t) = app.threads {
            runtime.worker_threads(t);
        }
        */

        let runtime = match runtime.build() {
            Ok(r) => r,
            Err(e) => {
                println!("Failed to build async runtime: {}", e);
                exit(1)
            }
        };

        let result = runtime.block_on(async {

            //setup:

            let phonebook_path: String = "test_k_dir/phonebook".parse().unwrap();

            //create test working directory
            tokio::fs::create_dir_all("test_k_dir").await.unwrap();
            tokio::fs::create_dir_all("test_k_dir/identities").await.unwrap();
            tokio::fs::create_dir_all("test_k_dir/bls_keys").await.unwrap();

            //create hosts file
            let hosts = "id,ip\n0,127.0.0.1:42000\n1,127.0.0.1:42001\n2,127.0.0.1:42002\n3,127.0.0.1:42003";
            tokio::fs::write("test_k_dir/hosts", hosts).await.unwrap();

            //create phonebook and keys
            p2p_noise::p2pNoiseAE::generateP2pKeys("test_k_dir/hosts".parse().unwrap(), phonebook_path.clone(), "test_k_dir/identities".parse().unwrap()).unwrap();


            //test:


            //start keygen for all 4 peers
            println!("keygen test: starting peers");

            //0
            let ph0_path = phonebook_path.clone();
            let id0_path = "test_k_dir/identities/0".parse().unwrap();
            let out0_path = "test_k_dir/bls_keys/0".parse().unwrap();
            let h0 = tokio::spawn( async move {
                let (noiseAE, in_stream, out_sink) = connect_p2p(ph0_path, id0_path, 0).await.unwrap();
                keygen(in_stream, out_sink, 4, 2, (noiseAE.local_id() + 1), out0_path).await.unwrap();
            });

            //1
            let ph1_path = phonebook_path.clone();
            let id1_path = "test_k_dir/identities/1".parse().unwrap();
            let out1_path = "test_k_dir/bls_keys/1".parse().unwrap();
            let h1 = tokio::spawn( async move {
                let (noiseAE, in_stream, out_sink) = connect_p2p(ph1_path, id1_path, 0).await.unwrap();
                keygen(in_stream, out_sink, 4, 2, (noiseAE.local_id() + 1), out1_path).await.unwrap();
            });

            //2
            let ph2_path = phonebook_path.clone();
            let id2_path = "test_k_dir/identities/2".parse().unwrap();
            let out2_path = "test_k_dir/bls_keys/2".parse().unwrap();
            let h2 = tokio::spawn( async move {
                let (noiseAE, in_stream, out_sink) = connect_p2p(ph2_path, id2_path, 0).await.unwrap();
                keygen(in_stream, out_sink, 4, 2, (noiseAE.local_id() + 1), out2_path).await.unwrap();
            });

            //3
            let ph3_path = phonebook_path.clone();
            let id3_path = "test_k_dir/identities/3".parse().unwrap();
            let out3_path = "test_k_dir/bls_keys/3".parse().unwrap();
            let h3 = tokio::spawn( async move {
                let (noiseAE, in_stream, out_sink) = connect_p2p(ph3_path, id3_path, 0).await.unwrap();
                keygen(in_stream, out_sink, 4, 2, (noiseAE.local_id() + 1), out3_path).await.unwrap();
            });


            //sleep(Duration::from_secs(10));


            //wait for protocol to finish
            h0.await.unwrap();
            h1.await.unwrap();
            h2.await.unwrap();
            h3.await.unwrap();

            //TODO: check if bls keys were generated correctly (they _should_ have been if no error occurred above)
        });
    }

    #[test]
    fn test_signing() {
        //keygen must have been successful for this thest to pass

        //some bits to sign
        let test_digest: Vec<u8> = vec![69; 32];


        // Build async runtime
        let mut runtime = tokio::runtime::Builder::new_multi_thread();

        runtime.enable_all();

        /*
        if let Some(t) = app.threads {
            runtime.worker_threads(t);
        }
        */

        let runtime = match runtime.build() {
            Ok(r) => r,
            Err(e) => {
                println!("Failed to build async runtime: {}", e);
                exit(1)
            }
        };

        let result = runtime.block_on(async {

            //setup:

            let phonebook_path: String = "test_k_dir/phonebook".parse().unwrap();

            //test:


            //start signing for all 4 peers
            println!("signing test: starting peers");

            let mut signature: BLSSignature;

            //0
            let ph0_path = phonebook_path.clone();
            let id0_path = "test_k_dir/identities/0".parse().unwrap();
            let pk0_path = "test_k_dir/bls_keys/0".parse().unwrap();
            let td0 = test_digest.clone();
            let h0 = tokio::spawn( async move {
                let (noiseAE, in_stream, out_sink) = connect_p2p(ph0_path, id0_path, 0).await.unwrap();
                let loc_key = read_bls_keys(pk0_path).await.unwrap();
                let sig = bls_sign(in_stream, out_sink, td0, (noiseAE.local_id() + 1), 4, loc_key).await.unwrap();
                println!("Signature: {:?}", sig);
                return sig;
            });

            //1
            let ph1_path = phonebook_path.clone();
            let id1_path = "test_k_dir/identities/1".parse().unwrap();
            let pk1_path = "test_k_dir/bls_keys/1".parse().unwrap();
            let td1 = test_digest.clone();
            let h1 = tokio::spawn( async move {
                let (noiseAE, in_stream, out_sink) = connect_p2p(ph1_path, id1_path, 0).await.unwrap();
                let loc_key = read_bls_keys(pk1_path).await.unwrap();
                let sig = bls_sign(in_stream, out_sink, td1, (noiseAE.local_id() + 1), 4, loc_key).await.unwrap();
                println!("Signature: {:?}", sig);
            });

            //2
            let ph2_path = phonebook_path.clone();
            let id2_path = "test_k_dir/identities/2".parse().unwrap();
            let pk2_path = "test_k_dir/bls_keys/2".parse().unwrap();
            let td2 = test_digest.clone();
            let h2 = tokio::spawn( async move {
                let (noiseAE, in_stream, out_sink) = connect_p2p(ph2_path, id2_path, 0).await.unwrap();
                let loc_key = read_bls_keys(pk2_path).await.unwrap();
                let sig = bls_sign(in_stream, out_sink, td2, (noiseAE.local_id() + 1), 4, loc_key).await.unwrap();
                println!("Signature: {:?}", sig);
            });

            //3
            let ph3_path = phonebook_path.clone();
            let id3_path = "test_k_dir/identities/3".parse().unwrap();
            let pk3_path = "test_k_dir/bls_keys/3".parse().unwrap();
            let td3 = test_digest.clone();
            let h3 = tokio::spawn( async move {
                let (noiseAE, in_stream, out_sink) = connect_p2p(ph3_path, id3_path, 0).await.unwrap();
                let loc_key = read_bls_keys(pk3_path).await.unwrap();
                let sig = bls_sign(in_stream, out_sink, td3, (noiseAE.local_id() + 1), 4, loc_key).await.unwrap();
                println!("Signature: {:?}", sig);
            });


            //wait for protocol to finish
            signature = h0.await.unwrap();
            h1.await.unwrap();
            h2.await.unwrap();
            h3.await.unwrap();


            //verify signature
            let lk = read_bls_keys("test_k_dir/bls_keys/0".parse().unwrap()).await.unwrap();
            let public_key = curv::elliptic::curves::traits::ECPoint::pk_to_key_slice(&lk.public_key());
            let signature = curv::elliptic::curves::traits::ECPoint::pk_to_key_slice(&signature.sigma);
            let ver = verify(hex::encode(public_key.clone()), hex::encode(signature.clone()), hex::encode(test_digest.clone())).unwrap();

            assert_eq!(ver, true);
            println!("Signature valid: {}", ver);

            //test wrong signature
            let alt_digest = vec![42, 32];
            let ver2 = verify(hex::encode(public_key), hex::encode(signature), hex::encode(alt_digest)).unwrap();

            assert_eq!(ver2, false);
            println!("invalid signature verification result: {}", ver2);
        });
    }

    #[test]
    fn test_sign_ext() {
        // Build async runtime
        let mut runtime = tokio::runtime::Builder::new_multi_thread();

        runtime.enable_all();

        let runtime = match runtime.build() {
            Ok(r) => r,
            Err(e) => {
                println!("Failed to build async runtime: {}", e);
                exit(1)
            }
        };

        let result = runtime.block_on(async {
            //setup:
            //bls key paths
            let blskp0 = "test_k_dir/bls_keys/0".parse().unwrap();
            let blskp1 = "test_k_dir/bls_keys/1".parse().unwrap();
            let blskp2 = "test_k_dir/bls_keys/2".parse().unwrap();

            //id structs
            let pid0 = p2p_noise::p2pNoiseAE::read_identity("test_k_dir/identities/0".parse().unwrap()).unwrap();
            let pid1 = p2p_noise::p2pNoiseAE::read_identity("test_k_dir/identities/1".parse().unwrap()).unwrap();
            let pid2 = p2p_noise::p2pNoiseAE::read_identity("test_k_dir/identities/2".parse().unwrap()).unwrap();

            let verification_keys = read_bls_keys("test_k_dir/bls_keys/0".parse().unwrap()).await.unwrap().vk_vec;

            //message to be signed:
            let msg: Vec<u8> = vec![69; 32];

            let keys0 = read_bls_keys(blskp0).await.unwrap();
            let keys1 = read_bls_keys(blskp1).await.unwrap();
            let keys2 = read_bls_keys(blskp2).await.unwrap();

            //start 3 peers
            tokio::spawn(async move {
                let p0 = bls_sign_service_ext(keys0, pid0.listen_addr).await.unwrap();
            });
            tokio::spawn(async move {
                let p1 = bls_sign_service_ext(keys1, pid1.listen_addr).await.unwrap();
            });
            tokio::spawn(async move {
                let p2 = bls_sign_service_ext(keys2, pid2.listen_addr).await.unwrap();
            });

            //start requester
            let phonebook = p2p_noise::p2pNoiseAE::read_phonebook("test_k_dir/phonebook".parse().unwrap()).unwrap();
            let sig = request_sig_ext(2, 4, verification_keys, phonebook, msg.clone()).await.unwrap();

            println!("Signature: {:?}", sig);


            //verify signature
            let lk = read_bls_keys("test_k_dir/bls_keys/0".parse().unwrap()).await.unwrap();
            let public_key = curv::elliptic::curves::traits::ECPoint::pk_to_key_slice(&lk.public_key());
            let signature = curv::elliptic::curves::traits::ECPoint::pk_to_key_slice(&sig.sigma);
            let ver = verify(hex::encode(public_key.clone()), hex::encode(signature.clone()), hex::encode(msg.clone())).unwrap();

            assert_eq!(ver, true);
            println!("Signature valid: {}", ver);
        });
    }

    #[test]
    fn test_sign_ext_and_aggregator_service() {
        // Build async runtime
        let mut runtime = tokio::runtime::Builder::new_multi_thread();

        runtime.enable_all();

        let runtime = match runtime.build() {
            Ok(r) => r,
            Err(e) => {
                println!("Failed to build async runtime: {}", e);
                exit(1)
            }
        };

        let result = runtime.block_on(async {
            //setup:
            //bls key paths
            let blskp0 = "test_k_dir/bls_keys/0".parse().unwrap();
            let blskp1 = "test_k_dir/bls_keys/1".parse().unwrap();
            let blskp2 = "test_k_dir/bls_keys/2".parse().unwrap();

            //id structs
            let pid0 = p2p_noise::p2pNoiseAE::read_identity("test_k_dir/identities/0".parse().unwrap()).unwrap();
            let pid1 = p2p_noise::p2pNoiseAE::read_identity("test_k_dir/identities/1".parse().unwrap()).unwrap();
            let pid2 = p2p_noise::p2pNoiseAE::read_identity("test_k_dir/identities/2".parse().unwrap()).unwrap();

            let verification_keys = read_bls_keys("test_k_dir/bls_keys/0".parse().unwrap()).await.unwrap().vk_vec;

            //message to be signed:
            let msg: Vec<u8> = vec![69; 32];

            let keys0 = read_bls_keys(blskp0).await.unwrap();
            let keys1 = read_bls_keys(blskp1).await.unwrap();
            let keys2 = read_bls_keys(blskp2).await.unwrap();

            //aggregator listen address
            let agg_rx_addr = "127.0.0.1:42069".parse::<SocketAddr>().unwrap();

            let phonebook = p2p_noise::p2pNoiseAE::read_phonebook("test_k_dir/phonebook".parse().unwrap()).unwrap();

            //start 3 peers
            let agg_rx_addr_clone = agg_rx_addr.clone();
            let phonebook_clone = phonebook.clone();
            tokio::spawn(async move {
                let p0 = sign_and_aggregate_service(keys0, pid0.listen_addr, agg_rx_addr_clone, phonebook_clone).await.unwrap();
                //let p0 = bls_sign_service_ext(keys0, pid0.listen_addr).await.unwrap();
            });
            tokio::spawn(async move {
                let p1 = bls_sign_service_ext(keys1, pid1.listen_addr).await.unwrap();
            });
            tokio::spawn(async move {
                let p2 = bls_sign_service_ext(keys2, pid2.listen_addr).await.unwrap();
            });

            sleep(Duration::from_secs(1));

            //start requester
            let sig = request_sig_from_aggregator_service(agg_rx_addr, msg.clone()).await.unwrap();
            //let sig = request_sig_ext(2, 4, verification_keys, phonebook, msg.clone()).await.unwrap();


            println!("Signature: {}", hex::encode(sig.clone()));


            //verify signature
            let lk = read_bls_keys("test_k_dir/bls_keys/0".parse().unwrap()).await.unwrap();
            let public_key = curv::elliptic::curves::traits::ECPoint::pk_to_key_slice(&lk.public_key());
            let ver = verify(hex::encode(public_key.clone()), hex::encode(sig.clone()), hex::encode(msg.clone())).unwrap();

            assert_eq!(ver, true);
            println!("Signature valid: {}", ver);
        });
    }
}
