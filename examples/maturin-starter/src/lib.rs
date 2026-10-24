use r2p::prelude::*;
use r2p::types::PyDict;
use r2p::wrap_pymodule;

mod submodule;

#[pyclass]
struct ExampleClass {
    #[r2p(get, set)]
    value: i32,
}

#[pymethods]
impl ExampleClass {
    #[new]
    pub fn new(value: i32) -> Self {
        ExampleClass { value }
    }
}

/// An example module implemented in Rust using r2p.
#[pymodule]
fn maturin_starter(py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<ExampleClass>()?;
    m.add_wrapped(wrap_pymodule!(submodule::submodule))?;

    // Inserting to sys.modules allows importing submodules nicely from Python
    // e.g. from maturin_starter.submodule import SubmoduleClass

    let sys = PyModule::import(py, "sys")?;
    let sys_modules: Bound<'_, PyDict> = sys.getattr("modules")?.cast_into()?;
    sys_modules.set_item("maturin_starter.submodule", m.getattr("submodule")?)?;

    Ok(())
}
