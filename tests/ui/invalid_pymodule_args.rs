use r2p::prelude::*;

#[pymodule(some_arg)]
//~^ ERROR: expected one of: `name`, `crate`, `module`, `submodule`, `gil_used`
fn module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    Ok(())
}

#[r2p::pymodule(gil_used = false, gil_used = true, name = "foo", name = "bar")]
//~^ ERROR: `name` may only be specified once
//~| ERROR: `gil_used` may only be specified once
fn module_fn_multiple_errors(m: &Bound<'_, PyModule>) -> PyResult<()> {
    Ok(())
}

#[r2p::pymodule(gil_used = false, gil_used = true, name = "foo", name = "bar")]
//~^ ERROR: `name` may only be specified once
//~| ERROR: `gil_used` may only be specified once
mod r2p_module_multiple_errors {}

fn main() {}
