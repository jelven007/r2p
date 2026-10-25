"""Validate structured support evidence and render its current summary."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from tools.candidate_artifacts import digest, verify_manifest
from tools.performance import validate_work

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs/testing/evidence.json"
SUMMARY = ROOT / "docs/testing/evidence-summary.md"


def validate(data: dict) -> list[str]:
    errors = []
    if data.get("schema_version") != 1:
        return ["unsupported evidence schema"]
    seen = set()
    for row in data.get("records", []):
        identifier = row.get("id", "")
        if not identifier or identifier in seen:
            errors.append(f"duplicate/missing evidence ID: {identifier}")
        seen.add(identifier)
        required = (
            "source_sha",
            "source_state",
            "target",
            "rust",
            "python",
            "gil",
            "abi",
            "features",
            "commands",
            "result",
            "level",
            "limitations",
            "log",
            "verified_at",
        )
        if any(key not in row for key in required):
            errors.append(f"{identifier}: incomplete record")
            continue
        if not re.fullmatch(r"[0-9a-f]{40}", row["source_sha"]):
            errors.append(f"{identifier}: invalid source SHA")
        if row["source_state"] not in {"committed", "worktree-changes"}:
            errors.append(f"{identifier}: invalid source state")
        if row["result"] not in {
            "success",
            "failure",
            "cancelled",
            "skipped",
            "not-run",
        }:
            errors.append(f"{identifier}: invalid result")
        if row["level"] not in {"configured", "compiled", "run", "check", "delivered"}:
            errors.append(f"{identifier}: invalid evidence level")
        if row["result"] in {"skipped", "not-run"} and not row.get("skip_reason"):
            errors.append(f"{identifier}: skipped/not-run requires a reason")
        if row["level"] == "configured" and row["result"] == "success":
            errors.append(
                f"{identifier}: configuration alone is not successful evidence"
            )
        if row["gil"] not in {"enabled", "disabled", "unrecorded", "not-applicable"}:
            errors.append(f"{identifier}: invalid GIL state")
        if "python_environment" in row:
            environment = row["python_environment"]
            if not isinstance(environment, dict) or any(
                key in environment
                and environment[key] is not None
                and type(environment[key]) is not bool
                for key in ("gil_enabled", "gil_after_imports", "free_threaded")
            ):
                errors.append(f"{identifier}: invalid observed Python environment")
            elif row["gil"] != gil_state(environment):
                errors.append(
                    f"{identifier}: GIL label differs from observed environment"
                )
        for key in ("target", "rust", "python", "abi", "limitations"):
            if not isinstance(row[key], str) or not row[key]:
                errors.append(f"{identifier}: missing {key}")
        for key in ("features", "commands"):
            if not isinstance(row[key], list) or not row[key]:
                errors.append(f"{identifier}: missing {key}")
        try:
            if datetime.fromisoformat(row["verified_at"]).tzinfo is None:
                errors.append(f"{identifier}: timestamp requires timezone")
        except (TypeError, ValueError):
            errors.append(f"{identifier}: invalid verification time")
        link = row["log"]
        if not isinstance(link, str) or not link:
            errors.append(f"{identifier}: missing log/report")
        elif not urlsplit(link).scheme and not (ROOT / link).is_file():
            errors.append(f"{identifier}: missing evidence reference {link}")
    if not seen:
        errors.append("no evidence records")
    return errors


def render(data: dict) -> str:
    lines = [
        "# 当前结构化验证摘要",
        "",
        "由 `tools/evidence.py` 从 `evidence.json` 生成；手工补充上下文见[支持矩阵](support-matrix.md)。",
        "源码、工作区变更、配置、编译和行为分别登记；未记录的版本不推定。",
        "",
        "| 记录 | 源码/状态 | 目标 | Rust / Python / GIL | ABI / 特性 | 结果/等级 | 证据与限制 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in data["records"]:
        target = row["target"]
        log = row["log"]
        if not urlsplit(log).scheme:
            log = str(Path(log).relative_to("docs/testing"))
        lines.append(
            f"| {row['id']} | `{row['source_sha'][:12]}` / {row['source_state']} "
            f"| {target} | {row['rust']} / {row['python']} / {row['gil']} "
            f"| {row['abi']} / {', '.join(row['features'])} "
            f"| {row['result']} / {row['level']} "
            f"| [记录]({log})；{row['limitations']} |"
        )
    return "\n".join(lines) + "\n"


def check(data: dict | None = None) -> list[str]:
    data = data or json.loads(DATA.read_text())
    errors = validate(data)
    if not errors and (not SUMMARY.is_file() or SUMMARY.read_text() != render(data)):
        errors.append("evidence summary is stale; run python -m tools.evidence render")
    return errors


def gil_state(environment: dict, *, after_imports: bool = True) -> str:
    """A build flag or wheel tag cannot attest to the process's GIL state."""
    key = (
        "gil_after_imports"
        if after_imports and "gil_after_imports" in environment
        else "gil_enabled"
    )
    value = environment.get(key)
    if value is True:
        return "enabled"
    if value is False:
        return "disabled"
    return "unrecorded"


