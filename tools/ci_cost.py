"""Summarize actual exported Actions timing, without inferring billing or cache hits."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from datetime import datetime
from pathlib import Path


def timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def measure(snapshot: dict) -> dict:
    run, jobs = snapshot["run"], snapshot["jobs"]
    if (
        run["status"] != "completed"
        or not re.fullmatch("[0-9a-f]{40}", run["head_sha"])
        or not jobs
        or len({job["id"] for job in jobs}) != len(jobs)
        or any(job["status"] != "completed" for job in jobs)
        or ("total_jobs" in snapshot and snapshot["total_jobs"] != len(jobs))
    ):
        raise ValueError("incomplete/duplicate jobs or invalid source SHA")
    rows = []
    for job in jobs:
        if job.get("run_id", run["id"]) != run["id"]:
            raise ValueError("job belongs to a different run")
        if job["conclusion"] == "skipped":
            seconds = 0.0
        else:
            seconds = (
                timestamp(job["completed_at"]) - timestamp(job["started_at"])
            ).total_seconds()
            if seconds < 0:
                raise ValueError("negative job duration")
        rows.append(
            {
                "id": job["id"],
                "name": job["name"],
                "conclusion": job["conclusion"],
                "runner_labels": job.get("labels", []),
                "seconds": seconds,
                "cache_hit": "unrecorded",
            }
        )
    start = timestamp(run["run_started_at"])
    created = timestamp(run["created_at"])
    finish = max(timestamp(job["completed_at"]) for job in jobs)
    if start < created or finish < start:
        raise ValueError("invalid run time order")
    return {
        "run_id": run["id"],
        "run_attempt": run.get("run_attempt", 1),
        "run_number": run["run_number"],
        "workflow_id": run["workflow_id"],
        "source_sha": run["head_sha"],
        "event": run["event"],
        "branch": run["head_branch"],
        "created_at": run["created_at"],
        "conclusion": run["conclusion"],
        "queue_seconds": (start - created).total_seconds(),
        "execution_seconds": (finish - start).total_seconds(),
        "job_seconds": sum(row["seconds"] for row in rows),
        "jobs": rows,
        "job_inventory_complete": snapshot.get("total_jobs") == len(jobs),
    }


def summarize(records: list[dict]) -> dict:
    keys = {(row["run_id"], row["run_attempt"]) for row in records}
    if len(keys) != len(records):
        raise ValueError("duplicate Actions run attempt")
    workflow_ids = {row["workflow_id"] for row in records}
    numbers = sorted(row["run_number"] for row in records)
    consecutive = (
        len(workflow_ids) == 1
        and len(numbers) == len(set(numbers))
        and all(b == a + 1 for a, b in zip(numbers, numbers[1:]))
        and all(row["job_inventory_complete"] for row in records)
    )
    result = {
        "runs": len(records),
        "consecutive_complete_workflow_runs": consecutive,
        "twenty_run_sample_complete": consecutive and len(records) >= 20,
        "billing_cost": "unrecorded",
        "cache_hit_rate": "unrecorded",
        "limitations": "Durations are observed job occupancy, not billed minutes. Execution includes dependency waits. Run-number continuity covers one workflow, not all repository activity. No before/after saving claim or five-minute gate.",
    }
    for key in ("queue_seconds", "execution_seconds", "job_seconds"):
        values = sorted(row[key] for row in records)
        result[key] = {
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "empirical_p95": values[math.ceil(0.95 * len(values)) - 1]
            if len(values) >= 20
            else None,
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        action="append",
        required=True,
        help="exported JSON with run, jobs and optional total_jobs",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = [measure(json.loads(path.read_text())) for path in args.input]
    data = {
        "schema_version": 1,
        "input_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in args.input
        },
        "records": records,
        "summary": summarize(records),
    }
    if args.output.exists():
        parser.error("preserve previous cost samples; use a new output path")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(data["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
