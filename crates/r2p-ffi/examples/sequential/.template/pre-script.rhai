variable::set("R2P_VERSION", "0.19.2");
file::rename(".template/Cargo.toml", "Cargo.toml");
file::rename(".template/pyproject.toml", "pyproject.toml");
file::rename(".template/maturin-bridge", "maturin-bridge");
file::delete(".template");
