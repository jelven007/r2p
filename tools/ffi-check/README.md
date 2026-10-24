# r2p-ffi-check

This is a simple program which compares ffi definitions from `r2p-ffi` against those produced by `bindgen`.

It checks type layouts, function signatures, and the addresses of functions and statics. Any differences are printed to stdout and the process exits nonzero.

The main purpose of this program is to be run as part of r2p's continuous integration pipeline to catch possible errors in r2p's ffi definitions.
