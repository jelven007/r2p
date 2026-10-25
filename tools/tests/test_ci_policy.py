"""Change selection, matrix completeness, and executable conclusion regressions."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.ci_policy import JOBS, ROOT, check_workflow_contract, make_plan, validate
from tools.cli_wheel_acceptance import matches_platform
from tools.engineering import ci_matrix
from tools.engineering.ci_matrix import build_matrices, cli_matrix, release_cells
from tools.release_gate import job_policy, required_jobs, validate_run

# The 24 prerequisites used by the previous 50-case gate regression.
LEGACY_JOBS = {
    "resolve",
    "zizmor",
    "fmt",
    "semver-checks",
    "check-msrv",
    "clippy",
    "check-nightly",
    "build-pr",
    "build-full",
    "valgrind",
    "careful",
    "docsrs",
    "emscripten",
    "wasm32-wasip1",
    "no_std",
    "test-debug",
    "test-debug-min-version",
    "test-version-limits",
    "check-feature-powerset",
    "test-cross-compilation",
    "test-cross-compilation-windows",
    "test-introspection",
    "test-introspection-pr",
    "pytests-type-checking",
}


def successful_needs(plan: dict) -> dict:
    needs = {
        name: {"result": "skipped" if rule["status"] == "not-applicable" else "success"}
        for name, rule in plan["jobs"].items()
    }
    needs["resolve"]["outputs"] = {"plan": json.dumps(plan)}
    return needs


class SelectionTests(unittest.TestCase):
    def test_engineering_only_is_lightweight(self):
        for path in (
            "docs/governance/document-management.md",
            "docs/operations/support-policy.md",
            "docs/testing/reports/new.md",
            "newsfragments/123.fixed.md",
            ".github/ISSUE_TEMPLATE/bug_report.yml",
        ):
            with self.subTest(path=path):
                plan = make_plan([path], "pull_request")
                self.assertEqual(
                    {
                        name
                        for name, rule in plan["jobs"].items()
                        if rule["status"] == "required"
                    },
                    {"resolve", "engineering"},
                )
                self.assertFalse(plan["site"])
                self.assertFalse(plan["benchmarks"])

    def test_compiled_docs_cannot_skip_doctests(self):
        for path in (
            "README.md",
            "Contributing.md",
            "docs/guide/src/class.md",
            "docs/sdk/README.md",
        ):
            with self.subTest(path=path):
                plan = make_plan([path], "pull_request")
                for name in ("sdk-docs", "consumer-smoke", "fmt"):
                    self.assertEqual(plan["jobs"][name]["status"], "required")
                self.assertEqual(plan["jobs"]["build-pr"]["status"], "not-applicable")
                self.assertTrue(plan["site"])

    def test_core_and_tooling_changes_preserve_coverage(self):
        for path in (
            "crates/r2p-macros-backend/src/pyclass.rs",
            "crates/r2p-ffi/src/object.rs",
            "Cargo.lock",
            "noxfile.py",
            ".github/workflows/ci.yml",
            "unknown-file",
        ):
            with self.subTest(path=path):
                plan = make_plan([path], "pull_request")
                for name in (
                    "build-pr",
                    "check-msrv",
                    "clippy",
                    "consumer-smoke",
                    "sdk-docs",
                ):
                    self.assertEqual(plan["jobs"][name]["status"], "required")

    def test_ffi_and_introspection_impact(self):
        for path in ("crates/r2p-ffi/src/object.rs", "Cargo.lock", "noxfile.py"):
            self.assertTrue(make_plan([path], "pull_request")["ffi"])
        plan = make_plan(
            ["crates/r2p-introspection/src/introspection.rs"], "pull_request"
        )
        self.assertEqual(plan["jobs"]["test-introspection"]["status"], "required")
        self.assertEqual(
            plan["jobs"]["test-introspection-pr"]["status"], "not-applicable"
        )
        plan = make_plan(["docs/README.md"], "pull_request", ["CI-test-introspection"])
        self.assertEqual(plan["jobs"]["fmt"]["status"], "required")
        self.assertEqual(plan["jobs"]["test-introspection"]["status"], "required")

    def test_events_labels_and_unknown_diffs_recompute(self):
        for event in ("schedule", "workflow_dispatch", "merge_group"):
            plan = make_plan(["docs/README.md"], event)
            self.assertTrue(plan["full"])
            self.assertEqual(
                plan["jobs"]["check-feature-powerset"]["status"], "required"
            )
        for paths, labels in (
            ([], []),
            (["docs/README.md"], ["CI-build-full"]),
            ([".github/workflows/build.yml"], []),
            (["tools/engineering/matrix.py"], []),
        ):
            self.assertTrue(make_plan(paths, "pull_request", labels)["full"])
        self.assertFalse(make_plan(["docs/README.md"], "pull_request")["full"])
        self.assertTrue(make_plan(["src/instance.rs"], "push")["benchmarks"])
        self.assertFalse(make_plan(["docs/README.md"], "push")["benchmarks"])

    def test_workflow_uses_the_policy_for_all_checks(self):
        self.assertEqual(check_workflow_contract(), [])
        text = (ROOT / ".github/workflows/ci.yml").read_text()
        self.assertIn("cargo +stable test --doc --features full", text)
        self.assertNotIn("paths-ignore", text)
        self.assertIn("schedule:", text)
        self.assertIn("labeled, unlabeled", text)
        build = (ROOT / ".github/workflows/build.yml").read_text()
        self.assertIn("set-msrv-package-versions -- docs test-rust test-py", build)
        self.assertNotIn("dorny/paths-filter", build)

    def test_matrix_preserves_supported_combinations(self):
        matrices = build_matrices("1.85")
        self.assertEqual(len(matrices["pr"]["include"]), 10)
        self.assertEqual(len(matrices["full"]["include"]), 45)
        cells = {
            (
                row["rust"],
                row["python-version"],
                row["platform"]["os"],
                row["platform"]["python-architecture"],
            )
            for row in matrices["full"]["include"]
        }
        self.assertEqual(len(cells), 45)
        for python in (
            "3.9",
            "3.10",
            "3.11",
            "3.12",
            "3.13",
            "3.14",
            "3.14t",
            "3.15",
            "3.15t",
            "pypy3.11",
            "pypy3.12",
            "graalpy25.4",
        ):
            for runner, architecture in (
                ("ubuntu-latest", "x64"),
                ("windows-latest", "x64"),
                ("macos-latest", "arm64"),
            ):
                if python == "3.9" and architecture == "arm64":
                    continue
                self.assertIn(("stable", python, runner, architecture), cells)
        self.assertIn(("1.85", "3.14", "ubuntu-latest", "x64"), cells)
        self.assertIn(("stable", "3.9", "macos-15-intel", "x64"), cells)
        for runner in ("ubuntu-24.04-arm", "windows-11-arm"):
            self.assertIn(("stable", "3.14t", runner, "arm64"), cells)


class ConclusionTests(unittest.TestCase):
    def run_cli(self, needs: dict) -> int:
        process = subprocess.run(
            [sys.executable, "-m", "tools.ci_policy", "conclude"],
            cwd=ROOT,
            env=os.environ | {"CI_NEEDS": json.dumps(needs)},
            capture_output=True,
            text=True,
            check=False,
        )
        return process.returncode

    def test_original_50_execution_scenarios(self):
        # The two successes now contain only explicitly inapplicable skips.
        core = make_plan(["src/instance.rs"], "pull_request")
        full = make_plan(["src/instance.rs"], "pull_request", ["CI-build-full"])
        self.assertEqual(self.run_cli(successful_needs(core)), 0)
        self.assertEqual(self.run_cli(successful_needs(full)), 0)
        self.assertEqual(len(LEGACY_JOBS), 24)
        for name in LEGACY_JOBS:
            for status in ("failure", "cancelled"):
                needs = successful_needs(full)
                needs[name]["result"] = status
                with self.subTest(name=name, status=status):
                    self.assertNotEqual(self.run_cli(needs), 0)

    def test_every_required_or_optional_skip_blocks(self):
        for paths, event in ((["src/lib.rs"], "pull_request"), ([], "schedule")):
            plan = make_plan(paths, event)
            for name, rule in plan["jobs"].items():
                if rule["status"] == "not-applicable":
                    continue
                needs = successful_needs(plan)
                needs[name]["result"] = "skipped"
                with self.subTest(event=event, name=name):
                    self.assertTrue(validate(plan, needs))

    def test_missing_jobs_and_corrupted_plans_block(self):
        plan = make_plan(["src/lib.rs"], "pull_request")
        for name in JOBS:
            needs = successful_needs(plan)
            del needs[name]
            self.assertTrue(validate(plan, needs))
        for mutate in ("matrix", "status", "reason", "labels", "inventory"):
            altered = copy.deepcopy(plan)
            if mutate == "matrix":
                altered["matrices"]["pr"]["include"].pop()
            elif mutate == "status":
                altered["jobs"]["build-pr"]["status"] = "not-applicable"
            elif mutate == "reason":
                altered["jobs"]["build-pr"]["reason"] = ""
            elif mutate == "labels":
                altered["labels"] = ["CI-build-full"]
            else:
                del altered["jobs"]["build-pr"]
            with self.subTest(mutate=mutate):
                self.assertTrue(validate(altered, successful_needs(altered)))
        self.assertNotEqual(self.run_cli({}), 0)


class SharedMatrixTests(unittest.TestCase):
    def test_platform_runner_change_reaches_execution_and_gate_with_stable_id(self):
        before = build_matrices("1.85")
        changed = ci_matrix.PLATFORMS | {
            "linux-x64": ("ubuntu-26.04", "x64", "x86_64-unknown-linux-gnu")
        }
        with patch.object(ci_matrix, "PLATFORMS", changed):
            after = build_matrices("1.85")
            for group in ("pr", "full", "cross", "introspection"):
                self.assertEqual(
                    {row["id"] for row in before[group]["include"]},
                    {row["id"] for row in after[group]["include"]},
                )
            self.assertIn(
                "python3.14-x64 ubuntu-26.04 rust-stable / build",
                required_jobs("1.85"),
            )
            self.assertNotIn(
                "python3.14-x64 ubuntu-latest rust-stable / build",
                required_jobs("1.85"),
            )
            self.assertEqual(after["cli"]["include"][0]["runner"], "ubuntu-26.04")

    def test_add_remove_clippy_target_and_cli_platform_changes_both_sets(self):
        target = "riscv64gc-unknown-linux-gnu"
        for targets in (
            ci_matrix.CLIPPY_TARGETS + (target,),
            ci_matrix.CLIPPY_TARGETS[1:],
        ):
            with patch.object(ci_matrix, "CLIPPY_TARGETS", targets):
                self.assertEqual(
                    {
                        row["target"]
                        for row in build_matrices("1.85")["clippy"]["include"]
                        if row["rust"] == "stable"
                    },
                    set(targets),
                )
                self.assertEqual(
                    {
                        name
                        for name in required_jobs("1.85")
                        if name.startswith("clippy/")
                    },
                    {f"clippy/{item}/stable" for item in targets},
                )
        original = ci_matrix.CLI_PLATFORMS
        with patch.dict(
            original,
            {"linux-riscv64": ("linux-arm", "riscv64", ("manylinux",), "riscv64")},
        ):
            self.assertIn(
                "linux-riscv64", {row["platform-id"] for row in cli_matrix()["include"]}
            )
            self.assertTrue(
                matches_platform("py3-none-manylinux_2_17_riscv64", "linux-riscv64")
            )
        saved = original.pop("windows-x86")
        try:
            self.assertNotIn(
                "windows-x86", {row["platform-id"] for row in cli_matrix()["include"]}
            )
            self.assertFalse(matches_platform("py3-none-win32", "windows-x86"))
        finally:
            original["windows-x86"] = saved

    def test_msrv_changes_required_names_without_changing_cell_ids(self):
        before, after = build_matrices("1.85"), build_matrices("1.90")
        for group in ("full", "powerset"):
            self.assertEqual(
                {row["id"] for row in before[group]["include"]},
                {row["id"] for row in after[group]["include"]},
            )
        self.assertIn("check-feature-powerset 1.90", required_jobs("1.90"))
        self.assertNotIn("check-feature-powerset 1.85", required_jobs("1.90"))
        for value in ("stable", "nightly", "", "1.85\n"):
            with self.assertRaises(ValueError):
                build_matrices(value)

    def test_prospective_policy_controls_execution_and_gate_and_never_skips(self):
        run = {
            "head_sha": "1" * 40,
            "name": "CI",
            "path": ".github/workflows/ci.yml",
            "repository": {"full_name": "jelven007/r2p"},
            "status": "completed",
            "conclusion": "success",
        }
        with patch.object(ci_matrix, "PROSPECTIVE_TOOLCHAINS", {"nightly"}):
            rules = job_policy("1.85")
            self.assertFalse(
                build_matrices("1.85")["clippy"]["include"][-1]["allow-failure"]
            )
            self.assertIn("clippy/x86_64-unknown-linux-gnu/beta", required_jobs("1.85"))
            jobs = [
                {"name": name, "status": "completed", "conclusion": "success"}
                for name in rules
            ]
            future = next(job for job in jobs if "rust-nightly / build" in job["name"])
            future["conclusion"] = "failure"
            self.assertEqual(validate_run(run, jobs, "1" * 40, "1.85"), [])
            for result in ("skipped", "cancelled", "timed_out"):
                future["conclusion"] = result
                self.assertTrue(validate_run(run, jobs, "1" * 40, "1.85"))
            future["conclusion"] = "success"
            beta = next(job for job in jobs if job["name"].endswith("/beta"))
            beta["conclusion"] = "failure"
            self.assertTrue(validate_run(run, jobs, "1" * 40, "1.85"))
        self.assertEqual(len(release_cells("1.85")), 71)

    def test_independent_workflow_matrix_or_tolerance_is_detected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workflow = root / ".github/workflows"
            workflow.mkdir(parents=True)
            originals = {
                name: (ROOT / ".github/workflows" / name).read_text()
                for name in ("ci.yml", "build.yml", "python-wheel.yml")
            }
            for name, old, new in (
                ("ci.yml", "matrices.clippy", "matrices.other"),
                ("build.yml", "inputs.allow-failure", "inputs.rust != 'stable'"),
                ("python-wheel.yml", "needs.admission.outputs.cli-matrix", "'{}'"),
            ):
                for filename, text in originals.items():
                    (workflow / filename).write_text(text)
                (workflow / name).write_text(originals[name].replace(old, new))
                with patch("tools.ci_policy.ROOT", root):
                    self.assertTrue(check_workflow_contract())


if __name__ == "__main__":
    unittest.main()
