#[r2p::pymodule]
mod r2p_scratch {
    use r2p::prelude::*;

    #[pyclass]
    struct Foo {}

    #[pymethods]
    impl Foo {
        #[pyfunction]
        fn bug() {}
//~^ ERROR: functions inside #[pymethods] do not need to be annotated with #[pyfunction]
    }
}

fn main() {}