def python_version(environment: dict) -> str:
    if not environment.get("implementation") or not environment.get("version"):
        return "unrecorded"
    return (
        environment["implementation"] + " " + ".".join(map(str, environment["version"]))
    )


def actions_level(job: dict, environment: dict) -> str:
    """A failed test bundle may have failed during installation or compilation."""
    runtime = {
        "Test python examples and tests",
        "Run MSRV docs and tests in the isolated dependency snapshot",
    }
    succeeded = {
        step["name"]
        for step in job.get("steps", [])
        if step.get("conclusion") == "success"
    }
    if runtime & succeeded or (
        "Run Rust tests" in succeeded and environment.get("implementation") == "cpython"
    ):
        return "run"
    # Nox uses --no-run for Rust tests on PyPy/GraalPy. Unknown implementation
    # cannot upgrade that successful command from compilation to runtime.
    if {"Build docs", "Run Rust tests"} & succeeded:
        return "compiled"
    if any(
        step["name"] in runtime | {"Run Rust tests"}
        and step.get("conclusion") == "failure"
        for step in job.get("steps", [])
    ):
        return "check"
    return "configured"


def import_actions_data(
    run: dict, jobs: list[dict], environments: dict | None = None
) -> list[dict]:
    """Import a saved API export; observed metadata is optional, never inferred."""
    if run["status"] != "completed":
        raise ValueError("only completed Actions runs can become support evidence")
    run_id = run["id"]
    environments = environments or {}
    records = []
    for job in jobs:
        if not re.fullmatch(r"python\S+-\S+ .+ rust-\S+ / build", job["name"]):
            continue
        snapshot = environments.get(job["name"], {})
        if snapshot and (
            snapshot.get("source_sha") != run["head_sha"] or snapshot.get("dirty")
        ):
            raise ValueError("Actions environment source differs from the tested SHA")
        environment = snapshot.get("target_python", {})
        level = actions_level(job, environment)
        result = job["conclusion"] or "not-run"
        if level == "configured" and result == "success":
            result = "not-run"
        records.append(
            {
                "id": f"actions-observed-{run_id}-{job['id']}",
                "source_sha": run["head_sha"],
                "source_state": "committed",
                "target": snapshot.get("target", "unrecorded"),
                "rust": next(
                    (
                        line
                        for line in snapshot.get("rust", [])
                        if line.startswith("rustc ")
                    ),
                    "unrecorded",
                ),
                "python": python_version(environment),
                "gil": gil_state(environment),
                "python_environment": environment,
                "requested_configuration": job["name"],
                "abi": "inspect individual Nox combinations in logs",
                "features": ["step-specific; inspect logs"],
                "commands": [
                    step["name"]
                    for step in job.get("steps", [])
                    if step.get("conclusion") in {"success", "failure"}
                ]
                or [job["name"]],
                "steps": job.get("steps", []),
                "result": result,
                "level": level,
                "skip_reason": "no SDK execution step recorded"
                if result in {"skipped", "not-run"}
                else "",
                "limitations": "level reflects successful SDK steps; failed test bundles alone do not prove execution; environment absent from old runs is unrecorded; startup GIL does not attest to module imports; no registry support inference",
                "log": job["html_url"],
                "verified_at": job.get("completed_at") or run["updated_at"],
            }
        )
    records.append(
        {
            "id": f"ci-{run_id}",
            "source_sha": run["head_sha"],
            "source_state": "committed",
            "target": "Actions workflow aggregate",
            "rust": "job-specific",
            "python": "job-specific",
            "gil": "not-applicable",
            "abi": "job-specific",
            "features": ["selected jobs"],
            "commands": [f"Actions {run['name']} / {run_id}"],
            "result": run["conclusion"],
            "level": "check",
            "skip_reason": "workflow skipped" if run["conclusion"] == "skipped" else "",
            "limitations": "aggregate check is not a new interpreter/ABI behavior result",
            "log": run["html_url"],
            "verified_at": run["updated_at"],
        }
    )
    return records


