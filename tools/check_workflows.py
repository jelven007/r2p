"""Run actionlint with current GitHub self-repository syntax (Python 3.11+)."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actionlint", default="actionlint")
    args = parser.parse_args()
    executable = shutil.which(args.actionlint)
    if executable is None:
        parser.error(f"actionlint executable not found: {args.actionlint}")
    executable = str(Path(executable).resolve())
    # actionlint 1.7.12 predates GitHub's $/ self-repository references. Translate
    # only uses entries in a disposable copy, preserving all other validation.
    # The source files retain $/, as required by the current zizmor audit.
    with tempfile.TemporaryDirectory(prefix="r2p-workflows-") as directory:
        temporary = Path(directory)
        (temporary / ".git").mkdir()
        shutil.copytree(ROOT / ".github", temporary / ".github")
        workflows = sorted((temporary / ".github/workflows").glob("*.yml"))
        for path in workflows:
            source = path.read_text()
            normalized = re.sub(r"(?m)^(\s*(?:-\s*)?uses:\s*)\$/", r"\1./", source)
            path.write_text(normalized)
        result = subprocess.run(
            [executable, *(str(path.relative_to(temporary)) for path in workflows)],
            cwd=temporary,
            check=False,
        )
        if result.returncode == 0:
            print(
                f"Workflow lint OK: {len(workflows)} workflows, $/ compatibility copy."
            )
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
