use std::io;
use tracing_subscriber::filter::{EnvFilter, LevelFilter};

pub fn init() {
  init_with_level(LevelFilter::WARN);
}

pub fn init_with_level(level: LevelFilter) {
  // control logging via ENV variable (tres debugging filter)
  let filter = EnvFilter::from_env("TDF").add_directive(level.into());
  let _ = tracing_subscriber::fmt::Subscriber::builder().with_writer(io::stderr).with_env_filter(filter).compact().try_init();
}

pub fn debug_msg_string(m: &dyn std::fmt::Debug) -> String {
  let mut temp = format!("{:?}", m);
  temp.truncate(160);
  temp
}
