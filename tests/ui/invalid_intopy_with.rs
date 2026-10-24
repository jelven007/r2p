use r2p::{IntoPyObject, IntoPyObjectRef};

#[derive(IntoPyObject, IntoPyObjectRef)]
struct InvalidIntoPyWithFn {
    #[r2p(into_py_with = into)]
//~^ ERROR: mismatched types
//~| ERROR: mismatched types
    inner: String,
}

fn into(_a: String, _py: r2p::Python<'_>) -> r2p::PyResult<r2p::Bound<'_, r2p::PyAny>> {
    todo!()
}

fn main() {}
