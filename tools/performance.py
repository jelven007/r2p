"""Measure independent walltime and build-cost samples for two immutable SDK revisions."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from tools.engineering.environment import probe_python
else:
    from engineering.environment import probe_python

ROOT = Path(__file__).resolve().parent.parent
PROBE = ROOT / "tools/perf-probe"


def output(*command: str) -> str:
    return subprocess.check_output(command, cwd=ROOT, text=True).strip()


def archive(sha: str, destination: Path) -> None:
    destination.mkdir(parents=True)
    content = subprocess.check_output(["git", "archive", sha], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(content)) as source:
        source.extractall(destination, filter="data")


def build(directory: Path, environment: dict, features: list[str], log: Path) -> dict:
    command = ["cargo", "build", "--release", "--locked", "--offline", *features]
    timer = ["/usr/bin/time", "-l" if platform.system() == "Darwin" else "-v"]
    start = time.perf_counter()
    with log.open("w") as stream:
        subprocess.run(
            timer + command,
            cwd=directory,
            env=environment,
            stdout=stream,
            stderr=stream,
            check=True,
        )
    seconds = time.perf_counter() - start
    text = log.read_text()
    if platform.system() == "Darwin":
        match = re.search(r"(\d+)\s+maximum resident set size", text)
        peak = int(match[1]) if match else None
    else:
        match = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", text)
        peak = int(match[1]) * 1024 if match else None
    if peak is None:
        raise ValueError(f"missing peak memory measurement in {log}")
    binary = Path(environment["CARGO_TARGET_DIR"]) / "release/r2p-perf-probe"
    return {
        "seconds": seconds,
        "peak_rss_bytes": peak,
        "binary_bytes": binary.stat().st_size,
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "log": str(log),
    }


def summarize(samples: list[dict]) -> list[dict]:
    groups = {}
    for sample in samples:
        key = (
            sample["python_mode"],
            sample["variant"],
            sample["case"],
            sample["threads"],
            sample.get("work_model", "fixed_per_thread"),
        )
        groups.setdefault(key, []).append(sample["elapsed_ns"] / sample["units"])
    rows = []
    for (mode, variant, case, threads, work_model), values in sorted(groups.items()):
        rows.append(
            {
                "python_mode": mode,
                "variant": variant,
                "case": case,
                "threads": threads,
                "work_model": work_model,
                "samples": len(values),
                "median_ns_per_unit": statistics.median(values),
                "mean_ns_per_unit": statistics.mean(values),
                "stdev_ns_per_unit": statistics.stdev(values),
                "cv": statistics.stdev(values) / statistics.mean(values),
                "noisy": statistics.stdev(values) / statistics.mean(values) > 0.1,
                "min_ns_per_unit": min(values),
                "max_ns_per_unit": max(values),
            }
        )
    indexed = {
        (
            row["python_mode"],
            row["variant"],
            row["case"],
            row["threads"],
            row["work_model"],
        ): row
        for row in rows
    }
    for row in rows:
        if row["variant"] == "candidate":
            baseline = indexed[
                (
                    row["python_mode"],
                    "baseline",
                    row["case"],
                    row["threads"],
                    row["work_model"],
                )
            ]
            row["relative_median_change"] = (
                row["median_ns_per_unit"] / baseline["median_ns_per_unit"] - 1
            )
    return rows


def variant_order(repeat: int) -> tuple[str, str]:
    # ABBA balances both immediate order and the direction of longer drift.
    return (
        ("baseline", "candidate") if repeat % 4 in {0, 3} else ("candidate", "baseline")
    )


def validate_work(samples: list[dict], iterations: int, threaded_only: bool) -> None:
    expected = {
        (case, threads, model)
        for case in ("threaded_call_attach_detach", "threaded_deferred_drop_64")
        for threads in (1, 2, 4, 8)
        for model in ("fixed_total", "fixed_per_thread")
    }
    threaded = [row for row in samples if row["case"].startswith("threaded_")]
    if (
        len(threaded) != 16
        or {(row["case"], row["threads"], row["work_model"]) for row in threaded}
        != expected
    ):
        raise ValueError("threaded case/work-model set differs")
    if len(samples) != (16 if threaded_only else 25):
        raise ValueError("runtime case set differs")
    for row in threaded:
        units = iterations * (64 if row["case"].endswith("_64") else 1)
        if row["work_model"] == "fixed_per_thread":
            units *= row["threads"]
        if row["units"] != units or row["elapsed_ns"] <= 0:
            raise ValueError("thread work accounting differs")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline", default="3a24917eb2766aa8ded8c04fefde1c1d4b133c00"
    )
    parser.add_argument("--candidate", default=output("git", "rev-parse", "HEAD"))
    parser.add_argument("--gil-python", required=True)
    parser.add_argument("--free-threaded-python")
    parser.add_argument(
        "--python-mode", choices=("gil", "free-threaded", "both"), default="both"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=50_000)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--build-samples", type=int, default=3)
    parser.add_argument(
        "--runtime-only",
        action="store_true",
        help="build only the two minimal runtime binaries once per interpreter",
    )
    parser.add_argument("--threaded-only", action="store_true")
    args = parser.parse_args()
    if args.samples < 3:
        parser.error("at least three independent samples are required")
    if args.build_samples < 3 and not args.runtime_only:
        parser.error("build measurements require at least three clean samples")
    if not 1_000 <= args.iterations <= 1_000_000:
        parser.error("iterations must be between 1,000 and 1,000,000")
    if args.python_mode != "gil" and not args.free_threaded_python:
        parser.error("the selected mode requires --free-threaded-python")
    for sha in (args.baseline, args.candidate):
        if not re.fullmatch("[0-9a-f]{40}", sha):
            parser.error("source revisions must be full immutable Git SHAs")
    destination = args.output.resolve()
    if destination.exists():
        parser.error(
            "use a new output directory to keep clean-build samples independent"
        )
    destination.mkdir(parents=True)
    data = {
        "schema_version": 2,
        "mode": "walltime",
        "baseline": args.baseline,
        "candidate": args.candidate,
        "rust": subprocess.check_output(
            ["rustc", "-vV"], env=os.environ | {"RUSTUP_TOOLCHAIN": "stable"}, text=True
        ).strip(),
        "cpu": output("sysctl", "-n", "machdep.cpu.brand_string")
        if platform.system() == "Darwin"
        else platform.processor(),
        "os": platform.platform(),
        "jobs": 4,
        "iterations": args.iterations,
        "runtime_samples": args.samples,
        "build_samples": 0 if args.runtime_only else args.build_samples,
        "threaded_only": args.threaded_only,
        "order_policy": "ABBA",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "builds": [],
        "runtime_setup": [],
        "processes": [],
        "samples": [],
        "harness_sha256": {
            str(path.relative_to(PROBE)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (PROBE / "Cargo.toml", PROBE / "src/main.rs")
        },
        "limitations": "Warm local dependency cache, offline native release builds. ABBA order and untimed thread initialization; no CPU pinning or exclusive machine. CV>10% is an investigation signal, not a release gate. Synthetic embedding workload, not external adoption; no calibrated 5% gate. Build peak RSS is largest child, not simultaneous memory.",
    }

    def save() -> None:
        (destination / "samples.json").write_text(json.dumps(data, indent=2) + "\n")

    sources = {}
    for variant, sha in (("baseline", args.baseline), ("candidate", args.candidate)):
        source = destination / f"source-{variant}"
        archive(sha, source)
        harness = destination / f"probe-{variant}"
        shutil.copytree(
            PROBE, harness, ignore=shutil.ignore_patterns("Cargo.lock", "target")
        )
        manifest = (
            (harness / "Cargo.toml")
            .read_text()
            .replace('path = "../.."', f"path = {json.dumps(str(source))}")
        )
        (harness / "Cargo.toml").write_text(manifest)
        sources[variant] = (source, harness)
    for mode, executable, expected_gil in (
        ("gil", args.gil_python, True),
        ("free-threaded", args.free_threaded_python, False),
    ):
        if args.python_mode not in {"both", mode}:
            continue
        metadata = probe_python(executable)
        if metadata["implementation"] != "cpython" or metadata["version"][:2] < [3, 14]:
            raise ValueError("this probe targets CPython 3.14 or later")
        if metadata["free_threaded"] == expected_gil:
            raise ValueError(f"{mode}: interpreter does not match the requested build")
        data[mode] = metadata
        environment = os.environ | {
            "R2P_PYTHON": metadata["executable"],
            "RUSTUP_TOOLCHAIN": "stable",
            "CARGO_BUILD_JOBS": "4",
            "CARGO_INCREMENTAL": "1",
        }
        binaries = {}
        for variant in ("baseline", "candidate"):
            source, harness = sources[variant]
            subprocess.run(
                ["cargo", "generate-lockfile", "--offline"],
                cwd=harness,
                env=environment,
                check=True,
            )
            data.setdefault("locks", {})[f"{mode}-{variant}"] = hashlib.sha256(
                (harness / "Cargo.lock").read_bytes()
            ).hexdigest()
            for profile in (
                ["minimal", "full-sdk"]
                if variant == "candidate" and not args.runtime_only
                else ["minimal"]
            ):
                features = [] if profile == "minimal" else ["--features", "full-sdk"]
                for repeat in range(1 if args.runtime_only else args.build_samples):
                    target = destination / f"build-{mode}-{variant}-{profile}-{repeat}"
                    environment["CARGO_TARGET_DIR"] = str(target)
                    prefix = f"{mode}-{variant}-{profile}-{repeat}"
                    for kind in (
                        ("clean",)
                        if args.runtime_only
                        else ("clean", "consumer-edit", "sdk-edit")
                    ):
                        edited = (
                            harness / "src/main.rs"
                            if kind == "consumer-edit"
                            else source / "src/lib.rs"
                        )
                        original = edited.read_bytes()
                        if kind != "clean":
                            edited.write_bytes(
                                original
                                + f"\n// Incremental measurement {repeat}.\n".encode()
                            )
                        try:
                            result = build(
                                harness,
                                environment,
                                features,
                                destination / f"{prefix}-{kind}.log",
                            )
                        finally:
                            if kind != "clean":
                                edited.write_bytes(original)
                        data["runtime_setup" if args.runtime_only else "builds"].append(
                            {
                                "python_mode": mode,
                                "variant": variant,
                                "profile": profile,
                                "repeat": repeat,
                                "kind": kind,
                                **result,
                            }
                        )
                        save()
                        print(f"{prefix} {kind}: {result['seconds']:.3f}s", flush=True)
                    if profile == "minimal" and repeat == 0:
                        binaries[variant] = target / "release/r2p-perf-probe"
        if data["locks"][f"{mode}-baseline"] != data["locks"][f"{mode}-candidate"]:
            raise ValueError(
                "baseline and candidate resolved different dependency locks"
            )
        for repeat in range(args.samples):
            for position, variant in enumerate(variant_order(repeat)):
                start = time.perf_counter()
                load_before = os.getloadavg()
                result = json.loads(
                    subprocess.check_output(
                        [
                            str(binaries[variant]),
                            str(args.iterations),
                            *(["--threaded-only"] if args.threaded_only else []),
                        ],
                        env=environment,
                        text=True,
                    )
                )
                if (
                    result["mode"] != "walltime"
                    or result["environment"]["gil_enabled"] != expected_gil
                ):
                    raise ValueError(
                        "runtime GIL mode differs from the configured interpreter"
                    )
                validate_work(result["samples"], args.iterations, args.threaded_only)
                data["processes"].append(
                    {
                        "python_mode": mode,
                        "variant": variant,
                        "repeat": repeat,
                        "position": position,
                        "seconds": time.perf_counter() - start,
                        "load_before": load_before,
                        "load_after": os.getloadavg(),
                        "binary_sha256": hashlib.sha256(
                            binaries[variant].read_bytes()
                        ).hexdigest(),
                        "environment": result["environment"],
                    }
                )
                for sample in result["samples"]:
                    data["samples"].append(
                        {
                            "python_mode": mode,
                            "variant": variant,
                            "repeat": repeat,
                            **sample,
                        }
                    )
                save()
                print(
                    f"{mode} {variant} process {repeat}: {len(result['samples'])} cases",
                    flush=True,
                )
    data["summary"] = summarize(data["samples"])
    data["finished_at"] = datetime.now(timezone.utc).isoformat()
    save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
