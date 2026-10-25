"""Install a native CLI wheel, execute it, and bind the tested digest to its source."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

import tomllib

from tools.candidate_artifacts import ROOT, check_cli, digest, wheel_metadata
from tools.consumer_smoke import python_in
from tools.engineering.ci_matrix import CLI_PLATFORMS

PLATFORMS = CLI_PLATFORMS.keys()


def matches_platform(tag: str, platform_id: str) -> bool:
    if not tag.startswith("py3-none-") or platform_id not in CLI_PLATFORMS:
        return False
    platforms = tag.split("-", 2)[2].split(".")
    _, _, prefixes, architecture = CLI_PLATFORMS[platform_id]
    if not architecture:
        return platforms == list(prefixes)
    return all(
        value.startswith(prefixes) and value.endswith("_" + architecture)
        for value in platforms
    )


def verify_set(directory: Path, sha: str, version: str) -> list[dict]:
    records = [
        json.loads(path.read_text()) for path in directory.glob("cli-acceptance-*.json")
    ]
    if (
        len(records) != len(PLATFORMS)
        or {row["platform_id"] for row in records} != PLATFORMS
    ):
        raise ValueError("missing or duplicate native wheel platform acceptance")
    wheels = set()
    for row in records:
        path = directory / row["artifact"]["path"]
        if (
            row.get("schema_version") != 1
            or row["source_sha"] != sha
            or row["result"] != "success"
            or row["behavior"]["result"] != "success"
            or not matches_platform(row["artifact"]["filename_tag"], row["platform_id"])
            or path.parent != directory
            or digest(path) != row["artifact"]["sha256"]
        ):
            raise ValueError("CLI acceptance source/behavior/artifact mismatch")
        wheel_metadata(
            path, "r2p-introspection", version, row["artifact"]["filename_tag"]
        )
        wheels.add(path.name)
    if len(wheels) != len(PLATFORMS) or wheels != {
        path.name for path in directory.glob("*.whl")
    }:
        raise ValueError("unaccepted wheel is present in the publish directory")
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--dist", required=True, type=Path)
    parser.add_argument("--platform-id", choices=sorted(PLATFORMS))
    parser.add_argument("--verify-set", action="store_true")
    args = parser.parse_args()
    source = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    version = tomllib.loads((ROOT / "Cargo.toml").read_text())["package"]["version"]
    if source != args.sha:
        parser.error("wheel source differs from the checked-out commit")
    if args.verify_set:
        verify_set(args.dist, args.sha, version)
        print(
            f"All {len(PLATFORMS)} native CLI wheels have matching source, digest and successful execution"
        )
        return 0
    if not args.platform_id:
        parser.error("--platform-id is required for native execution")
    (wheel,) = args.dist.glob("*.whl")
    tag = wheel.stem.split("-", 2)[2]
    if not matches_platform(tag, args.platform_id):
        parser.error("CLI wheel ABI/platform differs from the native platform ID")
    metadata = wheel_metadata(wheel, "r2p-introspection", version, tag)
    install = Path(tempfile.mkdtemp(prefix="r2p-cli-wheel-")) / "venv"
    subprocess.run(["uv", "venv", str(install), "--python", sys.executable], check=True)
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python_in(install)),
            "--no-deps",
            str(wheel.resolve()),
        ],
        check=True,
    )
    executable = install / (
        "Scripts/r2p-introspection.exe" if os.name == "nt" else "bin/r2p-introspection"
    )
    behavior = check_cli(executable, install.parent / "behavior")
    record = {
        "schema_version": 1,
        "source_sha": source,
        "platform_id": args.platform_id,
        "host": platform.platform(),
        "python": sys.version,
        "artifact": metadata | {"path": wheel.name},
        "behavior": behavior,
        "result": "success",
    }
    (args.dist / f"cli-acceptance-{args.platform_id}.json").write_text(
        json.dumps(record, indent=2) + "\n"
    )
    print(f"CLI wheel accepted after isolated native execution: {wheel.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
