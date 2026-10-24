variable::set("R2P_VERSION", "0.30.0");
file::rename(".template/Cargo.toml", "Cargo.toml");
file::rename(".template/plugin_api/Cargo.toml", "plugin_api/Cargo.toml");
file::rename(".template/maturin-bridge", "maturin-bridge");
file::delete(".template");
