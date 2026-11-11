# BLS

Major changes that have been introduced include:
1. Adding a client service (bench) to initiate DKG and Sign operations based on user parameters.
2. Accepting all message lengths which was restricted to only 32 bytes earlier.
3. Introduction of some optional inter-operation delays and restructuring of DKG to allow for client service integration.
4. For compatibility with Rust 1.76, rust-serialize version updated.