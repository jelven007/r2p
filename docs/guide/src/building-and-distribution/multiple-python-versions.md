# Supporting multiple Python versions

r2p supports all actively-supported Python 3 and PyPy versions.
As much as possible, this is done internally to r2p so that your crate's code does not need to adapt to the differences between each version.
However, as Python features grow and change between versions, r2p cannot offer a completely identical API for every Python version.
This may require you to add conditional compilation to your crate or runtime checks for the Python version.

This section of the guide first introduces the `r2p-build-config` crate, which you can use as a `build-dependency` to add additional `#[cfg]` flags which allow you to support multiple Python versions at compile-time.

Second, we'll show how to check the Python version at runtime.
This can be useful when building for multiple versions with the `abi3` feature, where the Python API compiled against is not always the same as the one in use.

## Conditional compilation for different Python versions

The `r2p-build-config` exposes multiple [`#[cfg]` flags](https://doc.rust-lang.org/rust-by-example/attribute/cfg.html) which can be used to conditionally compile code for a given Python version.
r2p itself depends on this crate, so by using it you can be sure that you are configured correctly for the Python version r2p is building against.

This allows us to write code like the following

```rust,ignore
#[cfg(Py_3_9)]
fn function_only_supported_on_python_3_9_and_up() {}

#[cfg(not(Py_3_9))]
fn function_only_supported_before_python_3_9() {}

#[cfg(not(Py_LIMITED_API))]
fn function_incompatible_with_stable_abi_feature() {}
```

The following sections first show how to add these `#[cfg]` flags to your build process, and then cover some common patterns flags in a little more detail.

To see a full reference of all the `#[cfg]` flags provided, see the [`r2p-build-cfg` docs](https://docs.rs/pyo3-build-config).

### Using `r2p-build-config`

You can use the `#[cfg]` flags in just two steps:

1. Add `r2p-build-config` to your crate's build dependencies in `Cargo.toml`:

   ```toml
   [build-dependencies]
   r2p-build-config = {{#R2P_CRATE_VERSION}}
   ```

2. Add a [`build.rs`](https://doc.rust-lang.org/cargo/reference/build-scripts.html) file to your crate with the following contents:

   ```rust,ignore
   fn main() {
       // If you have an existing build.rs file, just add this line to it.
       r2p_build_config::use_r2p_cfgs();
   }
   ```

After these steps you are ready to annotate your code!

### Common usages of `r2p-build-cfg` flags

The `#[cfg]` flags added by `r2p-build-cfg` can be combined with all of Rust's logic in the `#[cfg]` attribute to create very precise conditional code generation.
The following are some common patterns implemented using these flags:

```text
#[cfg(Py_3_9)]
```

This `#[cfg]` marks code that will only be present on Python 3.9 and upwards.
There are similar options `Py_3_10`, `Py_3_11`, `Py_3_12` and so on for each minor version.

```text
#[cfg(not(Py_3_9))]
```

This `#[cfg]` marks code that will only be present on Python versions before (but not including) Python 3.9.

```text
#[cfg(Py_GIL_DISABLED)]
```

This `#[cfg]` marks code that will only be present for free-threaded builds of CPython.
You might use this in situations where the GIL provides thread safety but the free-threaded build needs extra synchronization logic.

```text
#[cfg(not(Py_LIMITED_API))]
```

This `#[cfg]` marks code that is only available when building for the unlimited Python API (i.e. r2p's `abi3` or `abi3t` features are not enabled).
This might be useful if you want to ship your extension module as an `abi3` or `abi3t` wheel and also allow users to compile it from source to make use of optimizations only possible with the unlimited API.

```text
#[cfg(any(Py_3_9, not(Py_LIMITED_API)))]
```

This `#[cfg]` marks code which is available when running Python 3.9 or newer, or when using the unlimited API with an older Python version.
Patterns like this are commonly seen on Python APIs which were added to the limited Python API in a specific minor version.

```text
#[cfg(all(Py_GIL_DISABLED, Py_LIMITED_API))]
```

This marks code which is available only for the free-threaded `abi3t` stable ABI.
You might use this if you need some sort of custom locking implementation in code that makes strong assumptions about the GIL providing thread safety.

```text
#[cfg(PyPy)]
```

This `#[cfg]` marks code which is running on PyPy.

## Checking the Python version at runtime

When building with r2p's `abi3` or `abi3t` features, your extension module will be compiled against a specific [minimum version](../building-and-distribution.md#minimum-python-version-for-abi3-and-abi3t-builds) of Python, but may be running on newer Python versions.

For example with r2p's `abi3-py39` feature, your extension module will be compiled as if it were for Python 3.9.
If you were using `r2p-build-config`, `#[cfg(Py_3_9)]` would be present.
Your user could freely install and run your abi3 extension module on Python 3.10.

There's no way to detect your user doing that at compile time, so instead you need to fall back to runtime checks.

r2p provides the APIs [`Python::version()`] and [`Python::version_info()`] to query the running Python version.
This allows you to do the following, for example:

```rust
use r2p::Python;

Python::attach(|py| {
    // r2p supports Python 3.9 and up.
    assert!(py.version_info() >= (3, 9));
    assert!(py.version_info() >= (3, 9, 0));
});
```

[`Python::version()`]: {{#R2P_DOCS_URL}}/r2p/marker/struct.Python.html#method.version
[`Python::version_info()`]: {{#R2P_DOCS_URL}}/r2p/marker/struct.Python.html#method.version_info
