use std::error::Error;
use std::path::PathBuf;

use configparser::ini::Ini;
use frost_dalek::signature;
use structopt::StructOpt;

use tres::client::*;
use tres::node::common::{CONTEXT, ID};
use tres::util::config::*;
use tres::util::keys::*;
use tres::util::logging;

#[derive(Debug, StructOpt)]
#[structopt(about = "trec: Tamper-Resistant signaturE service Client: send commands to the signature service")]
struct CliArgs {
  /// INI-style config file telling us where to connect to the signing interface
  #[structopt(parse(from_os_str), short = "c", default_value = "config/client.cfg")]
  config_file: PathBuf,
  #[structopt(subcommand)]
  command: Command,
}

#[derive(Debug, StructOpt)]
enum Command {
  /// Start distributed key generation
  Dkg {
    /// the threshold number of nodes needed for a signature
    #[structopt(short, index = 1)] // set index to get a positional arg
    t: ID,
  },
  Preprocess {
    /// number of nonce pairs to generate for signing
    #[structopt(short, index = 1)]
    n: usize,
  },
  Sign {
    /// pass message to sign
    #[structopt(short, index = 1)]
    msg: String,
  },
}

fn main() -> Result<(), Box<dyn Error>> {
  logging::init();

  // heap alloc in case we return an Error
  let args = CliArgs::from_args();
  let mut config = Ini::new();
  config.load(args.config_file.to_str().expect("Got bad file path!"))?;

  let interface_addr = config.get("default", "interface").expect("Missing 'interface' to talk to!");
  let group_key_file = config.get("default", "group_key").expect("Missing 'group_key' path!");
  let group_key_file = path_relative_to(&args.config_file, &group_key_file)?;

  let rt = tokio::runtime::Runtime::new().unwrap();
  rt.block_on(async {
    let client = Client::new(interface_addr).await.expect("Error initializing client");

    match args.command {
      Command::Dkg { t } => {
        let group_key = {
          match client.initiate_dkg(&t).await {
            Ok(gk) => gk,
            Err(err) => panic!("{}", err),
          }
        };

        match write_group_key(&group_key_file, group_key) {
          Ok(_) => println!("Saved group key to file for later use"),
          Err(err) => panic!("Error saving group key: {}", err),
        }
      }
      Command::Preprocess { n } => match client.initiate_preprocessing(n).await {
        Ok(()) => {}
        Err(err) => panic!("{}", err),
      },
      Command::Sign { msg } => {
        let message_hash = signature::compute_message_hash(CONTEXT, msg.as_bytes());
        let threshold_sig = {
          match client.initiate_signing(msg).await {
            Ok(sig) => sig,
            Err(err) => panic!("Signing request error: {}", err),
          }
        };
        println!("Signature: {}", hex::encode(threshold_sig.to_bytes()));

        let group_key = {
          match read_group_key(&group_key_file) {
            Ok(gk) => Some(gk),
            Err(err) => {
              eprintln!("Error loading group key: {}", err);
              None
            }
          }
        };

        if let Some(group_key) = group_key {
          match threshold_sig.verify(&group_key, &message_hash) {
            Ok(()) => println!("Signature ok"),
            Err(err) => panic!("Signature NOT ok: {:?}", err),
          }
        }
      }
    }
  });

  Ok(())
}
