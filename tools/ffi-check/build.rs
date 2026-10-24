fn main() {
    let out_dir = std::env::var("OUT_DIR").unwrap();
    let target = std::env::var("TARGET").unwrap();

    let doc_dir = std::path::Path::new(&out_dir)
        .join(&target)
        .join("doc")
        .join("r2p_ffi_check_definitions");

    // write docs into the build script output directory, they will be read
    // by the proc macro to resolve what definitions exist
    let status = std::process::Command::new("cargo")
        .args([
            "doc",
            "-p",
            "r2p-ffi-check-definitions",
            "--no-deps",
            "--document-private-items",
        ])
        .env("CARGO_TARGET_DIR", out_dir)
        // forward target to the doc build to ensure `--target` is honored
        .env("CARGO_BUILD_TARGET", target)
        .status()
        .expect("failed to build definitions");

    // macro will use this env var to locate the docs
    println!(
        "cargo:rustc-env=R2P_FFI_CHECK_DOC_DIR={}",
        doc_dir.to_str().unwrap()
    );

    status
        .success()
        .then_some(())
        .expect("failed to build definitions, see above for details");

    // rerun if any of the definitions change, to ensure the docs are up to date
    println!("cargo:rerun-if-changed=definitions");
    println!("cargo:rerun-if-changed=../../crates/r2p-ffi");

    r2p_build_config::use_r2p_cfgs();

    // Because `r2p-ffi` is a dependency, libpython is linked, this ensures `main.rs` can run.
    // Slightly needless (no symbols from libpython are actually called), but simple to do.
    r2p_build_config::add_libpython_rpath_link_args();

    // Forward config into this crate's compilation, so that `ffi-check` macro can consume it.
    let r2p_config_raw =
        std::env::var("DEP_PYTHON_R2P_CONFIG").expect("R2P_CONFIG environment variable not set");
    println!("cargo:rustc-env=DEP_PYTHON_R2P_CONFIG={r2p_config_raw}");
}
