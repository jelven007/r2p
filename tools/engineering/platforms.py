"""Cross-compilation metadata, independent of Nox session registration."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path


class EmscriptenInfo:
    def __init__(self, root: Path, version: str):
        self.emscripten_dir = root / "infrastructure" / "wasm" / "emscripten"
        self.builddir = root / ".nox/emscripten"
        self.builddir.mkdir(exist_ok=True, parents=True)
        self.pyversion = version.split()[0]
        self.pymajor, self.pyminor, self.pymicro = self.pyversion.split(".")
        self.pymicro, self.pydev = re.match(
            "([0-9]*)([^0-9].*)?", self.pymicro
        ).groups()
        if self.pydev is None:
            self.pydev = ""
        self.pymajorminor = f"{self.pymajor}.{self.pyminor}"
        self.pymajorminormicro = f"{self.pymajorminor}.{self.pymicro}"


class WasiInfo:
    def __init__(self, root: Path, version: str, environment: Mapping[str, str]):
        self.wasi_dir = root / "infrastructure" / "wasm" / "wasi"
        self.builddir = root / ".nox/wasi"
        self.builddir.mkdir(exist_ok=True, parents=True)
        self.pyversion = version.split()[0]
        self.pymajor, self.pyminor = self.pyversion.split(".")[:2]
        self.pymajorminor = f"{self.pymajor}.{self.pyminor}"
        wasi_sdk_env = environment.get("WASI_SDK_PATH")
        self.wasi_sdk = (
            Path(wasi_sdk_env) if wasi_sdk_env else self.builddir / "wasi-sdk"
        )
        self.cpython_dir = self.builddir / "build" / f"Python-{self.pyversion}"
        crossbuild_dir = self.cpython_dir / "cross-build" / "wasm32-wasip1"
        self.libdir = crossbuild_dir / "build" / f"lib.wasi-wasm32-{self.pymajorminor}"
