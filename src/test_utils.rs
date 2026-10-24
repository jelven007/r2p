// Brings in `test_utils` from the `tests` directory
//
// to make that file function (lots of references to `r2p` within it) need
// re-bind `crate` as r2p
use crate as r2p;
include!("../tests/test_utils/mod.rs");
