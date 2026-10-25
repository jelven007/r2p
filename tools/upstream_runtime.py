"""Replay historical upstream runtime repairs with preserved source provenance."""

from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

from tools.engineering.environment import digest, probe_python

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = "7ed9ac01341592cfaa631e592bd816c88b620aad"
SOURCE_PARENT = "6a930e9de1fa7eb3783bfdbb4f7df6e4207cb08e"
GC_UPSTREAM = "5619fedbca3ad1baca82869b57df54afd0432a0b"


def git(*arguments: str, cwd: Path = ROOT) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=cwd)


def mapped_patch(source_sha: str, files: tuple[str, ...]) -> bytes:
    if (
        source_sha != UPSTREAM
        or git("rev-parse", source_sha + "^").decode().strip() != SOURCE_PARENT
    ):
        raise ValueError("runtime repair source/parent differs")
    original = git("diff", source_sha + "^", source_sha, "--", *files)
    if (
        not original
        or b"ATTACH_COUNT" not in original
        and files == ("src/internal/state.rs",)
    ):
        raise ValueError("runtime source patch is absent")
    return original.replace(
        b"pytests/src/misc.rs", b"tests/python/src/misc.rs"
    ).replace(b"pyo3", b"r2p")


def regression_program(test_file: Path, module_dir: Path) -> str:
    """Keep the original test body/GC loop, running the chosen test at shutdown."""
    tree = ast.parse(test_file.read_text())
    tree.body = [
        node
        for node in tree.body
        if not isinstance(node, ast.Import)
        or not any(alias.name == "pytest" for alias in node.names)
    ]
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            node.decorator_list.clear()
    return (
        "import sys, resource\n"
        "resource.setrlimit(resource.RLIMIT_CORE, (0, 0))\n"
        f"sys.path.insert(0, {str(module_dir)!r})\n"
        + ast.unparse(tree)
        + "\ntest_detach_during_finalization()\nprint('regression ready for interpreter finalization', flush=True)\n"
    )


