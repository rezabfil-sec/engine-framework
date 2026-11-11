// Common defs needed by the client and other components

/// Context string to ensure that the signature verifier does not confuse the context of the signature
pub const CONTEXT: &[u8] = b"CONTEXT STRING: TRES: Tamper-Resistant signaturE Service based on FROST";

/// Participant index. frost_dalek requires that 0 is an invalid participant index
pub type ID = u32;
