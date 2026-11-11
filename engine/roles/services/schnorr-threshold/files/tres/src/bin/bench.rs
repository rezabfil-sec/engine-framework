use std::error::Error;
use std::fmt;
use std::fs::File;
use std::io::Write;
use std::path::PathBuf;

use configparser::ini::Ini;
use frost_dalek::keygen::GroupKey;
use frost_dalek::signature;
use frost_dalek::signature::ThresholdSignature;
use rand::distributions::{Alphanumeric, Distribution};
use rand::rngs::SmallRng; // PRNG for message generation
use rand::SeedableRng;
use tracing::error; // trace debug info warn

use std::path::Path;
use std::time::{Duration, Instant};
use structopt::StructOpt;

use tres::client::*;
use tres::node::common::{CONTEXT, ID};
use tres::util::logging;

#[derive(Debug, StructOpt)]
#[structopt(about = "treb: Tamper-Resistant signaturE service Benchmark: performance measurements")]
struct CliArgs {
  /// INI-style config file telling us where to connect to the signing interface
  #[structopt(parse(from_os_str), short = "c", default_value = "config/client.cfg")]
  config_file: PathBuf,
  /// threshold for signature generation. "n" is set implicitely by the number of nodes running.
  t: ID,
  /// CSV file to store the results in. Will be truncated and created if nonexistent.
  #[structopt(parse(from_os_str))]
  resultsfile: PathBuf,
  /// iteration count
  iterations: usize,
  #[structopt(subcommand)]
  command: Command,
}

#[derive(Debug, StructOpt)]
enum Command {
  /// Measure distributed key generation
  Dkg {},
  /// Measure preprocessing phase
  Preprocess {
    /// number of nonce pairs to generate for signing
    #[structopt(short, index = 1)]
    num_noncepairs: usize,
  },
  /// Measure signing performance
  Sign {
    /// length of the message to be signed
    #[structopt(short, index = 1)]
    msglen: usize,
  },
}

fn run() -> Result<i32, Box<dyn Error>> {
  logging::init();

  // heap alloc in case we return an Error
  let args = CliArgs::from_args();
  let mut config = Ini::new();
  config.load(args.config_file.to_str().expect("Got bad file path!"))?;

  let interface_addr = config.get("default", "interface").expect("Missing 'interface' to talk to!");

  let rt = tokio::runtime::Runtime::new().unwrap();
  Ok(rt.block_on(async {
    let client = Client::new(interface_addr).await.expect("Error initializing client");
    let number_of_nodes = client.get_n().await.expect("Error getting number of nodes");
    let mut bench = Benchmark::new(args, client, number_of_nodes);

    let interfaceaddrs = config.get_map_ref().iter().filter(|(section, _data)| *section != "default").map(|(section, data)| {
      let _ = section.parse::<ID>().unwrap_or_else(|_| panic!("Bad peer ID '{}': not an unsigned int", section));
      data["interface"].as_ref().expect("Benchmark requires that all nodes offer their HTTP interface")
    });

    bench.run(interfaceaddrs).await
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
  args: CliArgs,
  client: Client,
  aspect: Aspect,
  _number_of_nodes: ID,
}
/// Runs a benchmark and stores the result
impl Benchmark {
  fn new(args: CliArgs, mut client: Client, number_of_nodes: ID) -> Self {
    let aspect = match args.command {
      Command::Dkg {} => Aspect::Dkg(MeasureDkg::new(&args.iterations)),
      Command::Preprocess { num_noncepairs } => Aspect::Preprocess(MeasurePreprocessing::new(&args.iterations, num_noncepairs)),
      Command::Sign { msglen } => Aspect::Sign(MeasureSign::new(&args.iterations, msglen)),
    };
    client.allow_precise_measurements(true);
    Self { results: Vec::with_capacity(args.iterations), args, client, aspect, _number_of_nodes: number_of_nodes }
  }

  async fn run(&mut self, allnodeinterfaces: impl Iterator<Item = &String>) -> i32 {
    // wait till connected
    for addr in allnodeinterfaces {
      let client = Client::new(addr).await.expect("Error initializing client");
      client.peer_fully_connected().await.expect("Error waiting for client");
    }

    // prepare
    match &mut self.aspect {
      Aspect::Dkg(_) => {}
      Aspect::Preprocess(_) => {}
      Aspect::Sign(s) => s.prepare(self.args.t, &self.client).await,
    }

    for i in 0..self.results.capacity() {
      self.client.ready().await.expect("HTTP connection error");
      let duration = match &mut self.aspect {
        Aspect::Dkg(dkg) => dkg.run_one_iteration(self.args.t, &self.client).await,
        Aspect::Preprocess(p) => p.run_one_iteration(&self.client).await,
        Aspect::Sign(s) => s.run_one_iteration(&self.client).await,
      };
      println!("done {}", i);

      self.results.push(duration);
    }

    // check that results are ok
    let exitcode = match &mut self.aspect {
      Aspect::Dkg(dkg) => dkg.finish(),
      Aspect::Preprocess(a) => a.finish(),
      Aspect::Sign(s) => s.finish(&self.client).await,
    };

    self.write_to_file(&self.args.resultsfile);
    exitcode
  }

  fn write_to_file(&self, filename: &Path) {
    let mut f = File::create(filename).expect("Error opening file for writing");
    writeln!(f, "is_ok,run_id,duration_ns").expect("Error writing data");

    let mut is_ok_iter = match &self.aspect {
      Aspect::Dkg(d) => d.is_ok_iter(),
      Aspect::Preprocess(p) => p.is_ok_iter(),
      Aspect::Sign(s) => s.is_ok_iter(),
    };

    for (run_id, timing) in self.results.iter().enumerate() {
      let is_ok = is_ok_iter.next().expect("Error: inconsistent length of result data!");
      writeln!(f, "{},{},{}", is_ok, run_id, timing.as_nanos()).expect("Error writing data");
    }
  }
}

enum Aspect {
  Dkg(MeasureDkg),
  Preprocess(MeasurePreprocessing),
  Sign(MeasureSign),
}
impl fmt::Display for Aspect {
  fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
    match &*self {
      Aspect::Dkg(_) => write!(f, "dkg"),
      Aspect::Preprocess(a) => write!(f, "preprocess_nonces{}", a.num_noncepairs),
      Aspect::Sign(a) => write!(f, "sign_msglen{}", a.message.len()),
    }
  }
}

struct MeasureDkg {
  results: Vec<Result<GroupKey, Box<dyn Error>>>,
}
impl MeasureDkg {
  fn new(iteration_count: &usize) -> Self {
    Self { results: Vec::with_capacity(*iteration_count) }
  }

  /// Performs one DKG phase and returns the time it took
  async fn run_one_iteration(&mut self, t: ID, client: &Client) -> Duration {
    // TODO better error handling
    let now_before = Instant::now();
    let res = client.initiate_dkg(&t).await;
    let now_after = Instant::now();
    if let Err(ref err) = res {
      error!("DKG error: {}", err)
    }
    self.results.push(res);

    now_after.duration_since(now_before)
  }

  fn is_ok_iter<'s>(&'s self) -> Box<dyn Iterator<Item = bool> + 's> {
    Box::new(self.results.iter().map(|x| x.is_ok()))
  }

  fn finish(&self) -> i32 {
    let mut exitcode = 0;
    for res in &self.results {
      match res {
        Ok(_) => {}
        Err(_) => {
          exitcode = 2;
        }
      }
    }
    exitcode
  }
}

