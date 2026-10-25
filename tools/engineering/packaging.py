"""Native library transformations used by introspection acceptance."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path


def library_variants(
    run: Callable, lib_file: Path, work_dir: Path, platform: str
) -> list[Path]:
    variants = [lib_file]

    def variant(name: str, *command: str) -> None:
        output = work_dir / f"{name}{lib_file.suffix}"
        shutil.copy(lib_file, output)
        run(*command, str(output), external=True)
        variants.append(output)

    if platform == "linux":
        variant("stripped", "strip", "--strip-all")
    elif platform == "darwin":
        variant("stripped", "strip", "-x")
        fat_file = work_dir / f"fat{lib_file.suffix}"
        run("lipo", "-create", str(lib_file), "-output", str(fat_file), external=True)
        variants.append(fat_file)
    return variants
