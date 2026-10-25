"""Verify work accounting and the boundary between samples and cost conclusions."""

from __future__ import annotations

import unittest

from tools.ci_cost import measure
from tools.ci_cost import summarize as cost_summary
from tools.performance import summarize, validate_work, variant_order


class PerformanceTests(unittest.TestCase):
    def test_thread_models_cannot_be_merged_or_miscounted(self):
        rows = [
            {
                "case": case,
                "threads": threads,
                "work_model": model,
                "units": 1001
                * (64 if case.endswith("_64") else 1)
                * (threads if model == "fixed_per_thread" else 1),
                "elapsed_ns": 1234,
            }
            for case in ("threaded_call_attach_detach", "threaded_deferred_drop_64")
            for threads in (1, 2, 4, 8)
            for model in ("fixed_per_thread", "fixed_total")
        ]
        validate_work(rows, 1001, True)
        rows[-1]["units"] += 1
        with self.assertRaisesRegex(ValueError, "accounting"):
            validate_work(rows, 1001, True)
        samples = [
            {
                "python_mode": "gil",
                "variant": variant,
                "case": "threaded_call_attach_detach",
                "threads": 4,
                "work_model": model,
                "elapsed_ns": duration,
                "units": 10,
            }
            for variant in ("baseline", "candidate")
            for model in ("fixed_total", "fixed_per_thread")
            for duration in (100, 110, 120)
        ]
        result = summarize(samples)
        self.assertEqual(len(result), 4)
        self.assertTrue(all(row["samples"] == 3 for row in result))

    def test_abba_balances_order_and_noise_remains_visible(self):
        self.assertEqual(
            [variant_order(i)[0] for i in range(4)],
            ["baseline", "candidate", "candidate", "baseline"],
        )
        rows = [
            {
                "python_mode": "gil",
                "variant": "baseline",
                "case": "call",
                "threads": 1,
                "elapsed_ns": value,
                "units": 1,
            }
            for value in (1, 10, 100)
        ]
        self.assertTrue(summarize(rows)[0]["noisy"])


class CostTests(unittest.TestCase):
    def snapshot(self):
        return {
            "run": {
                "id": 1,
                "status": "completed",
                "head_sha": "a" * 40,
                "run_number": 10,
                "workflow_id": 22,
                "event": "pull_request",
                "head_branch": "test",
                "conclusion": "failure",
                "created_at": "2026-10-25T12:00:00Z",
                "run_started_at": "2026-10-25T12:00:05Z",
            },
            "total_jobs": 1,
            "jobs": [
                {
                    "id": 2,
                    "run_id": 1,
                    "status": "completed",
                    "name": "test",
                    "conclusion": "failure",
                    "started_at": "2026-10-25T12:00:10Z",
                    "completed_at": "2026-10-25T12:01:10Z",
                }
            ],
        }

    def test_failed_run_cost_counts_but_missing_inventory_never_closes_sample(self):
        row = measure(self.snapshot())
        self.assertEqual(
            (row["queue_seconds"], row["execution_seconds"], row["job_seconds"]),
            (5, 65, 60),
        )
        result = cost_summary([row])
        self.assertFalse(result["twenty_run_sample_complete"])
        self.assertIsNone(result["job_seconds"]["empirical_p95"])
        self.assertEqual(result["cache_hit_rate"], "unrecorded")
        incomplete = self.snapshot()
        incomplete["total_jobs"] = 2
        with self.assertRaisesRegex(ValueError, "incomplete"):
            measure(incomplete)

    def test_consecutive_runs_require_full_inventory_and_distinct_attempts(self):
        original = measure(self.snapshot())
        rows = [original | {"run_id": i, "run_number": i + 10} for i in range(20)]
        self.assertTrue(cost_summary(rows)["twenty_run_sample_complete"])
        rows[-1]["run_number"] += 1
        self.assertFalse(cost_summary(rows)["twenty_run_sample_complete"])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            cost_summary([original, original])


if __name__ == "__main__":
    unittest.main()
