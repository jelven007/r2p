"""Require a completed full CI run at the exact candidate source revision."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path

import tomllib

from tools.candidate_artifacts import ROOT, verify_manifest
from tools.ci_policy import CORE_JOBS, FULL_JOBS
from tools.engineering.ci_matrix import build_matrices

REPOSITORY = "jelven007/r2p"
CLIPPY_TARGETS = (
    "aarch64-apple-darwin",
    "x86_64-unknown-linux-gnu",
    "aarch64-unknown-linux-gnu",
    "powerpc64le-unknown-linux-gnu",
    "s390x-unknown-linux-gnu",
    "wasm32-wasip1",
    "x86_64-pc-windows-msvc",
    "i686-pc-windows-msvc",
    "aarch64-pc-windows-msvc",
)


def required_jobs(msrv: str) -> set[str]:
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
    ) - {
        "clippy",
        "no_std",
        "pytests-type-checking",
        "build-full",
        "test-cross-compilation",
        "check-feature-powerset",
    }
    names |= {f"clippy/{target}/stable" for target in CLIPPY_TARGETS}
    names |= {f"no_std ({session})" for session in ("test-py", "test-rust", "clippy")}
    names |= {f"pytests-type-checking ({checker})" for checker in ("mypy", "pyrefly")}
    names |= {f"check-feature-powerset {rust}" for rust in ("stable", msrv)}
    names |= {
        "test-introspection (macos-latest, arm64, aarch64-apple-darwin)",
        "test-introspection (ubuntu-latest, x64, x86_64-unknown-linux-gnu)",
        "test-introspection (windows-latest, x64, x86_64-pc-windows-msvc)",
        "test-introspection (windows-latest, x86, i686-pc-windows-msvc)",
    }
    names |= {
        f"test-cross-compilation {runner} -> {target}"
        for runner, target in (
            ("ubuntu-latest", "x86_64-unknown-linux-gnu"),
            ("ubuntu-latest", "aarch64-unknown-linux-gnu"),
            ("ubuntu-latest", "x86_64-pc-windows-gnu"),
            ("windows-latest", "aarch64-pc-windows-msvc"),
        )
    }
    for cell in build_matrices(msrv)["full"]["include"]:
        platform = cell["platform"]
        # Nightly/beta are forward-looking; their job must complete but their
        # tolerated failures do not define the supported stable/MSRV set.
        if cell["rust"] in {"nightly", "beta"}:
            continue
        names.add(
            f"python{cell['python-version']}-{platform['python-architecture']} "
            f"{platform['os']} rust-{cell['rust']} / build"
        )
    return names


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
    counts = Counter(job["name"] for job in jobs)
    for name in sorted(required_jobs(msrv)):
        matches = [job for job in jobs if job["name"] == name]
        if (
            counts[name] != 1
            or matches[0].get("status") != "completed"
            or matches[0].get("conclusion") != "success"
        ):
            errors.append(
                f"required full-matrix job missing, duplicated or unsuccessful: {name}"
            )
    for job in jobs:
        prospective = (
            job["name"] == "check-nightly/x86_64-unknown-linux-gnu/nightly"
            or job["name"] == "clippy/x86_64-unknown-linux-gnu/beta"
            or job["name"]
            in {
                "python3.14-x64 ubuntu-latest rust-nightly / build",
                "python3.14-x64 ubuntu-latest rust-beta / build",
            }
        )
        allowed = {"success", "failure"} if prospective else {"success", "skipped"}
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
        "schema_version": 1,
        "source_sha": args.sha,
        "version": version,
        "run_id": args.run_id,
        "run_url": run["html_url"],
        "required_jobs": sorted(
            required_jobs(package["workspace"]["package"]["rust-version"])
        ),
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
