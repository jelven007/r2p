//@check-pass
#![forbid(unsafe_code)]
#![forbid(unsafe_op_in_unsafe_fn)]

use r2p::*;

extern crate alloc;

#[path = "../../src/tests/hygiene/mod.rs"]
mod hygiene;

mod gh_4394 {
    use r2p::prelude::*;

    #[derive(Eq, Ord, PartialEq, PartialOrd, Clone)]
    #[pyclass(get_all)]
    pub struct VersionSpecifier {
        pub(crate) operator: Operator,
        pub(crate) version: Version,
    }

    #[derive(Eq, Ord, PartialEq, PartialOrd, Debug, Hash, Clone, Copy)]
    #[r2p::pyclass(eq, eq_int)]
    pub enum Operator {
        Equal,
    }

    #[derive(Clone, Eq, PartialEq, PartialOrd, Ord)]
    #[pyclass]
    pub struct Version;
}

#[pymodule]
mod from_py_with {
    use r2p::prelude::*;
    use r2p::types::PyBytes;

    fn bytes_from_py(bytes: &Bound<'_, PyAny>) -> PyResult<Vec<u8>> {
        Ok(bytes.cast::<PyBytes>()?.as_bytes().to_vec())
    }

    #[pyfunction]
    fn f(#[r2p(from_py_with = bytes_from_py)] _bytes: Vec<u8>) {}
}

fn main() {}
