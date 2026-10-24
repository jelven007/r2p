use r2p::prelude::*;

#[pyclass]
struct InvalidInitReturn;

#[pymethods]
impl InvalidInitReturn {
    fn __init__(&self) -> i32 {
        //~^ ERROR: the trait bound `i32: r2p::impl_::callback::IntoPyCallbackOutput<'_, i32>` is not satisfied
        0
    }
}

fn main() {}
