//@revisions: default nostd inspect
//@[default,nostd] no-experimental-inspect
//@[inspect] with-experimental-inspect
//@[default,inspect] with-std
//@[nostd] no-std

use r2p::prelude::*;

#[pyclass]
struct ClassWithGetter {}

#[pymethods]
impl ClassWithGetter {
    #[getter]
    fn getter_with_arg(&self, _py: Python<'_>, _index: u32) {}
    //~^ ERROR: getter function can only have one argument (of type r2p::Python)
}

#[pyclass]
struct ClassWithSetter {}

#[pymethods]
impl ClassWithSetter {
    #[setter]
    fn setter_with_no_arg(&mut self, _py: Python<'_>) {}
    //~^ ERROR: setter function expected to have one argument
}

#[pymethods]
impl ClassWithSetter {
    #[setter]
    fn setter_with_too_many_args(&mut self, _py: Python<'_>, _foo: u32, _bar: u32) {}
    //~^ ERROR: setter function can have at most two arguments ([r2p::Python,] and value)
}

#[pyclass]
struct TupleGetterSetterNoName(#[r2p(get, set)] i32);
//~^ ERROR: `get` and `set` with tuple struct fields require `name`

#[pyclass]
struct MultipleGet(#[r2p(get, get)] i32);
//~^ ERROR: `get` may only be specified once

#[pyclass]
struct MultipleSet(#[r2p(set, set)] i32);
//~^ ERROR: `set` may only be specified once

#[pyclass]
struct MultipleName(#[r2p(name = "foo", name = "bar")] i32);
//~^ ERROR: `name` may only be specified once

#[pyclass]
struct NameWithoutGetSet(#[r2p(name = "value")] i32);
//~^ ERROR: `name` is useless without `get` or `set`

#[pyclass]
struct InvalidGetterType {
    #[r2p(get)]
    value: ::std::marker::PhantomData<i32>,
    //~^ ERROR: `PhantomData<i32>` cannot be converted to a Python object
    //~[inspect]| ERROR: `PhantomData<i32>` cannot be converted to a Python object
}

fn main() {}
