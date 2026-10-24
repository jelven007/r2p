"""Explicit tool/target interpreter metadata and isolated source snapshots."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

PYTHON_PROBE = """\
import json, sys, sysconfig
print(json.dumps({
    "executable": sys.executable,
    "implementation": sys.implementation.name,
    "version": list(sys.version_info[:3]),
    "free_threaded": bool(sysconfig.get_config_var("Py_GIL_DISABLED")),
    "platform": sysconfig.get_platform(),
    "base_prefix": sys.base_prefix,
}))
"""


def probe_python(executable: str) -> dict:
    return json.loads(
        subprocess.check_output([executable, "-c", PYTHON_PROBE], text=True)
    )


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def environment_snapshot(
    root: Path, tool_python: str, target_python: str, arguments: list[str]
) -> dict:
    def output(*command: str) -> str:
        return subprocess.check_output(command, cwd=root, text=True).strip()

    config = os.environ.get("R2P_CONFIG_FILE")
    rust = output("rustc", "-vV").splitlines()
    host = next(
        line.removeprefix("host: ") for line in rust if line.startswith("host: ")
    )
    return {
        "schema_version": 1,
        "source_sha": output("git", "rev-parse", "HEAD"),
        "dirty": bool(output("git", "status", "--porcelain")),
        "tool_python": probe_python(tool_python),
        "target_python": probe_python(target_python),
        "rust": rust,
        "target": os.environ.get("CARGO_BUILD_TARGET", host),
        "nox_arguments": arguments,
        "configuration": {
            key: os.environ[key]
            for key in (
                "R2P_CROSS",
                "R2P_CROSS_LIB_DIR",
                "R2P_CROSS_PYTHON_VERSION",
                "R2P_CROSS_PYTHON_IMPLEMENTATION",
                "R2P_BUILD_EXTENSION_MODULE",
                "R2P_WIP_NO_STD",
                "UI_TEST",
                "RUSTFLAGS",
                "RUSTDOCFLAGS",
            )
            if key in os.environ
        },
        "config_file": {
            "path": config,
            "sha256": digest(Path(config)) if config else None,
        },
        "locks": {name: digest(root / name) for name in ("Cargo.lock", "uv.lock")},
    }


def isolated_source(root: Path, parent: Path) -> Path:
    """Copy current tracked/nonignored sources, including uncommitted edits.

    Unlike a worktree/archive this validates the actual candidate on disk. Avoid
    recursive copies of caches and never modify the source checkout's lockfiles.
    Keep the snapshot and generated locks available after success or failure.
    """
    paths = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
    ).split(b"\0")
    parent.mkdir(parents=True, exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix="checkout-", dir=parent))
    for relative in sorted(set(filter(None, paths))):
        source = root / os.fsdecode(relative)
        if not source.exists() and not source.is_symlink():
            continue
        target = destination / source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=False)
    return destination
