# Dependencies

For Rust dependencies, see `Cargo.toml`.

#  Build/Test

    cargo b
    cargo t testnameOrNothingForAllTests

# Config

The used ports, files to store key material in, ... can be configured by config files.
Default config files can be generated via a script, e.g.,

    ./config/create-cfg.py -n 3

# Debugging

Output can be controlled via env:

    TDF="tres=info,tres::node=debug"
