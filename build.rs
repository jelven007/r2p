use std::env;

use r2p_build_config::r2p_build_script_impl::{
    cargo_env_var, env_var, errors::Result, print_feature_cfgs,
};
use r2p_build_config::{InterpreterConfig, add_libpython_rpath_link_args, bail};

fn ensure_auto_initialize_ok(interpreter_config: &InterpreterConfig) -> Result<()> {
    if cargo_env_var("CARGO_FEATURE_AUTO_INITIALIZE").is_some() && !interpreter_config.shared() {
        bail!(
            "The `auto-initialize` feature is enabled, but your python installation only supports \
            embedding the Python interpreter statically. If you are attempting to run tests, or a \
            binary which is okay to link dynamically, install a Python distribution which ships \
            with the Python shared library.\n\
            \n\
            Embedding the Python interpreter statically does not yet have first-class support in \
            r2p. If you are sure you intend to do this, disable the `auto-initialize` feature.\n\
            \n\
            For more information, see \
            https://pyo3.rs/v{r2p_version}/\
                building-and-distribution.html#embedding-python-in-rust",
            r2p_version = env::var("CARGO_PKG_VERSION").unwrap()
        );
    }
    Ok(())
}

/// Prepares the r2p crate for compilation.
///
/// This loads the config from r2p-build-config and then makes some additional checks to improve UX
/// for users.
///
/// Emits the cargo configuration based on this config as well as a few checks of the Rust compiler
/// version to enable features which aren't supported on MSRV.
fn configure_r2p() -> Result<()> {
    let interpreter_config = r2p_build_config::get();

    ensure_auto_initialize_ok(interpreter_config)?;

    for cfg in interpreter_config.build_script_outputs() {
        println!("{cfg}")
    }

    print_feature_cfgs();

    // Forwards interpreter config under the links = "r2p-python" configuration,
    // which allows consumers of `r2p-build-config` APIs to depend on r2p instead of r2p-ffi.
    interpreter_config.to_cargo_dep_env()?;

    // Make `cargo test` etc work with non-system Python installations
    add_libpython_rpath_link_args();

    Ok(())
}

/// Enables a faux `std` feature by default.
///
/// Set env var `R2P_WIP_NO_STD` to `1` to disable it.
// Has matching functions in
// - r2p-macros-backend
// - pytests
fn configure_wip_no_std() {
    println!("cargo:rustc-check-cfg=cfg(wip_feature_std)");
    match env_var("R2P_WIP_NO_STD").map(|s| s.into_string().unwrap()) {
        Some(no_std) if no_std.trim() == "1" || no_std.trim().eq_ignore_ascii_case("true") => (),
        _ => println!("cargo:rustc-cfg=wip_feature_std"),
    }
}

fn main() {
    configure_wip_no_std();
    r2p_build_config::print_expected_cfgs();
    if let Err(e) = configure_r2p() {
        eprintln!("error: {}", e.report());
        std::process::exit(1)
    }
}
