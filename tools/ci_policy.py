"""One change-selection and conclusion contract for CI, benchmarks, and site builds."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

import tomllib

from tools.engineering.ci_matrix import MATRIX_JOBS, build_matrices

ROOT = Path(__file__).resolve().parent.parent
CORE_JOBS = {
    "check-msrv",
    "clippy",
    "no_std",
    "pytests-type-checking",
}
FULL_JOBS = {
    "build-full",
    "valgrind",
    "careful",
    "docsrs",
    "emscripten",
    "wasm32-wasip1",
    "test-debug",
    "test-debug-min-version",
    "test-version-limits",
    "check-feature-powerset",
    "test-cross-compilation",
    "test-cross-compilation-windows",
}
JOBS = (
    {
        "resolve",
        "engineering",
        "fmt",
        "zizmor",
        "semver-checks",
        "check-nightly",
        "build-pr",
        "test-introspection",
        "test-introspection-pr",
        "sdk-docs",
        "consumer-smoke",
        "candidate-acceptance",
    }
    | CORE_JOBS
    | FULL_JOBS
)
STATES = {"required", "optional", "not-applicable"}
ENGINEERING_PREFIXES = (
    "docs/governance/",
    "docs/operations/",
    "docs/runbooks/",
    "docs/requirements/",
    "docs/testing/",
    "docs/releases/",
    "docs/development/",
    "docs/architecture/",
    "docs/reference/",
    ".github/ISSUE_TEMPLATE/",
    "newsfragments/",
    "r2p-newsfragments/",
)
ENGINEERING_FILES = {
    "Architecture.md",
    "Releasing.md",
    "SECURITY.md",
    ".github/CODEOWNERS",
    ".github/pull_request_template.md",
    "docs/README.md",
    "R2P_CHANGELOG.md",
}
SDK_DOC_FILES = {"README.md", "Contributing.md"}


def classify(paths: list[str]) -> set[str]:
    categories = set()
    for path in paths:
        if path in SDK_DOC_FILES or path.startswith(("docs/guide/", "docs/sdk/")):
            categories.add("sdk-docs")
        elif path in ENGINEERING_FILES or path.startswith(ENGINEERING_PREFIXES):
            categories.add("engineering")
        elif path.startswith((".github/", "tools/")) or path in {
            "noxfile.py",
            "pyproject.toml",
            "uv.lock",
            ".python-version",
        }:
            categories.add("tooling")
        else:
            # Unknown files receive the complete core checks, including deletions.
            categories.add("core")
        if path.startswith(("src/", "crates/", "benchmarks/")) or path in {
            "Cargo.toml",
            "Cargo.lock",
            "noxfile.py",
            "tools/ci_policy.py",
            ".github/workflows/benches.yml",
        }:
            categories.add("performance")
    return categories


def make_plan(paths: list[str], event: str, labels: list[str] = ()) -> dict:
    categories = classify(paths)
    # Non-PR/non-push events and an unknown/empty diff fail closed to the full set.
    full = (
        event not in {"pull_request", "push"}
        or not paths
        or "CI-build-full" in labels
        or any(
            path
            in {
                ".github/workflows/build.yml",
                "tools/engineering/matrix.py",
                "tools/engineering/ci_matrix.py",
            }
            for path in paths
        )
    )
    core = (
        full
        or bool(categories & {"core", "tooling"})
        or "CI-test-introspection" in labels
    )
    docs = core or "sdk-docs" in categories
    introspection = (
        full
        or "CI-test-introspection" in labels
        or any(path.startswith("crates/r2p-introspection/") for path in paths)
    )
    jobs = {
        name: {"status": "not-applicable", "reason": "outside this change/event scope"}
        for name in sorted(JOBS)
    }

    def require(names: set[str], reason: str) -> None:
        for name in names:
            jobs[name] = {"status": "required", "reason": reason}

    require(
        {"resolve", "engineering"},
        "always validate policy, paths, and engineering content",
    )
    if docs:
        require(
            {"fmt", "sdk-docs", "consumer-smoke"},
            "compiled documentation or SDK/tooling impact",
        )
    if core:
        require(CORE_JOBS, "SDK/tooling compatibility checks")
        require({"zizmor"}, "SDK/tooling workflow validation")
        require(
            {"candidate-acceptance"},
            "isolated registry and candidate artifact acceptance",
        )
        jobs["check-nightly"] = {
            "status": "optional",
            "reason": "nightly toolchain is forward-looking, outside stable support",
        }
        if event == "pull_request":
            require(
                {"semver-checks"}, "same-package public API comparison against PR base"
            )
        require(
            {"build-full" if full else "build-pr"},
            "full matrix requested" if full else "core PR matrix",
        )
        require(
            {"test-introspection" if introspection else "test-introspection-pr"},
            "introspection impact/full matrix"
            if introspection
            else "representative introspection regression",
        )
    if introspection:
        require({"test-introspection"}, "explicit introspection impact or label")
    if full:
        require(
            FULL_JOBS,
            "full matrix: event, label, unknown diff, or matrix definition change",
        )
    return {
        "schema_version": 1,
        "event": event,
        "paths": sorted(set(paths)),
        "labels": sorted(set(labels)),
        "categories": sorted(categories),
        "full": full,
        "matrices": build_matrices(
            tomllib.loads((ROOT / "Cargo.toml").read_text())["workspace"]["package"][
                "rust-version"
            ]
        ),
        "benchmarks": full or "performance" in categories,
        "site": docs,
        "ffi": full
        or any(
            path.startswith(
                ("crates/r2p-ffi/", "crates/r2p-build-config/", "tools/ffi-check/")
            )
            or path
            in {
                "Cargo.toml",
                "Cargo.lock",
                "noxfile.py",
                ".github/workflows/ci.yml",
                ".github/workflows/build.yml",
            }
            for path in paths
        ),
        "jobs": jobs,
    }


def validate(plan: dict, needs: dict) -> list[str]:
    errors = []
    if plan.get("schema_version") != 1 or set(plan.get("jobs", {})) != JOBS:
        return ["invalid plan schema or missing/unknown jobs"]
    # Recompute the expected set so a corrupted/stale plan cannot make checks optional.
    expected = make_plan(plan["paths"], plan["event"], plan["labels"])
    if plan != expected:
        errors.append("plan differs from the event/change selection contract")
    if set(needs) != JOBS:
        errors.append(f"missing/unknown aggregate jobs: {sorted(set(needs) ^ JOBS)}")
    for name, rule in plan["jobs"].items():
        state = rule.get("status")
        if state not in STATES or not rule.get("reason"):
            errors.append(f"{name}: invalid status/reason")
            continue
        result = needs.get(name, {}).get("result")
        allowed = {
            "required": {"success"},
            # Forward-looking jobs handle tolerated failures at job/cell level.
            # They must still complete; never hide a raw failure or cancellation.
            "optional": {"success"},
            "not-applicable": {"skipped"},
        }[state]
        if result not in allowed:
            errors.append(f"{name}: {state}, received {result}; {rule['reason']}")
    return errors


def changed_paths(event: str, payload: dict) -> list[str]:
    if event == "pull_request":
        base = payload["pull_request"]["base"]["sha"]
        head = payload["pull_request"]["head"]["sha"]
        commits = f"{base}...{head}"
    elif event == "push" and payload.get("before", "").strip("0"):
        commits = f"{payload['before']}..{payload['after']}"
    else:
        return []
    # Shallow/missing commits are an error, never an empty successful selection.
    output = subprocess.check_output(
        ["git", "diff", "--name-only", "--no-renames", "-z", commits],
        cwd=ROOT,
    ).decode()
    return list(filter(None, output.split("\0")))


def check_workflow_contract() -> list[str]:
    text = (ROOT / ".github/workflows/ci.yml").read_text().split("\njobs:\n", 1)[1]
    jobs = dict(re.findall(r"(?ms)^  ([\w-]+):\n(.*?)(?=^  [\w-]+:\n|\Z)", text))
    errors = []
    if set(jobs) != JOBS | {"conclusion"}:
        errors.append("ci.yml job inventory differs from CI policy")
    needs = re.search(r"(?ms)^    needs:\n(.*?)(?=^    \S)", jobs["conclusion"])
    if (
        not needs
        or set(re.findall(r"^      - ([\w-]+)$", needs[1], re.MULTILINE)) != JOBS
    ):
        errors.append("conclusion must aggregate every policy job exactly once")
    for name in JOBS - {"resolve"}:
        condition = f"if: ${{{{ fromJSON(needs.resolve.outputs.plan).jobs['{name}'].status != 'not-applicable' }}}}"
        if condition not in jobs.get(name, ""):
            errors.append(f"{name}: condition must use the shared CI plan")
        dependency = re.search(
            r"^    needs: \[(.*)\]$", jobs.get(name, ""), re.MULTILINE
        )
        if not dependency or "resolve" not in dependency[1].split(", "):
            errors.append(f"{name}: must depend on resolve")
    for name, matrix in MATRIX_JOBS.items():
        if (
            f"matrix: ${{{{ fromJSON(needs.resolve.outputs.plan).matrices.{matrix} }}}}"
            not in jobs[name]
        ):
            errors.append(f"{name}: matrix must come from the verified selection")
        if "name: ${{ matrix.name }}" not in jobs[name]:
            errors.append(f"{name}: job name must come from the shared cell")
        if name in {"build-pr", "build-full"}:
            for field in ("allow-failure", "cell-id", "job-name"):
                value = {"cell-id": "id", "job-name": "name"}.get(field, field)
                if f"{field}: ${{{{ matrix.{value} }}}}" not in jobs[name]:
                    errors.append(f"{name}: missing shared cell input {field}")
        elif "runs-on: ${{ matrix.runner }}" not in jobs[name]:
            errors.append(f"{name}: runner must come from the shared cell")
    build = (ROOT / ".github/workflows/build.yml").read_text()
    if "continue-on-error: ${{ inputs.allow-failure }}" not in build:
        errors.append("build.yml: tolerated failure must use the shared policy")
    for name in ("clippy", "check-nightly"):
        if "continue-on-error: ${{ matrix.allow-failure }}" not in jobs[name]:
            errors.append(f"{name}: tolerated failure must use the shared policy")
    wheel = (ROOT / ".github/workflows/python-wheel.yml").read_text()
    if (
        "python -m tools.engineering.ci_matrix --github-output" not in wheel
        or "matrix: ${{ fromJSON(needs.admission.outputs.cli-matrix) }}" not in wheel
        or "cli-matrix: ${{ steps.matrix.outputs.cli-matrix }}" not in wheel
    ):
        errors.append("python-wheel.yml: CLI execution must use the shared matrix")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("select", "conclude", "check"))
    args = parser.parse_args()
    if args.command == "select":
        event = os.environ["GITHUB_EVENT_NAME"]
        payload = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
        plan = make_plan(
            changed_paths(event, payload),
            event,
            [
                label["name"]
                for label in payload.get("pull_request", {}).get("labels", [])
            ],
        )
        serialized = json.dumps(plan, separators=(",", ":"))
        with Path(os.environ["GITHUB_OUTPUT"]).open("a") as file:
            print(f"plan={serialized}", file=file)
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as file:
            print("```json\n" + json.dumps(plan, indent=2) + "\n```", file=file)
        print(serialized)
        return 0
    if args.command == "conclude":
        needs = json.loads(os.environ["CI_NEEDS"])
        raw = needs.get("resolve", {}).get("outputs", {}).get("plan")
        if not raw:
            print("resolve did not supply a selection plan")
            return 1
        errors = validate(json.loads(raw), needs)
    else:
        errors = check_workflow_contract()
    for error in errors:
        print(error)
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
