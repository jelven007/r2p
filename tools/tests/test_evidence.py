"""Evidence provenance, result levels, and generated-summary contract."""

from __future__ import annotations

import copy
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

import tomllib

from tools.engineering.environment import probe_python
from tools.engineering.status import status_errors
from tools.evidence import (
    DATA,
    check,
    gil_state,
    import_actions_data,
    import_local,
    import_performance,
    import_runtime_replay,
    render,
    validate,
)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(DATA.read_text())

    def test_current_records_and_summary_match(self):
        self.assertEqual(check(self.data), [])
        self.assertIn("worktree-changes", render(self.data))
        self.assertIn("compiled", render(self.data))

    def test_duplicate_and_missing_sources_block(self):
        duplicate = copy.deepcopy(self.data)
        duplicate["records"].append(duplicate["records"][0])
        self.assertTrue(validate(duplicate))
        for key in ("source_sha", "source_state", "commands", "log", "verified_at"):
            invalid = copy.deepcopy(self.data)
            del invalid["records"][0][key]
            with self.subTest(key=key):
                self.assertTrue(validate(invalid))

    def test_unperformed_results_need_reason(self):
        for result in ("skipped", "not-run"):
            data = copy.deepcopy(self.data)
            row = data["records"][0]
            row["result"] = result
            row["skip_reason"] = ""
            self.assertTrue(validate(data))
            row["skip_reason"] = "outside selected scope"
            self.assertEqual(validate(data), [])

    def test_configuration_is_not_behavior_success(self):
        data = copy.deepcopy(self.data)
        data["records"][0]["level"] = "configured"
        self.assertTrue(validate(data))
        data["records"][0]["result"] = "not-run"
        data["records"][0]["skip_reason"] = "configured but not executed"
        self.assertEqual(validate(data), [])

    def test_changed_result_requires_summary_update(self):
        data = copy.deepcopy(self.data)
        data["records"][0]["result"] = "failure"
        self.assertEqual(validate(data), [])
        self.assertTrue(check(data))

    def test_gil_is_observed_separately_from_the_build(self):
        for build in (True, False):
            for state, expected in (
                (True, "enabled"),
                (False, "disabled"),
                (None, "unrecorded"),
            ):
                with self.subTest(build=build, state=state):
                    self.assertEqual(
                        gil_state({"free_threaded": build, "gil_enabled": state}),
                        expected,
                    )
            self.assertEqual(gil_state({"free_threaded": build}), "unrecorded")
        self.assertEqual(
            gil_state({"gil_enabled": False, "gil_after_imports": True}), "enabled"
        )
        probe = probe_python(sys.executable, ("json", "r2p_missing_module_for_probe"))
        self.assertEqual(
            [row["result"] for row in probe["modules"]], ["success", "failure"]
        )
        self.assertIn("gil_after", probe["modules"][1])

    def test_actions_install_failure_and_absent_environment_are_not_runtime_support(
        self,
    ):
        row = self.data["records"][0]
        run = {
            "id": 123,
            "head_sha": row["source_sha"],
            "status": "completed",
            "conclusion": "failure",
            "name": "CI",
            "html_url": "https://example.com/run",
            "updated_at": row["verified_at"],
        }
        job = {
            "id": 456,
            "name": "python3.14t-x64 ubuntu-latest rust-stable / build",
            "conclusion": "failure",
            "html_url": "https://example.com/job",
            "completed_at": row["verified_at"],
            "steps": [
                {"name": "Set up Python 3.14t", "conclusion": "failure"},
                {"name": "Run Rust tests", "conclusion": "skipped"},
            ],
        }
        records = import_actions_data(run, [job])
        self.assertEqual(
            (records[0]["level"], records[0]["gil"], records[0]["python"]),
            ("configured", "unrecorded", "unrecorded"),
        )
        self.assertEqual(validate({"schema_version": 1, "records": records}), [])
        job["steps"] = [{"name": "Build docs", "conclusion": "success"}]
        self.assertEqual(import_actions_data(run, [job])[0]["level"], "compiled")
        job["steps"].append({"name": "Run Rust tests", "conclusion": "failure"})
        self.assertEqual(import_actions_data(run, [job])[0]["level"], "compiled")
        job["steps"] = [
            {"name": "Test python examples and tests", "conclusion": "failure"}
        ]
        self.assertEqual(import_actions_data(run, [job])[0]["level"], "check")
        job["steps"][0]["conclusion"] = "success"
        self.assertEqual(import_actions_data(run, [job])[0]["level"], "run")
        environments = {
            job["name"]: {
                "source_sha": run["head_sha"],
                "dirty": False,
                "target_python": {
                    "implementation": "cpython",
                    "version": [3, 14, 9],
                    "free_threaded": True,
                    "gil_enabled": True,
                },
            }
        }
        record = import_actions_data(run, [job], environments)[0]
        self.assertEqual(
            (record["python"], record["gil"]), ("cpython 3.14.9", "enabled")
        )
        job["steps"] = [{"name": "Run Rust tests", "conclusion": "success"}]
        environments[job["name"]]["target_python"]["implementation"] = "graalpy"
        self.assertEqual(
            import_actions_data(run, [job], environments)[0]["level"], "compiled"
        )
        environments[job["name"]]["source_sha"] = "0" * 40
        with self.assertRaises(ValueError):
            import_actions_data(run, [job], environments)

    def test_failed_local_bundle_cannot_claim_sdk_runtime_execution(self):
        snapshot = {
            "source_sha": "1" * 40,
            "dirty": False,
            "target_python": {
                "implementation": "cpython",
                "version": [3, 14, 9],
                "free_threaded": True,
            },
            "rust": ["rustc 1.99.1", "host: aarch64-apple-darwin"],
            "nox_arguments": ["-s", "test-rust"],
            "locks": {},
            "exit_code": 1,
            "finished_at": self.data["records"][0]["verified_at"],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            path.write_text(json.dumps(snapshot))
            record = import_local(
                path, "failed-bundle", "run", ["default"], "https://example.com/report"
            )
        self.assertEqual(
            (record["result"], record["level"], record["gil"]),
            ("failure", "configured", "unrecorded"),
        )

    def test_collected_evidence_and_reserved_runtime_cannot_drift(self):
        root = DATA.parents[2]
        with (root / "docs/requirements/traceability.csv").open() as file:
            rows = list(csv.DictReader(file))
        implementation = tomllib.loads((root / "product.toml").read_text())[
            "implementation"
        ]
        runtime = tomllib.loads(
            (root / "python/r2p-runtime/pyproject.toml").read_text()
        )
        self.assertEqual(
            status_errors(rows, self.data["records"], implementation, runtime), []
        )
        for identifier in ("NFR-002", "NFR-007"):
            changed = copy.deepcopy(rows)
            next(row for row in changed if row["id"] == identifier)[
                "acceptance_evidence"
            ] = "not-collected"
            self.assertTrue(
                status_errors(changed, self.data["records"], implementation, runtime)
            )
        changed_runtime = copy.deepcopy(runtime)
        changed_runtime["project"]["classifiers"] = ["Development Status :: 4 - Beta"]
        self.assertTrue(
            status_errors(rows, self.data["records"], implementation, changed_runtime)
        )

    def test_calibration_requires_every_thread_model_and_observed_gil(self):
        # Synthetic records validate rejection rules; never imported as evidence.
        snapshot = {
            "schema_version": 2,
            "finished_at": "2026-10-25T12:00:00Z",
            "runtime_samples": 3,
            "threaded_only": True,
            "build_samples": 0,
            "builds": [],
            "iterations": 1001,
            "locks": {"gil-baseline": "same", "gil-candidate": "same"},
            "processes": [{"environment": {"gil_enabled": True}} for _ in range(6)],
            "samples": [
                {
                    "python_mode": "gil",
                    "variant": variant,
                    "repeat": repeat,
                    "case": case,
                    "threads": threads,
                    "work_model": model,
                    "units": 1001
                    * (64 if case.endswith("_64") else 1)
                    * (threads if model == "fixed_per_thread" else 1),
                    "elapsed_ns": 100,
                }
                for variant in ("baseline", "candidate")
                for repeat in range(3)
                for case in ("threaded_call_attach_detach", "threaded_deferred_drop_64")
                for threads in (1, 2, 4, 8)
                for model in ("fixed_total", "fixed_per_thread")
            ],
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "calibration.json"
            snapshot["processes"][0]["environment"]["gil_enabled"] = False
            path.write_text(json.dumps({"datasets": [snapshot]}))
            with self.assertRaisesRegex(ValueError, "calibration"):
                import_performance(path)
            snapshot["processes"][0]["environment"]["gil_enabled"] = True
            snapshot["samples"][-1]["units"] += 1
            path.write_text(json.dumps({"datasets": [snapshot]}))
            with self.assertRaisesRegex(ValueError, "accounting"):
                import_performance(path)

    def test_runtime_replay_cannot_hide_missing_negative_or_failed_repair(self):
        source = DATA.parent / "data/upstream-runtime-2026-10-25.json"
        observed = json.loads(source.read_text())
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "replay.json"
            for variant in ("missing-negative", "failed-repair", "incomplete-gc"):
                changed = copy.deepcopy(observed)
                if variant == "missing-negative":
                    changed["replay"]["results"][0]["exit_code"] = 0
                elif variant == "failed-repair":
                    changed["replay"]["results"][-1]["exit_code"] = 101
                else:
                    changed["full_gc"]["passed"] = 25
                path.write_text(json.dumps(changed))
                with (
                    self.subTest(variant=variant),
                    self.assertRaisesRegex(ValueError, "runtime replay"),
                ):
                    import_runtime_replay(path)


if __name__ == "__main__":
    unittest.main()
