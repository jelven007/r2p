#![allow(unused_imports)]

use r2p::prelude::*;

#[pyfunction]
fn foo() -> usize {
    0
}

#[pymodule]
mod module {
    #[pymodule_export]
    use super::*;
//~^ ERROR: #[pymodule] cannot import glob statements
}

fn main() {}
