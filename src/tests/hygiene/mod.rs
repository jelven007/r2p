// TODO https://github.com/PyO3/pyo3/issues/5487
#![allow(clippy::undocumented_unsafe_blocks)]
#![no_implicit_prelude]
#![allow(dead_code, unused_variables, clippy::unnecessary_wraps)]

// The modules in this test are used to check r2p macro expansion is hygienic. By locating the test
// inside the crate the global `::r2p` namespace is not available, so in combination with
// #[r2p(crate = "crate")] this validates that all macro expansion respects the setting.

mod misc;
mod pyclass;
mod pyfunction;
mod pymethods;
mod pymodule;
