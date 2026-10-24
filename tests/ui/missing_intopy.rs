//@revisions: default nostd inspect
//@[default,nostd] no-experimental-inspect
//@[inspect] with-experimental-inspect
//@[default,inspect] with-std
//@[nostd] no-std

struct Blah;

#[r2p::pyfunction]
fn blah() -> Blah {
    //~^ ERROR: `Blah` cannot be converted to a Python object
    //~[inspect]| ERROR: the trait bound `Blah: r2p::impl_::introspection::return_type::Sealed` is not satisfied
    Blah
}

fn main() {}
