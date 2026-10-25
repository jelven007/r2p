"""Validate structured support evidence and render its current summary."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

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


def import_actions(run_id: int, gh: str) -> list[dict]:
    def api(path: str) -> dict:
        return json.loads(subprocess.check_output([gh, "api", path], text=True))

    run = api(f"repos/jelven007/r2p/actions/runs/{run_id}")
    if run["status"] != "completed":
        raise ValueError("only completed Actions runs can become support evidence")
    records = []
    page = 1
    while True:
        jobs = api(
            f"repos/jelven007/r2p/actions/runs/{run_id}/jobs?per_page=100&page={page}"
        )["jobs"]
        for job in jobs:
            match = re.fullmatch(
                r"python(\S+)-(\S+) (.+) rust-(\S+) / build", job["name"]
            )
            if not match:
                continue
            python, architecture, runner, rust = match.groups()
            result = job["conclusion"]
            records.append(
                {
                    "id": f"actions-{run_id}-{job['id']}",
                    "source_sha": run["head_sha"],
                    "source_state": "committed",
                    "target": f"{runner}/{architecture}",
                    "rust": f"{rust} (patch version in logs)",
                    "python": f"{python} (patch version in logs)",
                    "gil": "disabled" if python.endswith("t") else "enabled",
                    "abi": "Nox interpreter-specific combinations",
                    "features": [
                        "default",
                        "no-default",
                        "full",
                        "ABI according to Nox",
                    ],
                    "commands": [
                        "nox -s docs",
                        "nox -s test-rust",
                        "nox -s test-py",
                        "ffi-check conditional; inspect step results",
                    ],
                    "result": result,
                    "level": "run",
                    "skip_reason": "job did not run; inspect Actions event/dependency conditions"
                    if result == "skipped"
                    else "",
                    "limitations": "per-test skips remain in logs; nightly UI uses ignore; no registry support inference",
                    "log": job["html_url"],
                    "verified_at": job["completed_at"],
                }
            )
        if len(jobs) < 100:
            break
        page += 1
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
        "gil": "disabled" if python["free_threaded"] else "enabled",
        "abi": "native/selected ABI combinations",
        "features": features,
        "commands": [
            "python tools/dev.py --target-python <recorded-target> -- "
            + " ".join(snapshot["nox_arguments"])
        ],
        "result": "success" if snapshot["exit_code"] == 0 else "failure",
        "level": level,
        "limitations": "local worktree changes are not contained in source_sha; scope and skips in report",
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
                "id": f"consumer-{snapshot['source']['revision'][:8]}-{snapshot['verified_at'][:10]}-{mode}",
                "source_sha": snapshot["source"]["revision"],
                "source_state": "committed",
                "target": snapshot["platform"],
                "rust": snapshot["rust"].splitlines()[0],
                "python": snapshot["python"].split(" (", 1)[0],
                "gil": "disabled"
                if re.search(r"Tag: cp\d+t-", snapshot["wheel_metadata"]["native"])
                else "enabled",
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
        if (
            not snapshot.get("finished_at")
            or len(snapshot["samples"]) != 102
            or len(snapshot["builds"]) != 27
        ):
            raise ValueError(
                "performance evidence requires completed independent samples"
            )
        records.append(
            {
                "id": f"performance-{mode}-20261025",
                "source_sha": snapshot["candidate"],
                "baseline_sha": snapshot["baseline"],
                "source_state": "committed",
                "target": snapshot["os"] + " / " + snapshot["cpu"],
                "rust": snapshot["rust"].splitlines()[0],
                "python": "CPython " + ".".join(map(str, snapshot[mode]["version"])),
                "gil": "enabled" if mode == "gil" else "disabled",
                "abi": "native",
                "features": ["minimal", "full-sdk build profile", "1/2/4/8 threads"],
                "commands": [
                    "python -m tools.performance --baseline <recorded SHA> --candidate <recorded SHA> --python-mode "
                    + mode
                ],
                "result": "success",
                "level": "run",
                "limitations": "102 walltime and 27 build samples per mode; three processes cannot establish P95 or a 5% gate; noisy free-threaded scaling is not an optimization claim",
                "log": "docs/testing/reports/performance-baseline-2026-10-25.md",
                "verified_at": snapshot["finished_at"],
                "lock_sha256": snapshot["locks"],
                "harness_sha256": snapshot["harness_sha256"],
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
            "import-local",
            "import-consumer",
            "import-performance",
        ),
    )
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--gh", default="gh")
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--id")
    parser.add_argument("--level", choices=("compiled", "run", "check"), default="run")
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
            "import-local",
            "import-consumer",
            "import-performance",
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
