//@check-pass
#![deny(missing_docs)]
//! Some crate docs

use r2p::prelude::*;

/// Some module documentation
#[pymodule]
pub fn python_module(_m: &Bound<'_, PyModule>) -> PyResult<()> {
    Ok(())
}

/// Some module documentation
#[pymodule]
pub mod declarative_python_module {}

fn main() {}
