# r2p SDK

r2p provides Rust bindings to Python. The SDK crate family is `r2p`,
`r2p-ffi`, `r2p-build-config`, `r2p-macros`, `r2p-macros-backend`, and
`r2p-introspection`. It is derived from PyO3; upstream copyrights, licenses,
and historical records remain available in this repository.

Requires Rust 1.85 or later and CPython 3.9 or later. PyPy, GraalPy, stable
ABI, and free-threaded support depend on the selected interpreter and features.

## Calling Python from Rust

For a checkout of this repository, use a path dependency:

```toml
[dependencies]
r2p = { path = "/path/to/r2p", features = ["auto-initialize"] }
```

```rust
use r2p::prelude::*;
use r2p::types::PyDict;

fn main() -> PyResult<()> {
    Python::initialize();
    Python::attach(|py| {
        let locals = PyDict::new(py);
        py.run(r2p::ffi::c_str!("result = 6 * 7"), None, Some(&locals))?;
        let result: i32 = locals.get_item("result")?.unwrap().extract()?;
        assert_eq!(result, 42);
        Ok(())
    })
}
```

## Exposing Rust to Python

Use `crate-type = ["cdylib"]` for an extension module:

```rust
use r2p::prelude::*;

#[pyfunction]
#[r2p(signature = (a, b))]
fn sum_as_string(a: usize, b: usize) -> String {
    (a + b).to_string()
}

#[pymodule]
# #[r2p(name = "r2p_sdk_readme_example")]
fn string_sum(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(sum_as_string, m)?)?;
    Ok(())
}
```

The SDK uses `#[r2p(...)]`, `r2p_build_config::use_r2p_cfgs()`, and
`R2P_*` build variables. Python API names such as `Python`, `Py<T>`, and
`PyResult` retain their meaning.

Current Maturin releases detect the fixed package names `pyo3` and `pyo3-ffi`.
The runnable examples include the private `tools/maturin-bridge` adapter
under the dependency alias `r2p-maturin-bridge`. Include this local adapter
when packaging r2p extensions with Maturin, and forward stable ABI features
to it as demonstrated by `examples/maturin-starter/Cargo.toml`.
The adapter is excluded from the SDK dependency graph and registry publication.

See `docs/guide/` for the full guide and `docs/development/` for repository workflows.
