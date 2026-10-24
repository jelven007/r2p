use r2p::Python;

fn main() {
    let _foo = if true { "foo" } else { "bar" };
    Python::attach(|py| py.import(r2p::intern!(py, _foo)).unwrap().unbind());
    //~^ ERROR: attempt to use a non-constant value in a constant
}
