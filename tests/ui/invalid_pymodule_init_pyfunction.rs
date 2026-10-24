use r2p::prelude::*;

#[pymodule]
mod module {
    use r2p::prelude::*;

    #[pymodule_init]
    #[pyfunction]
//~^ ERROR: `#[pyfunction]` cannot be used alongside `#[pymodule_init]`
    fn init(_m: &Bound<'_, PyModule>) -> PyResult<()> {
        Ok(())
    }
}

fn main() {}
