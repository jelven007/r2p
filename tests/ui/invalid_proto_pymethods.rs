//! Check that some magic methods edge cases error as expected.
//!
//! For convenience use #[r2p(name = "__some_dunder__")] to create the methods,
//! so that the function names can describe the edge case to be rejected.

use r2p::prelude::*;
use r2p::pyclass::CompareOp;

#[pyclass]
struct MyClass {}

//
// Argument counts
//

#[pymethods]
impl MyClass {
    #[r2p(name = "__truediv__")]
    fn truediv_expects_one_argument(&self) -> PyResult<()> {
//~^ ERROR: Expected 1 arguments, got 0
        Ok(())
    }
}

#[pymethods]
impl MyClass {
    #[r2p(name = "__truediv__")]
    fn truediv_expects_one_argument_py(&self, _py: Python<'_>) -> PyResult<()> {
//~^ ERROR: Expected 1 arguments, got 0
        Ok(())
    }
}

//
// Forbidden attributes
//

#[pymethods]
impl MyClass {
    #[r2p(name = "__bool__", signature = ())]
//~^ ERROR: `signature` cannot be used with magic method `__bool__`
    fn signature_is_forbidden(&self) -> bool {
        true
    }
}

#[pymethods]
impl MyClass {
    #[r2p(name = "__bool__", text_signature = "")]
//~^ ERROR: `text_signature` cannot be used with magic method `__bool__`
    fn text_signature_is_forbidden(&self) -> bool {
        true
    }
}

#[pyclass]
struct EqAndRichcmp;

#[pymethods]
//~^ ERROR: duplicate definitions with name `__pymethod___richcmp____`
//~| ERROR: multiple applicable items in scope
//~| ERROR: multiple applicable items in scope
impl EqAndRichcmp {
    fn __eq__(&self, _other: &Self) -> bool {
        true
    }

    fn __richcmp__(&self, _other: &Self, _op: CompareOp) -> bool {
        true
    }
}

fn main() {}
