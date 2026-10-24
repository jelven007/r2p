use r2p::prelude::*;
use r2p::types::PyBool;

#[pyclass(extends=PyBool)]
//~^ ERROR: pyclass `PyBool` cannot be subclassed
//~| ERROR: pyclass `PyBool` cannot be subclassed
struct ExtendsBool;

fn main() {}