struct MeasurePreprocessing {
  results: Vec<Result<(), Box<dyn Error>>>,
  num_noncepairs: usize,
}
impl MeasurePreprocessing {
  fn new(iteration_count: &usize, num_noncepairs: usize) -> Self {
    Self { results: Vec::with_capacity(*iteration_count), num_noncepairs }
  }
  async fn run_one_iteration(&mut self, client: &Client) -> Duration {
    let now_before = Instant::now();
    let res = client.initiate_preprocessing(self.num_noncepairs).await;
    let now_after = Instant::now();
    if let Err(ref err) = res {
      error!("Preprocess error: {}", err)
    }
    self.results.push(res);

    now_after.duration_since(now_before)
  }

  fn is_ok_iter<'s>(&'s self) -> Box<dyn Iterator<Item = bool> + 's> {
    Box::new(self.results.iter().map(|x| x.is_ok()))
  }

  fn finish(&self) -> i32 {
    let mut exitcode = 0;
    for res in &self.results {
      match res {
        Ok(_) => {}
        Err(_) => {
          exitcode = 3;
        }
      }
    }
    exitcode
  }
}

struct MeasureSign {
  results: Vec<Result<ThresholdSignature, Box<dyn Error>>>,
  message: String,
  message_hash: [u8; 64],
}
impl MeasureSign {
  fn new(iteration_count: &usize, message_size: usize) -> Self {
    if message_size < 4 {
      panic!("Current message validation policy is: msg must have 'test' as a prefix!");
    }
    let mut rng = SmallRng::seed_from_u64(42); // generate pseudorandom message to sign
    let message: String = "test".chars().chain(Alphanumeric.sample_iter(&mut rng).take(message_size - 4).map(char::from)).collect();
    assert_eq!(message.len(), message_size);
    let message_hash = signature::compute_message_hash(CONTEXT, message.as_bytes());
    Self { results: Vec::with_capacity(*iteration_count), message, message_hash }
  }

  async fn prepare(&self, t: ID, client: &Client) {
    client.initiate_dkg(&t).await.expect("Error preparing 'Sign' benchmark: DKG failed");

    let res = client.initiate_preprocessing(self.results.capacity()).await;
    assert!(res.is_ok());
  }

  async fn run_one_iteration(&mut self, client: &Client) -> Duration {
    let msg = self.message.clone();
    let now_before = Instant::now();
    let res = client.initiate_signing(msg).await;
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

  /// verifies all signatures
  async fn finish(&self, client: &Client) -> i32 {
    let group_key = client.get_group_key().await.expect("Failed to get verification key");
    let mut exitcode = 0;

    for res in &self.results {
      match res {
        Ok(threshold_sig) => match threshold_sig.verify(&group_key, &self.message_hash) {
          Ok(()) => {}
          Err(err) => {
            exitcode = 5;
            error!("Signature NOT ok: {:?}", err)
          }
        },
        Err(_) => {
          exitcode = 4;
        }
      }
    }
    exitcode
  }
}
