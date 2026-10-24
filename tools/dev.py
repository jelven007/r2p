"""Run Nox under an explicit target Python, recording both interpreter roles."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from engineering.environment import environment_snapshot

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target-python",
        default=os.environ.get("R2P_PYTHON", sys.executable),
        help="actual executable used by Nox and Rust interpreter discovery",
    )
    parser.add_argument("--evidence", type=Path, help="write environment/result JSON")
    parser.add_argument("nox_arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if sys.version_info < (3, 14):
        parser.error("run the engineering launcher with Python 3.14 or later")
    arguments = args.nox_arguments
    if arguments[:1] == ["--"]:
        arguments = arguments[1:]
    snapshot = environment_snapshot(ROOT, sys.executable, args.target_python, arguments)
    target = snapshot["target_python"]["executable"]
    env = os.environ | {"R2P_PYTHON": target, "UV_PYTHON": target, "UV_LOCKED": "1"}
    # The target interpreter must run Nox itself: sys.version_info/sysconfig in
    # existing sessions describe the tested interpreter, including free-threading.
    command = [
        "uv",
        "run",
        "--isolated",
        "--only-group",
        "nox",
        "--python",
        target,
        "python",
        "-m",
        "nox",
        "-f",
        str(ROOT / "noxfile.py"),
        *arguments,
    ]
    snapshot["command"] = command
    snapshot["started_at"] = datetime.now(timezone.utc).isoformat()
    print(json.dumps(snapshot, indent=2), flush=True)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(snapshot, indent=2) + "\n")
    result = subprocess.run(command, cwd=ROOT, env=env, check=False)
    snapshot["exit_code"] = result.returncode
    snapshot["finished_at"] = datetime.now(timezone.utc).isoformat()
    if args.evidence:
        args.evidence.write_text(json.dumps(snapshot, indent=2) + "\n")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
