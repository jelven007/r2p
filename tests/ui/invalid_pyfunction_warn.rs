use r2p::prelude::*;

#[pyfunction]
#[r2p(warn)]
//~^ ERROR: unexpected end of input, expected parentheses
fn no_parenthesis_deprecated() {}

#[pyfunction]
#[r2p(warn())]
//~^ ERROR: missing `message` in `warn` attribute
fn no_message_deprecated() {}

#[pyfunction]
#[r2p(warn(category = r2p::exceptions::PyDeprecationWarning))]
//~^ ERROR: missing `message` in `warn` attribute
fn no_message_deprecated_with_category() {}

#[pyfunction]
#[r2p(warn(category = r2p::exceptions::PyDeprecationWarning, message = ,))]
//~^ ERROR: expected string literal
fn empty_message_deprecated_with_category() {}

#[pyfunction]
#[r2p(warn(message = "deprecated function", category = ,))]
//~^ ERROR: expected identifier
fn empty_category_deprecated_with_message() {}

#[pyfunction]
#[r2p(warn(message = "deprecated function", random_key))]
//~^ ERROR: expected `message` or `category`
fn random_key_deprecated() {}

#[pyclass]
struct DeprecatedMethodContainer {}

#[pymethods]
impl DeprecatedMethodContainer {
    #[classattr]
    #[r2p(warn(message = "deprecated class attr"))]
//~^ ERROR: #[classattr] cannot be used with #[r2p(warn)]
    fn deprecated_class_attr() -> i32 {
        5
    }
}

#[pymethods]
impl DeprecatedMethodContainer {
    #[r2p(warn(message = "deprecated __traverse__"))]
//~^ ERROR: __traverse__ cannot be used with #[r2p(warn)]
    fn __traverse__(&self, _visit: r2p::gc::PyVisit<'_>) -> Result<(), r2p::PyTraverseError> {
        Ok(())
    }
}

fn main() {}
