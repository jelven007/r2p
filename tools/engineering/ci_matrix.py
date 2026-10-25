"""Execution cells and release policy, shared by workflows and acceptance."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

import tomllib

PLATFORMS = {
    "mac-arm": ("macos-latest", "arm64", "aarch64-apple-darwin"),
    "linux-x64": ("ubuntu-latest", "x64", "x86_64-unknown-linux-gnu"),
    "linux-arm": ("ubuntu-24.04-arm", "arm64", "aarch64-unknown-linux-gnu"),
    "win-x64": ("windows-latest", "x64", "x86_64-pc-windows-msvc"),
    "win-x86": ("windows-latest", "x86", "i686-pc-windows-msvc"),
    "win-arm": ("windows-11-arm", "arm64", "aarch64-pc-windows-msvc"),
    "mac-x64": ("macos-latest", "x64", "x86_64-apple-darwin"),
    "mac-intel": ("macos-15-intel", "x64", "x86_64-apple-darwin"),
}
PYTHONS = (
    "3.9",
    "3.10",
    "3.11",
    "3.12",
    "3.13",
    "3.14",
    "3.14t",
    "3.15",
    "3.15t",
    "pypy3.11",
    "pypy3.12",
    "graalpy25.4",
)
CLIPPY_TARGETS = (
    PLATFORMS["mac-arm"][2],
    PLATFORMS["linux-x64"][2],
    PLATFORMS["linux-arm"][2],
    "powerpc64le-unknown-linux-gnu",
    "s390x-unknown-linux-gnu",
    "wasm32-wasip1",
    PLATFORMS["win-x64"][2],
    PLATFORMS["win-x86"][2],
    PLATFORMS["win-arm"][2],
)
CLI_PLATFORMS = {
    "linux-x86_64": (
        "linux-x64",
        "x86_64",
        ("manylinux", "musllinux_", "linux_"),
        "x86_64",
    ),
    "linux-aarch64": (
        "linux-arm",
        "aarch64",
        ("manylinux", "musllinux_", "linux_"),
        "aarch64",
    ),
    "windows-x64": ("win-x64", "x64", ("win_amd64",), ""),
    "windows-x86": ("win-x86", "x86", ("win32",), ""),
    "windows-aarch64": ("win-arm", "aarch64", ("win_arm64",), ""),
    "macos-x86_64": ("mac-intel", "x86_64", ("macosx_",), "x86_64"),
    "macos-aarch64": ("mac-arm", "aarch64", ("macosx_",), "arm64"),
}
MATRIX_JOBS = {
    "build-pr": "pr",
    "build-full": "full",
    "clippy": "clippy",
    "check-nightly": "nightly",
    "no_std": "no_std",
    "pytests-type-checking": "typing",
    "check-feature-powerset": "powerset",
    "test-cross-compilation": "cross",
    "test-introspection": "introspection",
}
PROSPECTIVE_TOOLCHAINS = {"nightly", "beta"}


def policy(identifier: str, name: str, rust: str = "stable", **fields) -> dict:
    prospective = rust in PROSPECTIVE_TOOLCHAINS
    return {
        "id": identifier,
        "name": name,
        "rust": rust,
        "support": "prospective" if prospective else "supported",
        "allow-failure": prospective,
        "allowed-results": ["success", "failure"] if prospective else ["success"],
        **fields,
    }


def cell(
    platform: str,
    python: str = "3.14",
    rust: str = "stable",
    *,
    role: str | None = None,
) -> dict:
    os, architecture, target = PLATFORMS[platform]
    return policy(
        f"build/{platform}/{python}/{role or rust}",
        f"python{python}-{architecture} {os} rust-{rust}",
        rust,
        **{
            "python-version": python,
            "runner": os,
            "target": target,
            "architecture": architecture,
            "platform": {
                "os": os,
                "python-architecture": architecture,
                "rust-target": target,
            },
        },
    )


def cli_matrix() -> dict:
    return {
        "include": [
            policy(
                f"cli/{identifier}",
                f"cli/{identifier}",
                runner=PLATFORMS[platform][0],
                target=target,
                **{
                    "rust-target": PLATFORMS[platform][2],
                    "python-architecture": PLATFORMS[platform][1],
                    "python-version": "3.14",
                    "platform-id": identifier,
                },
            )
            for identifier, (platform, target, _, _) in CLI_PLATFORMS.items()
        ]
    }


def build_matrices(msrv: str) -> dict:
    if not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", msrv):
        raise ValueError("MSRV must be a numeric Rust version")
    pr = [
        cell(platform)
        for platform in (
            "mac-arm",
            "linux-x64",
            "linux-arm",
            "win-x64",
            "win-x86",
            "win-arm",
        )
    ]
    pr += [cell("linux-x64", rust="nightly")]
    pr += [cell("linux-x64", python) for python in ("3.14t", "3.15", "3.15t")]
    full = [
        cell(platform, python)
        for python in PYTHONS
        for platform in ("mac-arm", "linux-x64", "win-x64")
        if (platform, python) != ("mac-arm", "3.9")
    ]
    full += [cell("linux-x64", rust=msrv, role="msrv")]
    full += [cell("linux-x64", rust=rust) for rust in ("nightly", "beta")]
    full += [cell("win-x86"), cell("mac-x64"), cell("mac-intel", "3.9")]
    full += [
        cell(platform, python)
        for platform in ("linux-arm", "win-arm")
        for python in ("3.14", "3.14t")
    ]
    clippy = [
        policy(
            f"clippy/{target}/{rust}",
            f"clippy/{target}/{rust}",
            rust,
            runner="ubuntu-24.04-arm",
            target=target,
            **{"python-version": "3.14"},
        )
        for rust, targets in (
            ("stable", CLIPPY_TARGETS),
            ("beta", (PLATFORMS["linux-x64"][2],)),
        )
        for target in targets
    ]
    introspection = []
    for platform in ("mac-arm", "linux-x64", "win-x64", "win-x86"):
        row = cell(platform)
        os, architecture, target = PLATFORMS[platform]
        row.update(
            policy(
                f"introspection/{platform}",
                f"test-introspection ({os}, {architecture}, {target})",
            )
        )
        introspection.append(row)
    cross = [
        policy(
            f"cross/{host}/{target}",
            f"test-cross-compilation {PLATFORMS[host][0]} -> {target}",
            runner=PLATFORMS[host][0],
            os=PLATFORMS[host][0],
            target=target,
            architecture=PLATFORMS[host][1],
            flags="-i python3.13",
            manylinux=manylinux,
            **{"python-version": "3.13", "apt-packages": packages},
        )
        for host, target, manylinux, packages in (
            ("linux-x64", "x86_64-unknown-linux-gnu", "auto", ""),
            ("linux-x64", "aarch64-unknown-linux-gnu", "auto", ""),
            ("linux-x64", "x86_64-pc-windows-gnu", "", "mingw-w64 llvm"),
            ("win-x64", "aarch64-pc-windows-msvc", "", ""),
        )
    ]
    matrices = {
        "pr": {"include": pr},
        "full": {"include": full},
        "clippy": {"include": clippy},
        "nightly": {
            "include": [
                policy(
                    "nightly/linux-x64",
                    f"check-nightly/{PLATFORMS['linux-x64'][2]}/nightly",
                    "nightly",
                    runner="ubuntu-24.04-arm",
                    target=PLATFORMS["linux-x64"][2],
                    **{"python-version": "3.14"},
                )
            ]
        },
        "introspection": {"include": introspection},
        "cross": {"include": cross},
        "powerset": {
            "include": [
                policy(
                    f"powerset/{role}",
                    f"check-feature-powerset {rust}",
                    rust,
                    runner=PLATFORMS["linux-x64"][0],
                    target=PLATFORMS["linux-x64"][2],
                    **{"python-version": "3.15"},
                )
                for role, rust in (("stable", "stable"), ("msrv", msrv))
            ]
        },
        "no_std": {
            "include": [
                policy(
                    f"no_std/{session}",
                    f"no_std ({session})",
                    session=session,
                    runner=PLATFORMS["linux-x64"][0],
                    target=PLATFORMS["linux-x64"][2],
                    **{"python-version": "3.14"},
                )
                for session in ("test-py", "test-rust", "clippy")
            ]
        },
        "typing": {
            "include": [
                policy(
                    f"typing/{checker}",
                    f"pytests-type-checking ({checker})",
                    checker=checker,
                    runner=PLATFORMS["linux-x64"][0],
                    target=PLATFORMS["linux-x64"][2],
                    **{"python-version": "3.14"},
                )
                for checker in ("mypy", "pyrefly")
            ]
        },
        "cli": cli_matrix(),
    }
    for name, matrix in matrices.items():
        rows = matrix["include"]
        if (
            not rows
            or len({row["id"] for row in rows}) != len(rows)
            or len({row["name"] for row in rows}) != len(rows)
        ):
            raise ValueError(f"empty or duplicate execution cells: {name}")
    return matrices


def release_cells(msrv: str) -> dict[str, dict]:
    matrices = build_matrices(msrv)
    return {
        row["name"] + (" / build" if key == "full" else ""): row
        for key in MATRIX_JOBS.values()
        if key != "pr"
        for row in matrices[key]["include"]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-output", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    msrv = tomllib.loads((root / "Cargo.toml").read_text())["workspace"]["package"][
        "rust-version"
    ]
    matrices = build_matrices(msrv)
    if args.github_output:
        with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
            print(
                "cli-matrix=" + json.dumps(matrices["cli"], separators=(",", ":")),
                file=output,
            )
    else:
        print(json.dumps(matrices, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
