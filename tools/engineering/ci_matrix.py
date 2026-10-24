"""Supported PR/full build cells, shared by selection, execution, and validation."""

from __future__ import annotations

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


def cell(platform: str, python: str = "3.14", rust: str = "stable") -> dict:
    os, architecture, target = PLATFORMS[platform]
    return {
        "rust": rust,
        "python-version": python,
        "platform": {
            "os": os,
            "python-architecture": architecture,
            "rust-target": target,
        },
    }


def build_matrices(msrv: str) -> dict:
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
    full += [cell("linux-x64", rust=rust) for rust in (msrv, "nightly", "beta")]
    full += [cell("win-x86"), cell("mac-x64"), cell("mac-intel", "3.9")]
    full += [
        cell(platform, python)
        for platform in ("linux-arm", "win-arm")
        for python in ("3.14", "3.14t")
    ]
    return {"pr": {"include": pr}, "full": {"include": full}}
