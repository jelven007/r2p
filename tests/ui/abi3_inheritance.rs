use r2p::exceptions::PyException;
use r2p::prelude::*;

#[pyclass(extends=PyException)]
//~^ ERROR: `PyException` cannot be subclassed
//~| ERROR: `PyException` cannot be subclassed
#[derive(Clone)]
struct MyException {
    code: u32,
}

fn main() {}
