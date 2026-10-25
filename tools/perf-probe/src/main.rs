use r2p::prelude::*;
use r2p::types::{PyBytes, PyDict, PyList, PyModule, PyString};
use serde_json::{Value, json};
use std::hint::black_box;
use std::sync::{Arc, Barrier};
use std::time::Instant;

fn measure(
    rows: &mut Vec<Value>,
    name: &str,
    units: usize,
    iterations: usize,
    mut work: impl FnMut() -> PyResult<()>,
) -> PyResult<()> {
    for _ in 0..100 {
        work()?;
    }
    let start = Instant::now();
    for _ in 0..iterations {
        work()?;
    }
    rows.push(json!({
        "case": name, "threads": 1, "units": units * iterations,
        "elapsed_ns": start.elapsed().as_nanos() as u64,
    }));
    Ok(())
}

fn threaded(
    rows: &mut Vec<Value>,
    threads: usize,
    iterations: usize,
    deferred_drop: bool,
    fixed_total: bool,
) {
    let ready = Arc::new(Barrier::new(threads + 1));
    let go = Arc::new(Barrier::new(threads + 1));
    let workers = (0..threads)
        .map(|worker| {
            let ready = ready.clone();
            let go = go.clone();
            let work = if fixed_total {
                iterations / threads + usize::from(worker < iterations % threads)
            } else {
                iterations
            };
            std::thread::spawn(move || {
                // Interpreter/import initialization stays outside the timed region.
                let function = Python::attach(|py| {
                    py.import("builtins")
                        .unwrap()
                        .getattr("abs")
                        .unwrap()
                        .unbind()
                });
                let step = || {
                    if deferred_drop {
                        let objects = Python::attach(|py| {
                            (0..64)
                                .map(|_| PyString::new(py, "a non-interned payload").unbind())
                                .collect::<Vec<_>>()
                        });
                        drop(objects);
                        Python::attach(|_| {});
                    } else {
                        Python::attach(|py| {
                            let result: i64 = function
                                .bind(py)
                                .call1((-123_i64,))
                                .unwrap()
                                .extract()
                                .unwrap();
                            assert_eq!(black_box(result), 123);
                            py.detach(|| black_box(123));
                        });
                    }
                };
                for _ in 0..100 {
                    step();
                }
                ready.wait();
                go.wait();
                for _ in 0..work {
                    step();
                }
            })
        })
        .collect::<Vec<_>>();
    ready.wait();
    let start = Instant::now();
    go.wait();
    for worker in workers {
        worker.join().unwrap();
    }
    rows.push(json!({
        "case": if deferred_drop { "threaded_deferred_drop_64" } else { "threaded_call_attach_detach" },
        "threads": threads,
        "work_model": if fixed_total { "fixed_total" } else { "fixed_per_thread" },
        "units": if fixed_total { iterations } else { threads * iterations } * if deferred_drop { 64 } else { 1 },
        "elapsed_ns": start.elapsed().as_nanos() as u64,
    }));
}

fn main() -> PyResult<()> {
    let arguments = std::env::args().skip(1).collect::<Vec<_>>();
    let iterations = arguments
        .first()
        .map(|v| v.parse::<usize>().unwrap())
        .unwrap_or(50_000);
    assert!((1_000..=1_000_000).contains(&iterations));
    let threaded_only = arguments.iter().any(|arg| arg == "--threaded-only");
    assert!(arguments.iter().skip(1).all(|arg| arg == "--threaded-only"));
    Python::initialize();
    let mut rows = Vec::new();
    let environment = Python::attach(|py| -> PyResult<Value> {
        let sys = py.import("sys")?;
        Ok(json!({
            "python": sys.getattr("version")?.extract::<String>()?,
            "gil_enabled": sys.call_method0("_is_gil_enabled")?.extract::<bool>()?,
        }))
    })?;
    if !threaded_only {
        Python::attach(|py| -> PyResult<()> {
            let module = PyModule::from_code(
                py,
                c"def scalar(x): return x + 1\n\ndef batch(xs): return sum(x + 1 for x in xs)\n",
                c"probe.py",
                c"probe",
            )?;
            let scalar = module.getattr("scalar")?;
            let batch = module.getattr("batch")?;
            let inputs = PyList::new(py, 0..64_i64)?;
            measure(&mut rows, "scalar_calls_64", 64, iterations, || {
                let mut total = 0;
                for value in 0..64_i64 {
                    total += scalar.call1((value,))?.extract::<i64>()?;
                }
                assert_eq!(black_box(total), 2080);
                Ok(())
            })?;
            measure(&mut rows, "batch_call_64", 64, iterations, || {
                assert_eq!(black_box(batch.call1((&inputs,))?.extract::<i64>()?), 2080);
                Ok(())
            })?;
            let text = "example string for conversion ".repeat(8);
            measure(
                &mut rows,
                "string_roundtrip_240",
                1,
                iterations * 16,
                || {
                    let value = PyString::new(py, &text);
                    assert_eq!(black_box(value.to_str()?), text);
                    Ok(())
                },
            )?;
            let bytes = [0x55; 256];
            measure(&mut rows, "bytes_roundtrip_256", 1, iterations * 16, || {
                let value = PyBytes::new(py, &bytes);
                assert_eq!(black_box(value.as_bytes()), bytes);
                Ok(())
            })?;
            let list = PyList::new(py, 0..1024_i64)?;
            measure(&mut rows, "list_iter_1024", 1024, iterations, || {
                let mut total = 0;
                for item in list.iter() {
                    total += item.extract::<i64>()?;
                }
                assert_eq!(black_box(total), 523776);
                Ok(())
            })?;
            let dict = PyDict::new(py);
            for i in 0..1024_i64 {
                dict.set_item(i, i)?;
            }
            measure(&mut rows, "dict_iter_1024", 1024, iterations, || {
                let mut total = 0;
                for (key, value) in dict.iter() {
                    let value = value.extract::<i64>()?;
                    assert_eq!(key.extract::<i64>()?, value);
                    total += value;
                }
                assert_eq!(black_box(total), 523776);
                Ok(())
            })?;
            measure(&mut rows, "attach_detach", 1, iterations * 16, || {
                Python::attach(|nested| nested.detach(|| black_box(123)));
                Ok(())
            })?;
            measure(&mut rows, "drop_attached_64", 64, iterations, || {
                let objects = (0..64)
                    .map(|_| PyString::new(py, "a non-interned payload").unbind())
                    .collect::<Vec<_>>();
                drop(objects);
                Ok(())
            })?;
            Ok(())
        })?;
        measure(&mut rows, "drop_deferred_64", 64, iterations, || {
            let objects = Python::attach(|py| {
                (0..64)
                    .map(|_| PyString::new(py, "a non-interned payload").unbind())
                    .collect::<Vec<_>>()
            });
            drop(objects);
            Python::attach(|_| {});
            Ok(())
        })?;
    }
    for fixed_total in [false, true] {
        for threads in [1, 2, 4, 8] {
            threaded(&mut rows, threads, iterations, false, fixed_total);
            threaded(&mut rows, threads, iterations, true, fixed_total);
        }
    }
    println!(
        "{}",
        json!({"mode": "walltime", "environment": environment, "samples": rows})
    );
    Ok(())
}
