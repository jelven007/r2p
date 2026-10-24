use r2p::prelude::*;

#[pyclass]
struct MyClass {}

#[pymethods]
impl MyClass {
    #[r2p(name = "__getbuffer__")]
    fn getbuffer_must_be_unsafe(&self, _view: *mut r2p::ffi::Py_buffer, _flags: std::ffi::c_int) {}
//~^ ERROR: `__getbuffer__` must be `unsafe fn`
}

#[pymethods]
impl MyClass {
    #[r2p(name = "__releasebuffer__")]
    fn releasebuffer_must_be_unsafe(&self, _view: *mut r2p::ffi::Py_buffer) {}
//~^ ERROR: `__releasebuffer__` must be `unsafe fn`
}

fn main() {}
