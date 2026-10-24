use std::env;
use std::ffi::OsString;

fn main() {
    configure_wip_no_std();
}

/// Enables a faux `std` feature by default.
///
/// Set env var `R2P_WIP_NO_STD` to `1` to disable it.
// Has a matching function in r2p's build.rs
fn configure_wip_no_std() {
    println!("cargo:rustc-check-cfg=cfg(wip_feature_std)");
    match env_var("R2P_WIP_NO_STD").map(|s| s.into_string().unwrap()) {
        Some(no_std) if no_std.trim() == "1" || no_std.trim().eq_ignore_ascii_case("true") => (),
        _ => println!("cargo:rustc-cfg=wip_feature_std"),
    }
}

/// Gets an external environment variable, and registers the build script to rerun if
/// the variable changes.
fn env_var(var: &str) -> Option<OsString> {
    println!("cargo:rerun-if-env-changed={var}");
    env::var_os(var)
}
