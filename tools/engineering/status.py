"""Check explicit product and requirement states against collected evidence."""

from __future__ import annotations


def status_errors(
    rows: list[dict], records: list[dict], implementation: dict, runtime: dict
) -> list[str]:
    errors = []
    collected = {
        "NFR-002": any(
            row["id"].startswith("performance-") and row["result"] == "success"
            for row in records
        ),
        "NFR-007": any(
            row["abi"] == "restoration" and row["result"] == "success"
            for row in records
        ),
    }
    for row in rows:
        if collected.get(row["id"]) and (
            "not-collected" in row["acceptance_evidence"].split("+")
            or row["capability_status"]
            in {
                "benchmarking-configured",
                "git-recovery-defined-external-drill-pending",
            }
        ):
            errors.append(
                f"{row['id']}: collected evidence contradicts declared status"
            )
    status = implementation.get("python_runtime_status")
    if status not in {"reserved", "implemented"}:
        errors.append("runtime capability status must be explicit")
    if status == "reserved":
        classifiers = set(runtime["project"].get("classifiers", []))
        if (
            implementation.get("python_runtime_publication") != "not-enabled"
            or "Private :: Do Not Upload" not in classifiers
            or "Development Status :: 1 - Planning" not in classifiers
            or any("Beta" in value or "Production" in value for value in classifiers)
        ):
            errors.append("reserved runtime must remain private and in planning")
    return errors
