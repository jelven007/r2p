use r2p::prelude::*;

#[pyfunction]
fn invalid_attribute(#[r2p(get)] _param: String) {}
//~^ ERROR: expected `cancel_handle` or `from_py_with`

#[pyfunction]
fn from_py_with_no_value(#[r2p(from_py_with)] _param: String) {}
//~^ ERROR: expected `=`

#[pyfunction]
fn from_py_with_string(#[r2p("from_py_with")] _param: String) {}
//~^ ERROR: expected `cancel_handle` or `from_py_with`

#[pyfunction]
fn from_py_with_value_not_found(#[r2p(from_py_with = func)] _param: String) {}

#[pyfunction]
fn from_py_with_repeated(#[r2p(from_py_with = func, from_py_with = func)] _param: String) {}
//~^ ERROR: `from_py_with` may only be specified once per argument

fn bytes_from_py(bytes: &Bound<'_, r2p::types::PyBytes>) -> Vec<u8> {
    bytes.as_bytes().to_vec()
}

#[pyfunction]
fn f(#[r2p(from_py_with = "bytes_from_py")] _bytes: Vec<u8>) {}
//~^ ERROR: expected identifier

fn main() {}
