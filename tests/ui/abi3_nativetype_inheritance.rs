//! With abi3, we cannot inherit native types.
use r2p::prelude::*;
use r2p::types::PyDict;

#[pyclass(extends=PyDict)]
//~^ ERROR: `PyDict` cannot be subclassed
//~| ERROR: `PyDict` cannot be subclassed
struct TestClass {}

fn main() {}
