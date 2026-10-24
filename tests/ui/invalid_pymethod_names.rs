use r2p::prelude::*;

#[pyclass]
struct TestClass {
    num: u32,
}

#[pymethods]
impl TestClass {
    #[r2p(name = "num")]
    #[getter(number)]
//~^ ERROR: `name` may only be specified once
    fn get_num(&self) -> u32 { self.num }
}

#[pymethods]
impl TestClass {
    #[r2p(name = "foo")]
    #[r2p(name = "bar")]
//~^ ERROR: `name` may only be specified once
    fn qux(&self) -> u32 { self.num }
}

#[pymethods]
impl TestClass {
    #[r2p(name = "makenew")]
//~^ ERROR: `name` not allowed with `#[new]`
    #[new]
    fn new(&self) -> Self { Self { num: 0 } }
}

#[pymethods]
impl TestClass {
    #[getter(1)]
//~^ ERROR: expected ident or string literal for property name
    fn get_one(&self) -> Self { Self { num: 0 } }
}

#[pymethods]
impl TestClass {
    #[getter = 1]
//~^ ERROR: expected `#[getter(name)]` to set the name
    fn get_two(&self) -> Self { Self { num: 0 } }
}


fn main() {}
