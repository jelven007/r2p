use r2p::prelude::*;

#[pyfunction]
async fn cancel_handle_repeated(#[r2p(cancel_handle, cancel_handle)] _param: String) {}
//~^ ERROR: `cancel_handle` may only be specified once per argument

#[pyfunction]
async fn cancel_handle_repeated2(
    #[r2p(cancel_handle)] _param: String,
    #[r2p(cancel_handle)] _param2: String,
    //~^ ERROR: `cancel_handle` may only be specified once
) {
}

#[pyfunction]
fn cancel_handle_synchronous(#[r2p(cancel_handle)] _param: String) {}
//~^ ERROR: `cancel_handle` attribute can only be used with `async fn`

#[pyfunction]
async fn cancel_handle_wrong_type(#[r2p(cancel_handle)] _param: String) {}
//~^ ERROR: mismatched types

#[pyfunction]
async fn missing_cancel_handle_attribute(_param: r2p::coroutine::CancelHandle) {}
//~^ ERROR: `CancelHandle` cannot be used as a Python function argument
//~| ERROR: `CancelHandle` cannot be used as a Python function argument

#[pyfunction]
async fn cancel_handle_and_from_py_with(
    #[r2p(cancel_handle, from_py_with = cancel_handle)] _param: r2p::coroutine::CancelHandle,
    //~^ ERROR: `from_py_with` and `cancel_handle` cannot be specified together
) {
}

fn main() {}
