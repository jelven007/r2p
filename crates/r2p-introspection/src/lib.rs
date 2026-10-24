//! Utilities to introspect cdylib built using r2p and generate [type stubs](https://typing.readthedocs.io/en/latest/source/stubs.html).

pub use crate::introspection::introspect_cdylib;
pub use crate::stubs::module_stub_files;

mod introspection;
pub mod model;
mod stubs;
