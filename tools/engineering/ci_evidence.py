"""Write observed interpreter/toolchain metadata before CI executes SDK steps."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from tools.engineering.environment import environment_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    snapshot = environment_snapshot(root, sys.executable, sys.executable, [])
    snapshot["job_name"] = os.environ.get("CI_JOB_NAME", "")
    snapshot["run_id"] = os.environ.get("GITHUB_RUN_ID", "")
    snapshot["recorded_at"] = datetime.now(timezone.utc).isoformat()
    snapshot["scope"] = (
        "interpreter startup; SDK steps and module imports recorded separately"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
