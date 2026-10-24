# string_sum

A project built using only `r2p_ffi`, without any of r2p's safe api.

## Building and Testing

To build this package, first install `maturin`:

```shell
pip install maturin
```

To build and test use `maturin develop`:

```shell
pip install -r requirements-dev.txt
maturin develop
pytest
```

Alternatively, install nox and run the tests inside an isolated environment:

```shell
nox
```

## Copying this example

Use [`cargo-generate`](https://crates.io/crates/cargo-generate):

```bash
$ cargo install cargo-generate
$ cargo generate --path /path/to/r2p crates/r2p-ffi/examples/string-sum
```

(`cargo generate` will take a little while to clone the r2p repo first; be patient when waiting for the command to run.)
