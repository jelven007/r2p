use r2p::prelude::*;

fn main() {
    Python::attach(|py| {
        let any = py.None().into_bound(py);
        any.call1("foo");
//~^ ERROR: `&str` cannot used as a Python `call` argument
    })
}
