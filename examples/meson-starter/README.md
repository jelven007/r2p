# meson-starter

An example of a basic Python extension module built using r2p and [`meson-python`](https://github.com/mesonbuild/meson-python).

## Building and Testing

Install nox and run the tests inside an isolated environment:

```shell
nox
```

## Copying this example

Use [`cargo-generate`](https://crates.io/crates/cargo-generate):

```bash
$ cargo install cargo-generate
$ cargo generate --path /path/to/r2p examples/meson-starter
```

(`cargo generate` will take a little while to clone the r2p repo first; be patient when waiting for the command to run.)
