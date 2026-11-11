use std::env;

use util::config::Config;
use util::keys_file::generate_keys_files;

mod network;
mod protocol;
mod protocol_process;
mod supervisor;
mod util;

#[tokio::main]
async fn main() {
    let args: Vec<String> = env::args().collect();

    let keys_file_path_prefix = String::from("keys/keyfile");

    let config = Config::read(String::from("config.yaml")).unwrap();

    match (&args[1]).as_str() {
        "run" => {
            let self_index = &args[2];
            let self_index: u16 = self_index.parse::<u16>().unwrap();

            if self_index == 0 {
                supervisor::run(&config).await;
            } else {
                protocol_process::run(&config, self_index).await;
            }
        }
        "gen-keys" => {
            generate_keys_files(keys_file_path_prefix, config.num_players);
        }
        _ => {
            println!("Usage: [run $self_index | gen-keys]")
        }
    }
}
