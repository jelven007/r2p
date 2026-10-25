"""Create a local immutable version fixture; never change the primary SDK version."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import tomllib

from tools.candidate_artifacts import ROOT, release_version, source_version


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", default="0.30.1")
    parser.add_argument("--consumer-version", default="0.2.0")
    args = parser.parse_args()
    version = release_version(args.version)
    consumer_version = release_version(args.consumer_version)
    destination = args.output.resolve()
    if destination.exists() or not destination.is_relative_to(ROOT / "target"):
        parser.error("fixture must be a new directory within this repository's target")
    parent = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    old = source_version(ROOT)
    if old == version:
        parser.error("fixture version must differ from the SDK version")
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(destination), parent],
        cwd=ROOT,
        check=True,
    )
    tracked = (
        subprocess.check_output(["git", "ls-files", "-z"], cwd=destination)
        .decode()
        .split("\0")
    )
    for relative in tracked:
        if relative.endswith("Cargo.toml") or relative == "Cargo.lock":
            path = destination / relative
            path.write_text(path.read_text().replace(old, version))
    consumer = destination / "examples/maturin-starter"
    old_consumer = tomllib.loads((consumer / "pyproject.toml").read_text())["project"][
        "version"
    ]
    for path in (
        consumer / "pyproject.toml",
        consumer / ".template/Cargo.toml",
        consumer / "Cargo.toml",
    ):
        path.write_text(
            path.read_text().replace(
                f'version = "{old_consumer}"', f'version = "{consumer_version}"'
            )
        )
    marker = {
        "schema_version": 1,
        "fixture_only": True,
        "parent": parent,
        "sdk_version": version,
        "consumer_version": consumer_version,
        "purpose": "Local cross-version candidate/restore validation; external publishing forbidden.",
    }
    (destination / "docs/governance/release-fixture.json").write_text(
        json.dumps(marker, indent=2) + "\n"
    )
    source_version(destination)
    subprocess.run(["git", "add", "-A"], cwd=destination, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=jelven",
            "-c",
            "user.email=24818820+jelven007@users.noreply.github.com",
            "commit",
            "-m",
            f"Local fixture only: SDK {version}, consumer {consumer_version}",
        ],
        cwd=destination,
        check=True,
    )
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=destination, text=True
    ).strip()
    subprocess.run(
        ["git", "update-ref", f"refs/r2p-fixtures/sdk-{version}", sha],
        cwd=ROOT,
        check=True,
    )
    print(
        json.dumps(marker | {"source_sha": sha, "checkout": str(destination)}, indent=2)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