def replay_gc(sha: str, executable: str, destination: Path) -> int:
    metadata = probe_python(executable)
    if metadata["implementation"] != "cpython" or metadata["version"][:2] != [3, 14]:
        raise ValueError("GC replay uses native CPython 3.14")
    destination = destination.resolve()
    destination.mkdir(parents=True)
    checkout = destination / "checkout"
    checkout.mkdir()
    with tarfile.open(fileobj=io.BytesIO(git("archive", sha))) as archive:
        archive.extractall(checkout, filter="data")
    git("init", "--quiet", cwd=checkout)
    path = "src/pycell/impl_.rs"
    accepted = (checkout / path).read_text()
    source_hashes = {
        name: digest(ROOT / name) for name in (path, "tests/test_gc.rs", "Cargo.lock")
    }
    original = git("format-patch", "-1", "--stdout", GC_UPSTREAM)
    fixed_lookup = """\
        let type_obj = T::lazy_type_object()
            .get_during_gc()
            .as_ptr()
            .cast::<ffi::PyTypeObject>();"""
    old_lookup = "        let type_obj = T::type_object_raw(unsafe { Python::assume_attached() });"
    upstream_before = git("show", GC_UPSTREAM + "^:" + path).decode()
    upstream_after = git("show", GC_UPSTREAM + ":" + path).decode()
    if (
        not original.startswith(f"From {GC_UPSTREAM} ".encode())
        or fixed_lookup not in upstream_after
        or old_lookup not in upstream_before
        or accepted.count(fixed_lookup) != 1
    ):
        raise ValueError("GC lookup is not bound to the historical repair")
    broken = accepted.replace(fixed_lookup, old_lookup)
    patch = (
        f"diff --git a/{path} b/{path}\n"
        + "".join(
            difflib.unified_diff(
                broken.splitlines(keepends=True),
                accepted.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )
    ).encode()
    (destination / "upstream.patch").write_bytes(original)
    (destination / "mapped-lookup.patch").write_bytes(patch)
    source_patch = git("diff", GC_UPSTREAM + "^", GC_UPSTREAM).replace(b"pyo3", b"r2p")
    conflict = subprocess.run(
        ["git", "apply", "--reverse", "--check", "-"],
        input=source_patch,
        cwd=checkout,
        capture_output=True,
        check=False,
    )
    test_name = "test_gc_during_classattr_initialization"
    test_source = (checkout / "tests/test_gc.rs").read_text()
    # Later formatting/namespace changes require mapping only this semantic
    # lookup delta. Keep the GC-safe guard and other inherited dependencies.
    evidence = {
        "schema_version": 1,
        "source_sha": sha,
        "upstream_sha": GC_UPSTREAM,
        "upstream_parent": git("rev-parse", GC_UPSTREAM + "^").decode().strip(),
        "source_patch_sha256": hashlib.sha256(original).hexdigest(),
        "mapped_patch_sha256": hashlib.sha256(patch).hexdigest(),
        "full_reverse_exit_code": conflict.returncode,
        "full_reverse_conflicts": conflict.stderr.decode(),
        "python": metadata,
        "scope": "controlled reversal/replay of type-data lookup delta from inherited #6453; preserves GC guard/dependencies; no new upstream runtime update",
        "runtime_before_sha256": hashlib.sha256(broken.encode()).hexdigest(),
        "runtime_after_sha256": hashlib.sha256(accepted.encode()).hexdigest(),
        "regression_source_sha256": hashlib.sha256(test_source.encode()).hexdigest(),
        "results": [],
        "result": "incomplete",
    }
    if (
        test_name not in test_source
        or test_name not in git("show", GC_UPSTREAM + ":tests/test_gc.rs").decode()
    ):
        raise ValueError("historical GC regression is absent")
    subprocess.run(
        ["git", "apply", "--reverse", "--check", "-"],
        input=patch,
        cwd=checkout,
        check=True,
    )
    subprocess.run(
        ["git", "apply", "--reverse", "-"], input=patch, cwd=checkout, check=True
    )
    environment = os.environ | {
        "R2P_PYTHON": metadata["executable"],
        "CARGO_TARGET_DIR": os.environ.get(
            "CARGO_TARGET_DIR", str(destination / "build")
        ),
        "RUSTUP_TOOLCHAIN": "stable",
        "CARGO_BUILD_JOBS": "4",
    }
    evidence["cargo_target"] = environment["CARGO_TARGET_DIR"]
    command = [
        "cargo",
        "test",
        "--locked",
        "--offline",
        "--no-default-features",
        "--features",
        "macros",
        "--test",
        "test_gc",
        test_name,
        "--",
        "--exact",
        "--nocapture",
    ]
    for variant in ("broken", "replayed"):
        if variant == "replayed":
            subprocess.run(
                ["git", "apply", "--check", "-"], input=patch, cwd=checkout, check=True
            )
            subprocess.run(["git", "apply", "-"], input=patch, cwd=checkout, check=True)
        for repeat in range(3):
            log = destination / f"{variant}-{repeat}.log"
            with log.open("w") as stream:
                result = subprocess.run(
                    command,
                    cwd=checkout,
                    env=environment,
                    stdout=stream,
                    stderr=stream,
                    timeout=180,
                    check=False,
                )
            text = log.read_text()
            evidence["results"].append(
                {
                    "variant": variant,
                    "repeat": repeat,
                    "exit_code": result.returncode,
                    "log_sha256": digest(log),
                    "command": command,
                }
            )
            (destination / "evidence.json").write_text(
                json.dumps(evidence, indent=2) + "\n"
            )
            if test_name not in text or (
                variant == "broken"
                and (
                    result.returncode == 0
                    or "class attribute initializer called more than once" not in text
                )
                or variant == "replayed"
                and (result.returncode != 0 or "1 passed" not in text)
            ):
                raise ValueError(
                    f"{variant} GC regression differs; inspect retained log"
                )
            print(
                f"{variant} GC regression {repeat}: exit={result.returncode}",
                flush=True,
            )
    if (checkout / path).read_text() != accepted or source_hashes != {
        name: digest(ROOT / name) for name in source_hashes
    }:
        raise ValueError("GC replay changed source/lock invariants")
    evidence["result"] = "success"
    evidence["source_invariants"] = "unchanged"
    (destination / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--repair", choices=("gc", "finalization"), default="gc")
    parser.add_argument("--target-python")
    parser.add_argument("--legacy-python")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch("[0-9a-f]{40}", args.sha) or args.output.exists():
        parser.error("use an immutable source SHA and a new output directory")
    if args.repair == "gc":
        if not args.target_python:
            parser.error("GC replay requires --target-python")
        return replay_gc(args.sha, args.target_python, args.output)
    if not args.legacy_python:
        parser.error("finalization replay requires --legacy-python")
    metadata = probe_python(args.legacy_python)
    if metadata["implementation"] != "cpython" or metadata["version"][:2] != [3, 9]:
        parser.error("this historical negative regression requires CPython 3.9")
    if os.name != "posix":
        parser.error("this controlled regression currently uses native POSIX shutdown")
    output = args.output.resolve()
    output.mkdir(parents=True)
    checkout = output / "checkout"
    checkout.mkdir()
    archive = git("archive", args.sha)
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        source.extractall(checkout, filter="data")
    git("init", "--quiet", cwd=checkout)
    original = git("format-patch", "-1", "--stdout", UPSTREAM)
    if not original.startswith(f"From {UPSTREAM} ".encode()):
        raise ValueError("original upstream source header differs")
    full = mapped_patch(UPSTREAM, ("src/internal/state.rs", "pytests/src/misc.rs"))
    runtime = mapped_patch(UPSTREAM, ("src/internal/state.rs",))
    for name, patch in (
        ("upstream.patch", original),
        ("mapped.patch", full),
        ("runtime.patch", runtime),
    ):
        (output / name).write_bytes(patch)
    files = ["src/internal/state.rs", "tests/python/src/misc.rs"]
    accepted_hashes = {name: digest(checkout / name) for name in files}
    source_hashes = {name: digest(ROOT / name) for name in files + ["Cargo.lock"]}
    subprocess.run(
        ["git", "apply", "--reverse", "--check", "-"],
        input=full,
        cwd=checkout,
        check=True,
    )
    subprocess.run(
        ["git", "apply", "--reverse", "-"], input=full, cwd=checkout, check=True
    )
    conflict = subprocess.run(
        ["git", "apply", "--check", "-"],
        input=original,
        cwd=checkout,
        capture_output=True,
        check=False,
    )
    if conflict.returncode == 0:
        raise ValueError(
            "original unmapped patch unexpectedly applies to renamed paths"
        )
    subprocess.run(
        ["git", "apply", "--check", "-"], input=full, cwd=checkout, check=True
    )
    subprocess.run(["git", "apply", "-"], input=full, cwd=checkout, check=True)
    if accepted_hashes != {name: digest(checkout / name) for name in files}:
        raise ValueError(
            "mapped replay changed the accepted local runtime/test content"
        )
    harness = output / "regression"
    (harness / "src").mkdir(parents=True)
    shutil.copy2(checkout / "tests/python/src/misc.rs", harness / "src/misc.rs")
    (harness / "src/lib.rs").write_text(
        "mod misc;\n"
        "#[r2p::pymodule]\nmod r2p_pytests {\n"
        "    #[pymodule_export]\n    use super::misc::misc;\n}\n"
    )
    (harness / "Cargo.toml").write_text(
        '[package]\nname = "r2p-runtime-replay"\nversion = "0.1.0"\nedition = "2024"\npublish = false\n'
        '[lib]\nname = "r2p_pytests"\ncrate-type = ["cdylib"]\n'
        f'[dependencies]\nr2p = {{ path = {json.dumps(str(checkout))}, features = ["extension-module"] }}\n'
        f"[build-dependencies]\nr2p-build-config = {{ path = {json.dumps(str(checkout / 'crates/r2p-build-config'))} }}\n"
        "[workspace]\n"
    )
    (harness / "build.rs").write_text(
        "fn main() { r2p_build_config::add_extension_module_link_args(); }\n"
    )
    environment = os.environ | {
        "R2P_PYTHON": metadata["executable"],
        "CARGO_TARGET_DIR": str(output / "build"),
        "RUSTUP_TOOLCHAIN": "stable",
        "CARGO_BUILD_JOBS": "4",
    }
    subprocess.run(
        ["cargo", "generate-lockfile", "--offline"],
        cwd=harness,
        env=environment,
        check=True,
    )
    evidence = {
        "schema_version": 1,
        "source_sha": args.sha,
        "upstream_sha": UPSTREAM,
        "upstream_parent": SOURCE_PARENT,
        "source_patch_sha256": hashlib.sha256(original).hexdigest(),
        "mapped_patch_sha256": hashlib.sha256(full).hexdigest(),
        "original_conflict_exit_code": conflict.returncode,
        "original_conflicts": conflict.stderr.decode(),
        "replay_hashes": accepted_hashes,
        "python": metadata,
        "lock_sha256": digest(harness / "Cargo.lock"),
        "regression_source_sha256": digest(
            checkout / "tests/python/tests/test_finalization.py"
        ),
        "scope": "controlled reverse/replay of an already inherited historical runtime fix; no new upstream runtime change",
        "result": "incomplete",
        "results": [],
    }
    (output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    module_dir = output / "module"
    module_dir.mkdir()
    program = regression_program(
        checkout / "tests/python/tests/test_finalization.py", module_dir
    )
    (output / "regression.py").write_text(program)
    subprocess.run(
        ["git", "apply", "--reverse", "-"], input=runtime, cwd=checkout, check=True
    )
    for variant in ("broken", "replayed"):
        if variant == "replayed":
            subprocess.run(
                ["git", "apply", "--check", "-"],
                input=runtime,
                cwd=checkout,
                check=True,
            )
            subprocess.run(
                ["git", "apply", "-"], input=runtime, cwd=checkout, check=True
            )
        with (output / f"{variant}-build.log").open("w") as log:
            subprocess.run(
                ["cargo", "build", "--locked", "--offline"],
                cwd=harness,
                env=environment,
                stdout=log,
                stderr=log,
                check=True,
            )
        binary = (
            Path(environment["CARGO_TARGET_DIR"])
            / "debug"
            / (
                "libr2p_pytests.dylib"
                if __import__("sys").platform == "darwin"
                else "libr2p_pytests.so"
            )
        )
        shutil.copy2(binary, module_dir / "r2p_pytests.so")
        for repeat in range(3):
            result = subprocess.run(
                [metadata["executable"], "-I", "-c", program],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            (output / f"{variant}-{repeat}.stdout").write_text(result.stdout)
            (output / f"{variant}-{repeat}.stderr").write_text(result.stderr)
            evidence["results"].append(
                {
                    "variant": variant,
                    "repeat": repeat,
                    "exit_code": result.returncode,
                    "binary_sha256": digest(binary),
                }
            )
            (output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
            if (
                "regression ready for interpreter finalization" not in result.stdout
                or variant == "broken"
                and (result.returncode == 0 or "PyThreadState_Get" not in result.stderr)
                or variant == "replayed"
                and result.returncode != 0
            ):
                raise ValueError(
                    f"{variant} finalization regression differs; inspect retained logs"
                )
            print(
                f"{variant} finalization {repeat}: exit={result.returncode}", flush=True
            )
    if accepted_hashes != {
        name: digest(checkout / name) for name in files
    } or source_hashes != {name: digest(ROOT / name) for name in source_hashes}:
        raise ValueError("local runtime/test/lock invariant changed")
    evidence["result"] = "success"
    evidence["source_invariants"] = "unchanged"
    (output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