def import_actions(run_id: int, gh: str) -> list[dict]:
    def api(path: str) -> dict:
        return json.loads(subprocess.check_output([gh, "api", path], text=True))

    run = api(f"repos/jelven007/r2p/actions/runs/{run_id}")
    jobs = []
    page = 1
    while True:
        batch = api(
            f"repos/jelven007/r2p/actions/runs/{run_id}/jobs?per_page=100&page={page}"
        )["jobs"]
        jobs.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return import_actions_data(run, jobs)


def import_local(
    path: Path, identifier: str, level: str, features: list[str], report: str
) -> dict:
    snapshot = json.loads(path.read_text())
    python = snapshot["target_python"]
    rust = next(line for line in snapshot["rust"] if line.startswith("rustc "))
    target = snapshot.get("target") or next(
        line.removeprefix("host: ")
        for line in snapshot["rust"]
        if line.startswith("host: ")
    )
    return {
        "id": identifier,
        "source_sha": snapshot["source_sha"],
        "source_state": "worktree-changes" if snapshot["dirty"] else "committed",
        "target": target,
        "rust": rust.split()[1],
        "python": python["implementation"]
        + " "
        + ".".join(map(str, python["version"])),
        "gil": gil_state(python),
        "python_environment": python,
        "abi": "native/selected ABI combinations",
        "features": features,
        "commands": [
            "python tools/dev.py --target-python <recorded-target> -- "
            + " ".join(snapshot["nox_arguments"])
        ],
        "result": "success" if snapshot["exit_code"] == 0 else "failure",
        "level": level if snapshot["exit_code"] == 0 else "configured",
        "level_basis": "successful command and explicitly selected scope"
        if snapshot["exit_code"] == 0
        else "failed bundle; SDK execution not attested",
        "limitations": "local worktree changes are not contained in source_sha; scope and skips in report; interpreter startup GIL does not attest to SDK module imports",
        "log": report,
        "verified_at": snapshot["finished_at"],
        "lock_sha256": snapshot["locks"],
    }


def import_consumer(path: Path) -> list[dict]:
    snapshot = json.loads(path.read_text())
    if snapshot["result"] != "success" or snapshot["source"]["mode"] != "git":
        raise ValueError(
            "consumer support evidence requires a successful immutable Git source"
        )
    records = []
    for mode, features in (
        ("native", ["default"]),
        ("abi3", ["abi3-py39"]),
        ("embedding", ["default"]),
    ):
        records.append(
            {
                "id": f"consumer-observed-{snapshot['source']['revision'][:8]}-{snapshot['verified_at'][:10]}-{mode}",
                "source_sha": snapshot["source"]["revision"],
                "source_state": "committed",
                "target": snapshot["platform"],
                "rust": snapshot["rust"].splitlines()[0],
                "python": snapshot["python"].split(" (", 1)[0],
                "gil": gil_state(
                    snapshot.get("behavior", {}).get(mode, {}).get("environment", {})
                ),
                "python_environment": snapshot.get("behavior", {})
                .get(mode, {})
                .get("environment", {}),
                "abi": mode,
                "features": features,
                "commands": ["python -m tools.consumer_smoke --output <new-directory>"],
                "result": "success",
                "level": "run",
                "limitations": "SDK pinned to committed SHA; consumer templates were worktree changes at generator_sha; only recorded interpreter/target ran, wheel tags do not prove others",
                "generator_sha": snapshot["generator_sha"],
                "artifacts": snapshot["artifacts"],
                "log": "docs/testing/reports/consumer-optimization-2026-10-25.md",
                "verified_at": snapshot["verified_at"],
            }
        )
    return records


