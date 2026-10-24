use r2p::prelude::*;
use r2p::types::PyType;

#[pyclass(generic)]
//~^ ERROR: duplicate definitions with name `__pymethod___class_getitem____`
//~| ERROR: duplicate definitions with name `__class_getitem__`
//~| ERROR: multiple applicable items in scope
//~| ERROR: multiple applicable items in scope
//~| ERROR: multiple applicable items in scope
struct ClassRedefinesClassGetItem {}

#[pymethods]
impl ClassRedefinesClassGetItem {
    #[new]
    fn new() -> ClassRedefinesClassGetItem {
        Self {}
    }

    #[classmethod]
    pub fn __class_getitem__(
        //~^ ERROR: multiple applicable items in scope
        //~| ERROR: multiple applicable items in scope
        cls: &Bound<'_, PyType>,
        key: &Bound<'_, PyAny>,
    ) -> PyResult<Py<PyAny>> {
        //~^ ERROR: multiple applicable items in scope
        r2p::types::PyGenericAlias::new(cls.py(), cls.as_any(), key)
        //~^ ERROR: mismatched types
    }
}

fn main() {}
