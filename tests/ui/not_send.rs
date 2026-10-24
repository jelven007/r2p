
use r2p::prelude::*;

fn test_not_send_detach(py: Python<'_>) {
    py.detach(|| drop(py));
    //~^ ERROR: `*mut r2p::Python<'static>` cannot be shared between threads safely
}

fn main() {
    Python::attach(|py| {
        test_not_send_detach(py);
    })
}
