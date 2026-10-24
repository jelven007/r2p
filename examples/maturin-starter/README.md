# maturin-starter

An example of a basic Python extension module built using r2p and [`maturin`](https://github.com/PyO3/maturin).

## Building and Testing

To build this package, first install `maturin`:

```shell
pip install maturin
```

To build and test use `maturin develop`:

```shell
pip install pytest
maturin develop && pytest
```

Alternatively, install nox and run the tests inside an isolated environment:

```shell
nox
```

## Copying this example

From an SDK checkout, generate a standalone project with a fixed Git revision:

```sh
python tools/new_project.py ../my-extension --example maturin-starter
```

The SDK and the bundled private Maturin adapter use the same source.
The generated distribution is named `my-extension`; import it as `maturin_starter`.
See the [SDK guide](https://github.com/jelven007/r2p/blob/main/docs/sdk/README.md) for source selection and isolated build verification.

Alternatively, use [`cargo-generate`](https://crates.io/crates/cargo-generate):

```bash
cargo install cargo-generate
cargo generate --path /path/to/r2p/examples/maturin-starter
```
