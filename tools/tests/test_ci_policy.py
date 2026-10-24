"""Change selection, matrix completeness, and executable conclusion regressions."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import unittest

from tools.ci_policy import JOBS, ROOT, check_workflow_contract, make_plan, validate
from tools.engineering.ci_matrix import build_matrices

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


if __name__ == "__main__":
    unittest.main()
