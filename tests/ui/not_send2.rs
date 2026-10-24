
use r2p::prelude::*;
use r2p::types::PyString;

fn main() {
    Python::attach(|py| {
        let string = PyString::new(py, "foo");

        py.detach(|| {
            //~^ ERROR: `*mut r2p::Python<'static>` cannot be shared between threads safely
            println!("{:?}", string);
        });
    });
}