def import_performance(path: Path) -> list[dict]:
    records = []
    for snapshot in json.loads(path.read_text())["datasets"]:
        mode = snapshot["samples"][0]["python_mode"]
        calibration = snapshot.get("schema_version") == 2
        if (
            not snapshot.get("finished_at")
            or not calibration
            and (len(snapshot["samples"]) != 102 or len(snapshot["builds"]) != 27)
        ):
            raise ValueError(
                "performance evidence requires completed independent samples"
            )
        if calibration:
            repeats = snapshot["runtime_samples"]
            cases = 16 if snapshot["threaded_only"] else 25
            expected_gil = mode == "gil"
            if (
                repeats < 3
                or len(snapshot["samples"]) != 2 * repeats * cases
                or len(snapshot["processes"]) != 2 * repeats
                or any(
                    process["environment"]["gil_enabled"] != expected_gil
                    for process in snapshot["processes"]
                )
                or len(snapshot["builds"]) != 9 * snapshot["build_samples"]
                or snapshot["locks"][f"{mode}-baseline"]
                != snapshot["locks"][f"{mode}-candidate"]
            ):
                raise ValueError(
                    "performance calibration source/environment/samples differ"
                )
            for variant in ("baseline", "candidate"):
                for repeat in range(repeats):
                    validate_work(
                        [
                            row
                            for row in snapshot["samples"]
                            if row["variant"] == variant and row["repeat"] == repeat
                        ],
                        snapshot["iterations"],
                        snapshot["threaded_only"],
                    )
        records.append(
            {
                "id": f"performance-{'calibration-' if calibration else ''}{mode}-20261025",
                "source_sha": snapshot["candidate"],
                "baseline_sha": snapshot["baseline"],
                "source_state": "committed",
                "target": snapshot["os"] + " / " + snapshot["cpu"],
                "rust": snapshot["rust"].splitlines()[0],
                "python": "CPython " + ".".join(map(str, snapshot[mode]["version"])),
                "gil": "enabled" if mode == "gil" else "disabled",
                "abi": "native",
                "features": [
                    "minimal",
                    "fixed_total",
                    "fixed_per_thread",
                    "1/2/4/8 threads",
                ]
                if calibration
                else ["minimal", "full-sdk build profile", "1/2/4/8 threads"],
                "commands": [
                    "python -m tools.performance --baseline <recorded SHA> --candidate <recorded SHA> --python-mode "
                    + mode
                ],
                "result": "success",
                "level": "run",
                "limitations": snapshot["limitations"]
                if calibration
                else "102 walltime and 27 build samples per mode; three processes cannot establish P95 or a 5% gate; noisy free-threaded scaling is not an optimization claim",
                "log": "docs/testing/reports/performance-calibration-2026-10-25.md"
                if calibration
                else "docs/testing/reports/performance-baseline-2026-10-25.md",
                "verified_at": snapshot["finished_at"],
                "lock_sha256": snapshot["locks"],
                "harness_sha256": snapshot["harness_sha256"],
                "data": str(path.relative_to(ROOT)),
            }
        )
    return records


