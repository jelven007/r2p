"""Report SDK test imports missing from the actual Windows Python DLL."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pefile


def inspect(binary_path: Path, libraries: dict[str, Path]) -> list[dict]:
    binary = pefile.PE(str(binary_path))
    failures = []
    for dependency in getattr(binary, "DIRECTORY_ENTRY_IMPORT", []):
        name = dependency.dll.decode().lower()
        if not name.startswith(("python", "libpypy")):
            continue
        library_path = libraries.get(name)
        if library_path is None:
            failures.append({"library": name, "missing_library": True})
            continue
        library = pefile.PE(str(library_path))
        exports = {
            symbol.name
            for symbol in library.DIRECTORY_ENTRY_EXPORT.symbols
            if symbol.name
        }
        missing = [
            symbol.name.decode()
            for symbol in dependency.imports
            if symbol.name and symbol.name not in exports
        ]
        if missing:
            failures.append(
                {
                    "library": str(library_path),
                    "missing_symbols": missing,
                }
            )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    libraries = {
        path.name.lower(): path
        for base in (Path(sys.base_prefix), Path(sys.executable).parent)
        for path in base.glob("*.dll")
    }
    records = []
    for binary in sorted(args.directory.glob("*.exe")):
        failures = inspect(binary, libraries)
        if failures:
            records.append({"binary": str(binary), "failures": failures})
    print(
        json.dumps(
            {
                "python": sys.executable,
                "version": sys.version,
                "libraries": {key: str(value) for key, value in libraries.items()},
                "records": records,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
