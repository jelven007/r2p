//! Example of custom annotations.

use r2p::prelude::*;

#[pymodule]
pub mod annotations {
    use crate::pyclasses::EmptyClass;
    use r2p::prelude::*;
    use r2p::types::{PyDict, PyTuple};

    #[pyfunction(signature = (a: "list[int]", *_args: "str", _b: "int | None" = None, **_kwargs: "bool") -> "int")]
    fn with_custom_type_annotations<'py>(
        a: Bound<'py, PyAny>,
        _args: Bound<'py, PyTuple>,
        _b: Option<Bound<'py, PyAny>>,
        _kwargs: Option<Bound<'py, PyDict>>,
    ) -> Bound<'py, PyAny> {
        a
    }

    #[pyfunction]
    fn cross_module_imports(_a: &EmptyClass) {}
}