def import_runtime_replay(path: Path) -> list[dict]:
    snapshot = json.loads(path.read_text())
    replay = snapshot["replay"]
    if (
        replay.get("result") != "success"
        or replay.get("upstream_sha") != "5619fedbca3ad1baca82869b57df54afd0432a0b"
        or replay.get("source_invariants") != "unchanged"
        or [
            (row["variant"], row["repeat"], row["exit_code"])
            for row in replay["results"]
        ]
        != [("broken", i, 101) for i in range(3)]
        + [("replayed", i, 0) for i in range(3)]
        or snapshot.get("full_gc", {}).get("result") != "success"
        or snapshot["full_gc"].get("passed") != 26
    ):
        raise ValueError(
            "runtime replay requires observed negative, repaired and complete GC results"
        )
    return [
        {
            "id": "upstream-runtime-gc-replay-20261025",
            "source_sha": replay["source_sha"],
            "source_state": "committed",
            "target": replay["python"]["platform"],
            "rust": snapshot["rust"].splitlines()[0],
            "python": "CPython " + ".".join(map(str, replay["python"]["version"])),
            "gil": gil_state(replay["python"]),
            "abi": "native",
            "features": ["macros", "controlled GC lookup reversal/replay"],
            "commands": [
                "python -m tools.upstream_runtime --sha <recorded SHA> --target-python <CPython 3.14> --output <new directory>"
            ],
            "result": "success",
            "level": "check",
            "limitations": replay["scope"]
            + "; #6404 finalization negative not reproduced; no complete remote matrix",
            "log": "docs/testing/reports/upstream-runtime-2026-10-25.md",
            "verified_at": snapshot["verified_at"],
            "data": str(path.relative_to(ROOT)),
            "upstream_sha": replay["upstream_sha"],
            "mapped_patch_sha256": replay["mapped_patch_sha256"],
        }
    ]


def import_candidate(path: Path) -> list[dict]:
    source_sha = json.loads(path.read_text())["source_sha"]
    snapshot = verify_manifest(path, source_sha)
    variant = snapshot["variants"]["candidate"]
    records = []
    for mode, features in (
        ("native", ["default"]),
        ("abi3", ["abi3-py39"]),
        ("embedding", ["default"]),
        ("cli", ["introspection"]),
        ("restoration", ["retained baseline", "native", "abi3", "CLI"]),
    ):
        retained = mode == "restoration"
        selected = snapshot["variants"]["baseline"] if retained else variant
        records.append(
            {
                "id": f"candidate-observed-{source_sha[:8]}-{mode}",
                "source_sha": selected["source_sha"],
                "candidate_sha": source_sha,
                "consumer_template_sha": snapshot["consumer_template_sha"],
                "tool_sha": snapshot["tool_sha"],
                "source_state": "committed",
                "target": snapshot["platform"],
                "rust": snapshot["rust"].splitlines()[0],
                "python": python_version(snapshot.get("target_python", {})),
                "gil": gil_state(
                    selected.get("behavior", {}).get(mode, {}).get("environment", {})
                ),
                "python_environment": selected.get("behavior", {})
                .get(mode, {})
                .get("environment", {}),
                "abi": mode,
                "features": features,
                "commands": [
                    "python -m tools.candidate --sha <recorded candidate SHA> --baseline-sha <recorded baseline SHA> --output <new-directory>",
                    "python -m tools.candidate_artifacts verify --manifest <retained manifest> --sha <recorded candidate SHA> --output <verification>",
                ],
                "result": "success",
                "level": "run",
                "limitations": "local sparse registry and recorded native host/interpreter only; baseline SDK uses the fixed candidate consumer template; ABI tags do not prove older interpreters; full remote CI and external publication remain separate",
                "log": "docs/testing/reports/candidate-acceptance-2026-10-25.md",
                "verified_at": snapshot["completed_at"],
                "lock_sha256": selected["locks"],
                "manifest_sha256": digest(path),
                "data": "docs/testing/data/candidate-2026-10-25.json",
                "artifacts": selected["crates"] + selected["wheels"],
            }
        )
    return records


