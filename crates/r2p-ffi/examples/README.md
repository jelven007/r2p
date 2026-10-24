# `r2p-ffi` Examples

These example crates are a collection of toy extension modules built with
`r2p-ffi`. They are all tested using `nox` in r2p's CI.

Below is a brief description of each of these:

| Example | Description |
| `word-count` | Illustrates how to use r2p-ffi to write a static rust extension |
| `sequential` | Illustrates how to use r2p-ffi to write subinterpreter-safe modules using multi-phase module initialization |

## Creating new projects from these examples

To copy an example, use [`cargo-generate`](https://crates.io/crates/cargo-generate). Follow the commands below, replacing `<example>` with the example to start from:

```bash
$ cargo install cargo-generate
$ cargo generate --path /path/to/r2p crates/r2p-ffi/examples/<example>
```

(`cargo generate` will take a little while to clone the r2p repo first; be patient when waiting for the command to run.)
