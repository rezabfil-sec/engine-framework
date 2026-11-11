use std::error::Error;
use std::path::Path;
use std::path::PathBuf;

/// Use the directory of the config file as a basedir and return resulting path
pub fn path_relative_to(root_file: &Path, path: &str) -> Result<PathBuf, Box<dyn Error>> {
  let mut relative_path = root_file.to_path_buf();
  relative_path.pop(); // get base path
  relative_path.push(path);
  Ok(relative_path)
}
