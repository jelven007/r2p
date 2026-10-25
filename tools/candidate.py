"""Assemble six SDK crates, then consume them through an isolated sparse registry."""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import tomllib

from tools.candidate_artifacts import (
    SDK,
    check_cli,
    crate_metadata,
    digest,
    verify_manifest,
    wheel_metadata,
)
from tools.consumer_smoke import BEHAVIOR, python_in
from tools.new_project import ROOT, generate


def index_path(name: str) -> str:
    name = name.lower()
    if len(name) < 3:
        return f"{len(name)}/{name}"
    if len(name) == 3:
        return f"3/{name[0]}/{name}"
    return f"{name[:2]}/{name[2:4]}/{name}"


def index_entry(manifest: dict, checksum: str) -> dict:
    dependencies = []

    def add(section: dict, target: str | None) -> None:
        for kind, key in (
            ("normal", "dependencies"),
            ("build", "build-dependencies"),
            ("dev", "dev-dependencies"),
        ):
            for alias, fields in section.get(key, {}).items():
                dependencies.append(
                    {
                        "name": alias,
                        "req": fields["version"],
                        "features": fields.get("features", []),
                        "optional": fields.get("optional", False),
                        "default_features": fields.get("default-features", True),
                        "target": target,
                        "kind": kind,
                        "package": fields.get("package"),
                        "registry": None,
                    }
                )

    add(manifest, None)
    for target, fields in manifest.get("target", {}).items():
        add(fields, target)
    package = manifest["package"]
    return {
        "name": package["name"],
        "vers": package["version"],
        "deps": dependencies,
        "cksum": checksum,
        "features": {},
        "features2": manifest.get("features", {}),
        "v": 2,
        "yanked": False,
        "links": package.get("links"),
        "rust_version": package.get("rust-version"),
    }


def cached_mirror(cache_home: Path, destination: Path) -> dict:
    """Copy only cache packages whose digest agrees with their public index."""
    entries = {}
    for cache in (cache_home / "registry/index").glob("*/.cache"):
        for path in cache.rglob("*"):
            if not path.is_file():
                continue
            for field in path.read_bytes().split(b"\0"):
                if field.startswith(b'{"name":'):
                    entry = json.loads(field)
                    entries[(entry["name"], entry["vers"])] = entry
    selected = {}
    for path in (cache_home / "registry/cache").glob("*/*.crate"):
        name, version = path.stem.rsplit("-", 1)
        if name in SDK:
            continue
        entry = entries.get((name, version))
        if entry is None:
            continue
        if digest(path) != entry["cksum"]:
            raise ValueError(f"public cache checksum mismatch: {path.name}")
        target = destination / "crates" / name / version / "download"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        selected.setdefault(name, {})[version] = entry
    for name, versions in selected.items():
        path = destination / index_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(json.dumps(entry) + "\n" for entry in versions.values())
        )
    return {
        "public_packages": sum(len(versions) for versions in selected.values()),
        "provenance": "public Cargo cached index checksums and matching .crate bytes",
    }


