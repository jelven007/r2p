#![cfg(not(any(PyPy, GraalPy)))]
#![cfg(not(target_arch = "wasm32"))]

use r2p::types::PyAnyMethods;

// Regression test for `try_attach` fast-path returning before site.py had
// finished initializing.
#[test]
fn test_concurrent_init_site_race() {
    let tmpdir = std::env::temp_dir().join("r2p_test_init_race");
    std::fs::create_dir_all(&tmpdir).unwrap();

    std::fs::write(
        tmpdir.join("sitecustomize.py"),
        "import sys, time\n\
         sys._r2p_site_done = False\n\
         time.sleep(2)\n\
         sys._r2p_site_done = True\n",
    )
    .unwrap();

    // SAFETY: This is the only test in this binary, and Python and the worker
    // threads have not been started yet.
    unsafe { std::env::set_var("PYTHONPATH", &tmpdir) };

    std::thread::scope(|s| {
        s.spawn(|| {
            r2p::Python::initialize();
        });

        s.spawn(|| {
            loop {
                let result = r2p::Python::try_attach(|py| {
                    let done = py
                        .import("sys")
                        .unwrap()
                        .getattr("_r2p_site_done")
                        .unwrap()
                        .extract::<bool>()
                        .unwrap();
                    assert!(done);
                });
                if result.is_some() {
                    break;
                }
                std::hint::spin_loop();
            }
        });
    });
}
