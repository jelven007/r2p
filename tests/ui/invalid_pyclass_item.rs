use r2p::prelude::*;

#[pyclass]
fn foo() {}
//~^ ERROR: #[pyclass] only supports structs and enums.

fn main() {}
