"""Require a completed full CI run at the exact candidate source revision."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

import tomllib

from tools.candidate_artifacts import ROOT, verify_manifest
from tools.ci_policy import CORE_JOBS, FULL_JOBS
from tools.engineering.ci_matrix import MATRIX_JOBS, release_cells

REPOSITORY = "jelven007/r2p"


def job_policy(msrv: str) -> dict[str, dict]:
    names = (
        CORE_JOBS
        | FULL_JOBS
        | {
            "resolve",
            "engineering",
            "zizmor",
            "fmt",
            "sdk-docs",
            "consumer-smoke",
            "candidate-acceptance",
            "conclusion",
        }
    ) - MATRIX_JOBS.keys()
    return {
        name: {
            "id": name,
            "support": "supported",
            "allowed-results": ["success"],
        }
        for name in names
    } | release_cells(msrv)


def required_jobs(msrv: str) -> set[str]:
    """Supported jobs require success; prospective cells still must complete."""
    return {
        name
        for name, rule in job_policy(msrv).items()
        if rule["support"] == "supported"
    }


def validate_run(run: dict, jobs: list[dict], sha: str, msrv: str) -> list[str]:
    errors = []
    if (
        not re.fullmatch(r"[0-9a-f]{40}", sha)
        or run.get("head_sha") != sha
        or run.get("name") != "CI"
        or run.get("path") != ".github/workflows/ci.yml"
        or run.get("repository", {}).get("full_name") != REPOSITORY
        or run.get("status") != "completed"
        or run.get("conclusion") != "success"
    ):
        errors.append("CI identity/source/completion/conclusion does not match")
    policies = job_policy(msrv)
    for name, rule in sorted(policies.items()):
        matches = [job for job in jobs if job["name"] == name]
        if (
            len(matches) != 1
            or matches[0].get("status") != "completed"
            or matches[0].get("conclusion") not in rule["allowed-results"]
        ):
            errors.append(
                f"required full-matrix job missing, duplicated or unsuccessful: {name}"
            )
    for job in jobs:
        allowed = policies.get(job["name"], {}).get(
            "allowed-results", ["success", "skipped"]
        )
        if job.get("status") != "completed" or job.get("conclusion") not in allowed:
            errors.append(f"CI job incomplete or unsuccessful: {job['name']}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--gh", default="gh")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.sha):
        parser.error("--sha must be a full immutable Git SHA")
    if args.run_id <= 0:
        parser.error("--run-id must be positive")
    actual_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    package = tomllib.loads((ROOT / "Cargo.toml").read_text())
    version = args.version.removeprefix("v")
    if actual_sha != args.sha or package["package"]["version"] != version:
        parser.error("checked-out source or version differs from the candidate")
    reference = os.environ.get("GITHUB_REF", "")
    if reference.startswith("refs/tags/") and reference != f"refs/tags/v{version}":
        parser.error("release tag differs from the candidate SDK version")

    def api(path: str) -> dict:
        return json.loads(subprocess.check_output([args.gh, "api", path], text=True))

    run = api(f"repos/{REPOSITORY}/actions/runs/{args.run_id}")
    jobs = []
    page = 1
    while True:
        data = api(
            f"repos/{REPOSITORY}/actions/runs/{args.run_id}/jobs?per_page=100&page={page}"
        )
        jobs.extend(data["jobs"])
        if len(data["jobs"]) < 100:
            break
        page += 1
    errors = validate_run(
        run, jobs, args.sha, package["workspace"]["package"]["rust-version"]
    )
    if args.manifest:
        verify_manifest(args.manifest, args.sha)
    evidence = {
        "schema_version": 2,
        "source_sha": args.sha,
        "version": version,
        "run_id": args.run_id,
        "run_url": run["html_url"],
        "required_jobs": sorted(
            required_jobs(package["workspace"]["package"]["rust-version"])
        ),
        "job_policy": job_policy(package["workspace"]["package"]["rust-version"]),
        "jobs": [
            {key: job[key] for key in ("name", "status", "conclusion", "html_url")}
            for job in jobs
        ],
        "result": "failure" if errors else "success",
        "errors": errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"Full CI and candidate source match: {args.sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