def registry_graph(metadata: dict, home: Path, version: str, sha: str) -> list[dict]:
    sdk = [package for package in metadata["packages"] if package["name"] in SDK]
    if len([package for package in sdk if package["name"] == "r2p-ffi"]) != 1:
        raise ValueError("consumer must resolve exactly one registry r2p-ffi")
    rows = []
    for package in sdk:
        manifest = Path(package["manifest_path"])
        if (
            package["version"] != version
            or not package["source"].startswith("registry+")
            or not manifest.resolve().is_relative_to(home / "registry/src")
            or json.loads((manifest.parent / ".cargo_vcs_info.json").read_text())[
                "git"
            ]["sha1"]
            != sha
        ):
            raise ValueError(f"consumer source mismatch: {package['id']}")
        rows.append(
            {
                "name": package["name"],
                "version": package["version"],
                "source": package["source"],
                "manifest_path": str(manifest),
                "source_sha": sha,
            }
        )
    return rows


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True)
    parser.add_argument(
        "--baseline-sha", default="3a24917eb2766aa8ded8c04fefde1c1d4b133c00"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--maturin-version", default="1.15.0")
    args = parser.parse_args()
    if (
        any(
            not re.fullmatch(r"[0-9a-f]{40}", sha)
            for sha in (args.sha, args.baseline_sha)
        )
        or args.sha == args.baseline_sha
    ):
        parser.error("candidate and baseline require different full immutable SHAs")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    work = Path(tempfile.mkdtemp(prefix="r2p-candidate-")).resolve()
    cache_home = Path(os.environ.get("CARGO_HOME", str(Path.home() / ".cargo")))
    lock_digest = digest(ROOT / "Cargo.lock")
    environment = os.environ.copy()
    for key in (
        "PYTHONPATH",
        "RUSTFLAGS",
        "CARGO_ENCODED_RUSTFLAGS",
        "R2P_CONFIG_FILE",
        "R2P_NO_PYTHON",
        "R2P_WIP_NO_STD",
        "R2P_USE_ABI3_FORWARD_COMPATIBILITY",
        "CARGO_BUILD_TARGET",
    ):
        environment.pop(key, None)
    environment.update(
        R2P_PYTHON=sys.executable,
        PYO3_PYTHON=sys.executable,
        CARGO_BUILD_JOBS="4",
        RUSTUP_TOOLCHAIN="stable",
    )
    report = {
        "schema_version": 1,
        "source_sha": args.sha,
        "tool_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "public_release": False,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "work_directory": str(work),
        "commands": [],
        "variants": {},
        "result": "failure",
        "limitations": "Local candidate registry, native host execution only. abi3-py39 ran on recorded CPython, not all supported interpreters. Full remote CI and external namespace/operations admission are separate gates.",
    }

    def save() -> None:
        (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")

    def run(*command: str | Path, cwd: Path = work, reject: str | None = None) -> str:
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
        log = output / f"{len(report['commands']):03d}.log"
        log.write_text(process.stdout + process.stderr)
        report["commands"].append(
            {
                "command": command,
                "cwd": str(cwd),
                "seconds": time.monotonic() - start,
                "exit_code": process.returncode,
                "log": log.name,
                "expected_rejection": reject,
            }
        )
        save()
        if reject:
            if process.returncode == 0 or reject not in process.stderr + process.stdout:
                raise ValueError(f"negative case did not fail as expected: {log}")
        elif process.returncode:
            raise RuntimeError(f"command failed: {log}")
        return process.stdout

    mirror = output / "mirror"
    mirror.mkdir()
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0),
        functools.partial(QuietHandler, directory=str(mirror)),
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    installations = {}
    try:
        report["rust"] = run("rustc", "-vV")
        builder_dir = work / "builder"
        run("uv", "venv", builder_dir, "--python", sys.executable)
        builder = python_in(builder_dir)
        run(
            "uv",
            "pip",
            "install",
            "--python",
            builder,
            f"maturin=={args.maturin_version}",
        )
        for variant, sha in (("candidate", args.sha), ("baseline", args.baseline_sha)):
            source = output / f"source-{variant}"
            run("git", "worktree", "add", "--detach", source, sha, cwd=ROOT)
            version = tomllib.loads((source / "Cargo.toml").read_text())["package"][
                "version"
            ]
            if version != "0.30.0":
                raise ValueError(
                    "this candidate contract targets the six 0.30.0 SDK crates"
                )
            records = {
                "source_sha": sha,
                "version": version,
                "crates": [],
                "wheels": [],
            }
            report["variants"][variant] = records
            environment["CARGO_HOME"] = str(cache_home)
            environment["CARGO_TARGET_DIR"] = str(work / f"package-{variant}")
            run("cargo", "fetch", "--locked", cwd=source)
            for name in SDK:
                run(
                    "cargo",
                    "package",
                    "-p",
                    name,
                    "--no-verify",
                    "--exclude-lockfile",
                    "--offline",
                    cwd=source,
                )
                artifact = (
                    Path(environment["CARGO_TARGET_DIR"])
                    / "package"
                    / f"{name}-{version}.crate"
                )
                destination = output / variant / artifact.name
                destination.parent.mkdir(exist_ok=True)
                shutil.copyfile(artifact, destination)
                row = crate_metadata(destination, name, version, sha)
                row["path"] = str(destination.relative_to(output))
                records["crates"].append(row)
            local = mirror / variant
            records["mirror"] = cached_mirror(cache_home, local)
            (local / "config.json").write_text(
                json.dumps(
                    {"dl": f"{base}/{variant}/crates/{{crate}}/{{version}}/download"}
                )
            )
            for row in records["crates"]:
                artifact = output / row["path"]
                with tarfile.open(artifact) as archive:
                    manifest_file = archive.extractfile(
                        f"{row['name']}-{version}/Cargo.toml"
                    )
                    if manifest_file is None:
                        raise ValueError("missing packaged manifest")
                    manifest = tomllib.loads(manifest_file.read().decode())
                path = local / index_path(row["name"])
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(index_entry(manifest, row["sha256"])) + "\n")
                download = local / "crates" / row["name"] / version / "download"
                download.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(artifact, download)
            home = work / f"cargo-{variant}"
            home.mkdir()
            configuration = (
                '[source.crates-io]\nreplace-with = "candidate-local"\n'
                f'[source.candidate-local]\nregistry = "sparse+{base}/{variant}/"\n'
            )
            (home / "config.toml").write_text(configuration)
            environment.update(
                CARGO_HOME=str(home), CARGO_TARGET_DIR=str(work / f"target-{variant}")
            )
            candidate_source = {"mode": "candidate-registry", "version": version}
            project = generate(
                "maturin-starter",
                work / f"extension-{variant}",
                name="maturin-starter",
                authors="r2p candidate acceptance",
                source=candidate_source,
                root=source,
            )
            embedding = generate(
                "plugin",
                work / f"embedding-{variant}",
                name="plugin",
                authors="r2p candidate acceptance",
                source=candidate_source,
                root=source,
            )
            records["graphs"] = {}
            for consumer in (project, embedding):
                metadata = json.loads(
                    run("cargo", "metadata", "--format-version", "1", cwd=consumer)
                )
                records["graphs"][consumer.name] = registry_graph(
                    metadata, home, version, sha
                )
                lock = output / variant / f"{consumer.name}.lock"
                shutil.copyfile(consumer / "Cargo.lock", lock)
                records.setdefault("locks", {})[lock.name] = digest(lock)
            result = run("cargo", "run", "--locked", cwd=embedding)
            if "class, exception, and recovery passed" not in result:
                raise ValueError("registry embedding behavior failed")
            records["embedding"] = "success"
            # Fetch and compile the sixth SDK crate as a genuine registry dependency.
            cli_project = work / f"cli-{variant}"
            (cli_project / "src").mkdir(parents=True)
            (cli_project / "Cargo.toml").write_text(
                f'[package]\nname = "candidate-cli"\nversion = "0.1.0"\nedition = "2024"\n'
                f'[dependencies]\nr2p-introspection = "={version}"\n'
            )
            (cli_project / "src/main.rs").write_text(
                "fn main() { let _ = r2p_introspection::module_stub_files; }\n"
            )
            cli_metadata = json.loads(
                run("cargo", "metadata", "--format-version", "1", cwd=cli_project)
            )
            (cli_package,) = [
                package
                for package in cli_metadata["packages"]
                if package["name"] == "r2p-introspection"
            ]
            cli_source = Path(cli_package["manifest_path"]).parent
            if not cli_source.is_relative_to(home / "registry/src"):
                raise ValueError("CLI package did not come from the candidate registry")
            run("cargo", "run", "--locked", cwd=cli_project)
            for abi in ("native", "abi3", "cli"):
                wheel_dir = output / variant / abi
                flags = ("--features", "abi3") if abi == "abi3" else ()
                cwd = cli_source if abi == "cli" else project
                run(
                    builder,
                    "-m",
                    "maturin",
                    "build",
                    "--release",
                    "--interpreter",
                    sys.executable,
                    "--out",
                    wheel_dir,
                    *flags,
                    cwd=cwd,
                )
                (wheel,) = wheel_dir.glob("*.whl")
                # Maturin chooses the native platform; require the exact Python ABI.
                tag = wheel.stem.split("-", 2)[2]
                prefix = (
                    "py3-none-"
                    if abi == "cli"
                    else (
                        "cp39-abi3-"
                        if abi == "abi3"
                        else f"cp{sys.version_info.major}{sys.version_info.minor}-cp{sys.version_info.major}{sys.version_info.minor}-"
                    )
                )
                if not tag.startswith(prefix):
                    raise ValueError(f"unexpected wheel ABI: {wheel.name}")
                row = wheel_metadata(
                    wheel,
                    "r2p-introspection" if abi == "cli" else "maturin-starter",
                    version if abi == "cli" else "0.1.0",
                    tag,
                )
                row.update(
                    path=str(wheel.relative_to(output)), kind=abi, source_sha=sha
                )
                records["wheels"].append(row)
                if variant == "candidate":
                    install = work / f"install-{abi}"
                    run("uv", "venv", install, "--python", sys.executable)
                    installations[abi] = install
                else:
                    install = installations[abi]
                interpreter = python_in(install)
                run(
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    interpreter,
                    "--no-deps",
                    "--reinstall",
                    wheel,
                )
                if abi == "cli":
                    executable = install / (
                        "Scripts/r2p-introspection.exe"
                        if os.name == "nt"
                        else "bin/r2p-introspection"
                    )
                    behavior = check_cli(executable, output / variant / "cli-behavior")
                else:
                    behavior = json.loads(run(interpreter, "-I", "-c", BEHAVIOR))
                records.setdefault("behavior", {})[abi] = behavior
            if variant == "candidate":
                # These failures exercise Cargo/pip/import themselves in fresh
                # environments, rather than only testing metadata predicates.
                negative = generate(
                    "maturin-starter",
                    work / "negative-consumer",
                    name="negative-consumer",
                    authors="r2p negative admission",
                    source=candidate_source,
                    root=source,
                )
                original_manifest = (negative / "Cargo.toml").read_text()

                def fresh_home(
                    case: str, config: str = configuration, consumer: Path = negative
                ) -> None:
                    negative_home = work / f"cargo-negative-{case}"
                    negative_home.mkdir()
                    (negative_home / "config.toml").write_text(config)
                    environment["CARGO_HOME"] = str(negative_home)
                    (consumer / "Cargo.lock").unlink(missing_ok=True)

                fresh_home("version")
                (negative / "Cargo.toml").write_text(
                    original_manifest.replace(f"={version}", "=99.0.0")
                )
                run(
                    "cargo",
                    "metadata",
                    "--format-version",
                    "1",
                    cwd=negative,
                    reject="failed to select a version",
                )
                (negative / "Cargo.toml").write_text(original_manifest)
                fresh_home("dependency")
                index = local / index_path("r2p-ffi")
                retained = index.with_suffix(".retained")
                index.rename(retained)
                try:
                    run(
                        "cargo",
                        "metadata",
                        "--format-version",
                        "1",
                        cwd=negative,
                        reject="no matching package named",
                    )
                finally:
                    retained.rename(index)
                fresh_home("checksum")
                download = local / "crates/r2p-ffi" / version / "download"
                content = download.read_bytes()
                download.write_bytes(content + b"tampered")
                try:
                    run(
                        "cargo",
                        "fetch",
                        cwd=negative,
                        reject="failed to verify the checksum",
                    )
                finally:
                    download.write_bytes(content)
                environment["CARGO_HOME"] = str(home)
                interpreter = python_in(installations["native"])
                module = Path(records["behavior"]["native"]["module"])
                module = module.parent if module.name == "__init__.py" else module
                retained_module = module.with_name(module.name + ".retained")
                module.rename(retained_module)
                try:
                    run(
                        interpreter,
                        "-I",
                        "-c",
                        "import maturin_starter",
                        reject="ModuleNotFoundError",
                    )
                finally:
                    retained_module.rename(module)
                native = next(
                    row for row in records["wheels"] if row["kind"] == "native"
                )
                wrong_abi = work / Path(native["path"]).name.replace(
                    f"-cp{sys.version_info.major}{sys.version_info.minor}-cp{sys.version_info.major}{sys.version_info.minor}-",
                    "-cp38-cp38-",
                )
                shutil.copyfile(output / native["path"], wrong_abi)
                run(
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    interpreter,
                    "--no-deps",
                    wrong_abi,
                    reject="not compatible",
                )
                records["negative_admission"] = {
                    "wrong_version": "blocked",
                    "missing_dependency": "blocked",
                    "tampered_crate": "blocked",
                    "missing_import": "blocked",
                    "wrong_abi": "blocked",
                }
            records["registry_result"] = "success"
            save()
        report["restoration"] = {
            "result": "success",
            "scope": "Local candidate → retained baseline packages and wheels; registry homes are independent and the same three wheel install environments were explicitly reinstalled.",
            "source_sha": args.baseline_sha,
            "commands": "baseline registry cargo run and uv pip install --reinstall followed by the identical behavior probes",
        }
        if digest(ROOT / "Cargo.lock") != lock_digest:
            raise ValueError("primary workspace lock changed")
        report["workspace_lock_sha256"] = lock_digest
        report["result"] = "success"
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        save()
        verify_manifest(output / "manifest.json", args.sha)
    finally:
        server.shutdown()
        server.server_close()
        save()
    print(f"Candidate local acceptance passed: {output / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
