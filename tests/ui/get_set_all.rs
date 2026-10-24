use r2p::prelude::*;

#[pyclass(set_all)]
//~^ ERROR: `set_all` on an unit struct does nothing, because unit structs have no fields
struct Foo;

#[pyclass(set_all)]
struct Foo2{
    #[r2p(set)]
//~^ ERROR: useless `set` - the struct is already annotated with `set_all`
    field: u8,
}

#[pyclass(get_all)]
//~^ ERROR: `get_all` on an unit struct does nothing, because unit structs have no fields
struct Foo3;

#[pyclass(get_all)]
struct Foo4{
    #[r2p(get)]
//~^ ERROR: useless `get` - the struct is already annotated with `get_all`
    field: u8,
}

fn main() {}
