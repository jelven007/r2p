"""Clean successful scratch work while retaining failed runs and acceptance bytes."""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from tools.engineering.environment import digest


@contextmanager
def scratch_directory(parent: Path, prefix: str) -> Iterator[Path]:
    parent.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix=prefix, dir=parent))
    try:
        yield directory
    except BaseException:
        (directory / "scratch-result.json").write_text(
            json.dumps({"result": "failed", "retained": True}) + "\n"
        )
        raise
    else:
        shutil.rmtree(directory)


def compact_msrv_snapshot(checkout: Path) -> Path:
    """Persist evidence and exact resolved locks before removing a successful copy."""
    evidence_file = checkout / "msrv-evidence.json"
    evidence = json.loads(evidence_file.read_text())
    if evidence["result"] != "success":
        raise ValueError("failed MSRV snapshots must remain intact")
    destination = checkout.with_name(checkout.name + "-evidence")
    destination.mkdir()
    for relative, checksum in evidence["locks"].items():
        source = checkout / relative
        if not source.resolve().is_relative_to(checkout.resolve()):
            raise ValueError("MSRV lock path escapes snapshot")
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if digest(target) != checksum:
            raise ValueError("saved MSRV lock digest differs")
    shutil.copy2(evidence_file, destination / evidence_file.name)
    if digest(destination / evidence_file.name) != digest(evidence_file):
        raise ValueError("saved MSRV evidence digest differs")
    shutil.rmtree(checkout)
    return destination