def import_environment(path: Path) -> list[dict]:
    snapshot = json.loads(path.read_text())
    if snapshot.get("result") != "success":
        raise ValueError("environment verification is incomplete")
    base = import_local(
        path,
        "environment-r02",
        "check",
        ["environment probe", "legacy C fixture"],
        "docs/testing/reports/evidence-environment-2026-10-25.md",
    )
    records = []
    for name, environment in snapshot["cases"].items():
        records.append(
            base
            | {
                "id": f"environment-r02-{name}",
                "python": python_version(environment),
                "python_environment": environment,
                "gil": gil_state(environment),
                "commands": [
                    "python -m tools.verify_environment --gil-python <recorded> --ft-python <recorded> --legacy-python <recorded> --output <new-directory>"
                ],
                "result": "success",
                "level": "check",
                "limitations": snapshot["limitations"],
                "data": str(path.relative_to(ROOT)),
            }
        )
    records.append(
        base
        | {
            "id": "environment-r02-install-failure",
            "result": "failure",
            "level": "configured",
            "gil": "unrecorded",
            "python_environment": {},
            "python": "unrecorded",
            "commands": ["uv pip install --no-index r2p-missing-package-for-evidence"],
            "limitations": "expected real offline installation failure; no SDK execution",
            "data": str(path.relative_to(ROOT)),
        }
    )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "check",
            "render",
            "import-actions",
            "import-actions-export",
            "import-local",
            "import-consumer",
            "import-performance",
            "import-runtime-replay",
            "import-candidate",
            "import-environment",
        ),
    )
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--gh", default="gh")
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--id")
    parser.add_argument(
        "--level", choices=("compiled", "run", "check"), default="check"
    )
    parser.add_argument("--features", nargs="+", default=["Nox-selected"])
    parser.add_argument("--report")
    args = parser.parse_args()
    data = (
        json.loads(DATA.read_text())
        if DATA.is_file()
        else {"schema_version": 1, "records": []}
    )
    if args.command == "import-actions":
        if not args.run_id:
            parser.error("--run-id is required")
        additions = import_actions(args.run_id, args.gh)
    elif args.command == "import-actions-export":
        if not args.snapshot:
            parser.error("--snapshot is required")
        snapshot = json.loads(args.snapshot.read_text())
        additions = import_actions_data(
            snapshot["run"], snapshot["jobs"], snapshot.get("environments")
        )
    elif args.command == "import-local":
        if not all((args.snapshot, args.id, args.report)):
            parser.error("--snapshot, --id, and --report are required")
        additions = [
            import_local(args.snapshot, args.id, args.level, args.features, args.report)
        ]
    elif args.command == "import-consumer":
        if not args.snapshot:
            parser.error("--snapshot is required")
        additions = import_consumer(args.snapshot)
    elif args.command == "import-performance":
        if not args.snapshot:
            parser.error("--snapshot is required")
        additions = import_performance(args.snapshot.resolve())
    elif args.command == "import-candidate":
        if not args.snapshot:
            parser.error("--snapshot is required")
        additions = import_candidate(args.snapshot.resolve())
    elif args.command == "import-runtime-replay":
        if not args.snapshot:
            parser.error("--snapshot is required")
        additions = import_runtime_replay(args.snapshot.resolve())
    elif args.command == "import-environment":
        if not args.snapshot:
            parser.error("--snapshot is required")
        additions = import_environment(args.snapshot.resolve())
    else:
        additions = []
    if additions:
        existing = {row["id"]: row for row in data["records"]}
        for row in additions:
            if row["id"] in existing and existing[row["id"]] != row:
                parser.error("existing evidence is immutable; use a new record ID")
            existing[row["id"]] = row
        data["records"] = sorted(existing.values(), key=lambda row: row["id"])
    errors = validate(data)
    if (
        args.command
        in {
            "render",
            "import-actions",
            "import-actions-export",
            "import-local",
            "import-consumer",
            "import-performance",
            "import-runtime-replay",
            "import-candidate",
            "import-environment",
        }
        and not errors
    ):
        if additions:
            DATA.write_text(json.dumps(data, indent=2) + "\n")
        SUMMARY.write_text(render(data))
    else:
        errors = check(data)
    for error in errors:
        print(error)
    if not errors:
        print(f"Evidence OK: {len(data['records'])} records")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
