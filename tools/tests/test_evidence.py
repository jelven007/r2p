"""Evidence provenance, result levels, and generated-summary contract."""

from __future__ import annotations

import copy
import json
import unittest

from tools.evidence import DATA, check, render, validate


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


if __name__ == "__main__":
    unittest.main()
