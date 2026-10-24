use r2p::prelude::*;

#[pyclass]
struct WarningMethodContainer {}

#[pymethods]
impl WarningMethodContainer {
    #[r2p(warn(message = "warn on __traverse__"))]
//~^ ERROR: __traverse__ cannot be used with #[r2p(warn)]
    fn __traverse__(&self) {}
}

#[pymethods]
impl WarningMethodContainer {
    #[classattr]
    #[r2p(warn(message = "warn for class attr"))]
//~^ ERROR: #[classattr] cannot be used with #[r2p(warn)]
    fn a_class_attr(_py: r2p::Python<'_>) -> i64 {
        5
    }
}

fn main() {}
