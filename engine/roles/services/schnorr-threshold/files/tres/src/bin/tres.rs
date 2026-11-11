use std::collections::{BTreeMap, HashMap};
use std::error::Error;
use std::fs;
use std::panic;
use std::path::Path;
use std::path::PathBuf;
use std::process;
use std::sync::Arc;

use configparser::ini::Ini;
use structopt::StructOpt;
use tokio::runtime::{Builder, Runtime};

use tres::node::common::ID;
use tres::node::validator::TestMessageValidator;
use tres::node::*;
use tres::transport::{PublicKey, SecretKey};
use tres::util::config::*;
use tres::util::logging;

const DEFAULT_SECTION: &str = "default";

#[derive(Debug, StructOpt)]
#[structopt(about = "tres: Tamper-Resistant signaturE Service (based on FROST)")]
struct CliArgs {
  // triple-slash comments are documentation comments
  /// INI-style config file
  #[structopt(parse(from_os_str), short = "c", default_value = "tres.cfg")]
  config_file: PathBuf,
  #[structopt(subcommand)]
  command: Option<Command>, // optional subcommand, defaults to run
}

#[derive(Debug, StructOpt)]
enum Command {
  /// Channel KeyGen - generate local keypair for the protected communication channel between nodes.
  /// You have to do this on every node and then distribute the public keys.
  Ckg {},
  /// the default - start up this peer
  Run {},
}

fn get_config(config: &HashMap<String, Option<String>>, key: &str, error_msg: &str) -> String {
  config.get(key).expect(error_msg).as_ref().unwrap().to_string()
}

#[rustfmt::skip]
fn get_local_id(config: &Ini) -> ID {
  config.get("default", "id").expect("Missing id").parse().expect("Local participant ID must not be negative!")
}

/// Generates new keys for the P2P commincation channel and stores them in the given files
fn channel_keygen(pubkey_file: &Path, seckey_file: &Path) -> Result<(PublicKey, SecretKey), Box<dyn Error>> {
  let (pubkey, seckey) = Node::new_channel_keypair();
  fs::write(&pubkey_file, &pubkey)?;
  fs::write(&seckey_file, &seckey)?;
  Ok((pubkey, seckey))
}

fn run(node: Arc<Node>, singlethread: bool) -> Result<(), Box<dyn Error>> {
  // MINOR: effect of .max_blocking_threads(1) ?
  let rt = if singlethread { Builder::new_current_thread().enable_all().build()? } else { Runtime::new()? };
  rt.block_on(node.run());
  Ok(())
}

// heap alloc in case we return an Error
fn main() -> Result<(), Box<dyn Error>> {
  logging::init();

  // kill whole program if one thread panics
  let existing_hook = panic::take_hook();
  panic::set_hook(Box::new(move |panic_info| {
    existing_hook(panic_info);
    process::exit(1);
  }));

  let args = CliArgs::from_args();
  let mut config = Ini::new();
  config.set_default_section(DEFAULT_SECTION);
  config.load(args.config_file.to_str().expect("Got bad file path!"))?;

  let id: ID = get_local_id(&config);
  #[rustfmt::skip]
  let addr = get_config(&config.get_map_ref()["default"],"addr","Missing local addr to listen on (addr=host:port)");
  let interface_addr = config.get("default", "interface");
  let section = &config.get_map_ref()["default"];
  let seckey_file = path_relative_to(&args.config_file, &get_config(section, "seckey", "Missing seckey=file path"))?;
  let pubkey_file = path_relative_to(&args.config_file, &get_config(section, "pubkey", "Missing pubkey=file path"))?;
  let singlethread = config.getboolcoerce(DEFAULT_SECTION, "singlethread").expect("Malformed option 'singlethread'").unwrap_or(false);

  match args.command {
    Some(Command::Ckg {}) => {
      channel_keygen(&pubkey_file, &seckey_file)?;
      Ok(())
    }
    _ => {
      let mut peers = BTreeMap::new();
      let mut config_file_base_path = args.config_file;
      config_file_base_path.pop();
      // build list of peers
      for (key, value) in config.get_map_ref() {
        if key != DEFAULT_SECTION {
          let mut peer_pubkey_file = config_file_base_path.clone();
          peer_pubkey_file.push(get_config(value, "pubkey", &format!("Missing pubkey=file path for peer {}", key)));

          if peer_pubkey_file.as_path().exists() {
            let peer_info = NodeInfo::new(get_config(value, "addr", &format!("No addr=host:port for peer {} configured", key)), fs::read(peer_pubkey_file)?);

            let peer_id = key.parse::<ID>().unwrap_or_else(|_| panic!("Bad peer ID '{}': not an unsigned int", key));
            let old = peers.insert(peer_id, peer_info);
            if old.is_some() || peer_id == id {
              // actually configparser does not return duplicates, but there's no explicit guarantee
              panic!("Duplicate node ID {}", key);
            }
          } else {
            println!("Warning: won't use configured peer {}, it's public key is missing.", key);
          }
        }
      }

      let (pubkey, seckey) = if seckey_file.as_path().exists() {
        (fs::read(&pubkey_file)?, fs::read(&seckey_file)?) // crash if only seckey but no pubkey exists
      } else {
        println!("{}: Secret key file does not exist, overwriting possibly existing sec/pub keys", id);
        channel_keygen(&pubkey_file, &seckey_file)?
      };
      let node = Node::new(id, addr, seckey, pubkey, peers, interface_addr, TestMessageValidator::new())?;

      run(node, singlethread)
    }
  }

  // async { tokio::signal::ctrl_c().await.expect("Could not create SIGINT handler"); // weirdly-named SIGINT
  // }
}
