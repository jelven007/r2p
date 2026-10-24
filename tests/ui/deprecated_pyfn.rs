#![deny(deprecated)]

use r2p::prelude::*;

#[pymodule]
fn module_with_pyfn(m: &Bound<'_, PyModule>) -> PyResult<()> {
    #[pyfn(m)]
//~^ ERROR: use of deprecated constant `module_with_pyfn::PYFN_ATTRIBUTE`: `pyfn` will be removed in a future r2p version, use declarative `#[pymodule]` with `mod` instead
    fn foo() {}

    Ok(())
}

fn main() {}
