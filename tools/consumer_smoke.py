"""Build generated consumers outside the repository and save reproducible evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from tools.new_project import ROOT, examples, generate, source_configuration

BEHAVIOR = """\
import json, pathlib, sys
import maturin_starter as sdk
assert pathlib.Path(sdk.__file__).is_relative_to(sys.prefix), sdk.__file__
assert sdk.divide(84, 2) == 42
value = sdk.ExampleClass(11)
assert value.value == 11
value.value = 42
assert value.value == 42
for args in ((1, 0), (-(2**31), -1)):
    try:
        sdk.divide(*args)
    except ValueError as error:
        assert str(error) == "division by zero or integer overflow"
    else:
        raise AssertionError("expected ValueError")
assert sdk.divide(6, 2) == 3
from maturin_starter.submodule import SubmoduleClass
assert SubmoduleClass().greeting() == "Hello, world!"
print(json.dumps({"python": sys.version, "module": sdk.__file__,
                  "function": "passed", "class": "passed", "exception": "passed"}))
"""


def python_in(directory: Path) -> Path:
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def check_graph(metadata: dict, source: dict) -> list[dict]:
    packages = metadata["packages"]
    ffi = [package for package in packages if package["name"] == "r2p-ffi"]
    if len(ffi) != 1:
        raise ValueError(f"expected exactly one r2p-ffi, found {len(ffi)}")
    sdk = [
        package
        for package in packages
        if package["name"] == "r2p" or package["name"].startswith("r2p-")
    ]
    for package in sdk:
        if package["version"] != source["version"]:
            raise ValueError(f"unexpected SDK version: {package['id']}")
        if source["mode"] == "git" and package["source"] != (
            f"git+{source['repository']}?rev={source['revision']}#{source['revision']}"
        ):
            raise ValueError(f"unexpected SDK source: {package['id']}")
        if source["mode"] == "path" and not Path(
            package["manifest_path"]
        ).is_relative_to(source["checkout"]):
            raise ValueError(f"unexpected SDK path: {package['id']}")
    return [
        {"name": package["name"], "version": package["version"], "id": package["id"]}
        for package in sdk
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", choices=("git", "path"), default="git")
    parser.add_argument("--revision")
    parser.add_argument("--checkout", type=Path)
    parser.add_argument("--maturin-version", default="1.15.0")
    args = parser.parse_args()
    source = source_configuration(
        args.source, revision=args.revision, checkout=args.checkout
    )
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    # A system temporary directory prevents accidental inheritance of workspace patches.
    work = Path(tempfile.mkdtemp(prefix="r2p-consumer-")).resolve()
    if work.is_relative_to(ROOT):
        raise ValueError("consumer validation must run outside the source repository")
    environment = os.environ.copy()
    for key in (
        "PYTHONPATH",
        "R2P_CONFIG_FILE",
        "R2P_NO_PYTHON",
        "CARGO_ENCODED_RUSTFLAGS",
        "RUSTFLAGS",
        "R2P_WIP_NO_STD",
        "R2P_USE_ABI3_FORWARD_COMPATIBILITY",
    ):
        environment.pop(key, None)
    environment.update(
        CARGO_TARGET_DIR=str(work / "target"),
        R2P_PYTHON=sys.executable,
        PYO3_PYTHON=sys.executable,
    )
    report = {
        "schema_version": 1,
        "source": source,
        "generator_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "work_directory": str(work),
        "commands": [],
        "graphs": {},
        "artifacts": [],
        "result": "failure",
    }

    def run(*command: str | Path, cwd: Path = work) -> str:
        command = [str(part) for part in command]
        print(f"+ {command!r} (cwd={cwd})", flush=True)
        start = time.monotonic()
        process = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        index = len(report["commands"])
        log = output / f"{index:02d}.log"
        log.write_text(process.stdout + process.stderr)
        report["commands"].append(
            {
                "command": command,
                "cwd": str(cwd),
                "exit_code": process.returncode,
                "seconds": round(time.monotonic() - start, 3),
                "log": log.name,
            }
        )
        if process.returncode:
            raise RuntimeError(f"command failed; see {log}")
        return process.stdout

    try:
        report["rust"] = run("rustc", "-vV")
        report["uv"] = run("uv", "--version").strip()
        for example in examples():
            project = generate(
                example, work / example, name=example, authors="r2p", source=source
            )
            metadata = json.loads(
                run("cargo", "metadata", "--format-version", "1", cwd=project)
            )
            report["graphs"][example] = check_graph(metadata, source)
            (output / f"{example}.lock").write_bytes(
                (project / "Cargo.lock").read_bytes()
            )
        build = work / "builder"
        run("uv", "venv", build, "--python", sys.executable)
        builder = python_in(build)
        run(
            "uv",
            "pip",
            "install",
            "--python",
            builder,
            f"maturin=={args.maturin_version}",
        )
        run(
            builder,
            "-m",
            "maturin",
            "sdist",
            "--out",
            output / "sdist",
            cwd=work / "maturin-starter",
        )
        (sdist,) = (output / "sdist").glob("*.tar.gz")
        extracted = work / "from-sdist"
        with tarfile.open(sdist) as archive:
            archive.extractall(extracted, filter="data")
        (project,) = extracted.iterdir()
        report["graphs"]["sdist"] = check_graph(
            json.loads(run("cargo", "metadata", "--format-version", "1", cwd=project)),
            source,
        )
        for abi in ("native", "abi3"):
            destination = output / abi
            flags = ("--features", "abi3") if abi == "abi3" else ()
            run(
                builder,
                "-m",
                "maturin",
                "build",
                "--release",
                "--locked",
                "--interpreter",
                sys.executable,
                "--out",
                destination,
                *flags,
                cwd=project,
            )
            (wheel,) = destination.glob("*.whl")
            expected = (
                "-cp39-abi3-"
                if abi == "abi3"
                else (f"-cp{sys.version_info.major}{sys.version_info.minor}-")
            )
            if expected not in wheel.name or (
                abi == "native" and "-abi3-" in wheel.name
            ):
                raise ValueError(f"incorrect wheel tag: {wheel.name}")
            with zipfile.ZipFile(wheel) as archive:
                report.setdefault("wheel_metadata", {})[abi] = archive.read(
                    next(name for name in archive.namelist() if name.endswith("/WHEEL"))
                ).decode()
            install = work / f"install-{abi}"
            run("uv", "venv", install, "--python", sys.executable)
            interpreter = python_in(install)
            run("uv", "pip", "install", "--python", interpreter, "--no-deps", wheel)
            installed = json.loads(run(interpreter, "-I", "-c", BEHAVIOR))
            report.setdefault("behavior", {})[abi] = installed
        result = run("cargo", "run", "--locked", cwd=work / "plugin")
        if "class, exception, and recovery passed" not in result:
            raise ValueError("embedding example did not complete")
        report["embedding"] = "passed"
        for artifact in output.rglob("*"):
            if artifact.suffix in {".whl", ".gz", ".lock"}:
                report["artifacts"].append(
                    {
                        "path": str(artifact.relative_to(output)),
                        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                        "size": artifact.stat().st_size,
                    }
                )
        report["result"] = "success"
    finally:
        (output / "evidence.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Consumer validation passed: {output / 'evidence.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
