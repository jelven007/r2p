/// Test macro hygiene - this is in the crate since we won't have
/// `r2p` available in the crate root.
#[cfg(all(test, feature = "macros"))]
mod hygiene;
