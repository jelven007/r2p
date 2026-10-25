"""Run the publishing CLI against real accepted crate bytes on loopback HTTP."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from tools.candidate_artifacts import ROOT, SDK, digest, verify_manifest
from tools.tests.test_registry_upload import RegistryUploadTests


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    manifest = verify_manifest(manifest_path, args.sha)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    rows = manifest["variants"]["candidate"]["crates"]
    data = {
        "schema_version": 1,
        "source_sha": args.sha,
        "manifest_sha256": digest(manifest_path),
        "tool_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "scope": "loopback HTTP fixture with actual accepted crate bytes; no external CI gate or release",
        "cases": [],
        "result": "failure",
    }
    for scenario in (
        "delayed",
        "partial",
        "accepted-error",
        "bad-index",
        "bad-download",
    ):
        fixture = RegistryUploadTests()
        fixture.setUp()
        fixture.rows = rows
        fixture.bytes = {
            row["name"]: (manifest_path.parent / row["path"]).read_bytes()
            for row in rows
        }
        fixture.journal = output / f"{scenario}-journal.json"
        if scenario == "partial":
            fixture.fail_before = SDK[1]
        if scenario == "accepted-error":
            fixture.fail_after = SDK[1]
        fixture.bad_index = scenario == "bad-index"
        fixture.bad_download = scenario == "bad-download"
        command = [
            sys.executable,
            "-m",
            "tools.publish_candidate",
            "--manifest",
            str(manifest_path),
            "--sha",
            args.sha,
            "--local-registry",
            f"http://127.0.0.1:{fixture.server.server_port}",
            "--journal",
            str(fixture.journal),
            "--wait-timeout",
            "0.4",
            "--poll-interval",
            "0.01",
        ]
        phases = {
            "delayed": (
                ("dry-run", False, False, 0),
                ("upload", True, False, 0),
                ("resume", True, False, 0),
            ),
            "partial": (
                ("error", True, False, 1),
                ("wait-only", True, False, 1),
                ("retry", True, True, 0),
            ),
            "accepted-error": (("error", True, False, 1), ("resume", True, False, 0)),
            "bad-index": (("stop", True, False, 1),),
            "bad-download": (("stop", True, False, 1),),
        }[scenario]
        try:
            for phase, execute, retry, expected in phases:
                flags = (["--execute"] if execute else []) + (
                    ["--retry-unindexed"] if retry else []
                )
                process = subprocess.run(
                    command + flags,
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                log = output / f"{scenario}-{phase}.log"
                log.write_text(process.stdout + process.stderr)
                if bool(process.returncode) != bool(expected):
                    raise ValueError(
                        f"unexpected publishing outcome: {scenario}/{phase}: {log}"
                    )
                journal = (
                    json.loads(fixture.journal.read_text())
                    if fixture.journal.exists()
                    else None
                )
                if not execute and (journal or fixture.uploads):
                    raise ValueError("dry-run sent a request or changed the journal")
                data["cases"].append(
                    {
                        "scenario": scenario,
                        "phase": phase,
                        "exit_code": process.returncode,
                        "expected_rejection": bool(expected),
                        "uploads": fixture.uploads[:],
                        "journal_result": journal["result"] if journal else None,
                        "download_hashes": {
                            name: entry.get("download_sha256")
                            for name, entry in journal["packages"].items()
                        }
                        if journal
                        else {},
                        "log": log.name,
                        "result": "success",
                    }
                )
                (output / "evidence.json").write_text(json.dumps(data, indent=2) + "\n")
            expected_uploads = {
                "delayed": list(SDK),
                "partial": [SDK[0], SDK[1], *SDK[1:]],
                "accepted-error": list(SDK),
                "bad-index": [SDK[0]],
                "bad-download": [SDK[0]],
            }[scenario]
            if fixture.uploads != expected_uploads:
                raise ValueError(f"duplicate/continued upload differs: {scenario}")
        finally:
            fixture.doCleanups()
    data["result"] = "success"
    (output / "evidence.json").write_text(json.dumps(data, indent=2) + "\n")
    print(
        f"Loopback accepted-byte publishing/recovery passed: {output / 'evidence.json'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
