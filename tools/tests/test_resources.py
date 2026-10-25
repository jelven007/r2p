"""Exercise resource lifetime and retained-byte verification contracts."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.artifact_bundle import retrieve
from tools.engineering.environment import digest
from tools.engineering.resources import compact_msrv_snapshot, scratch_directory


class ResourceTests(unittest.TestCase):
    def test_success_cleans_scratch_but_failure_retains_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            with scratch_directory(parent, "success-") as success:
                (success / "installed-wheel").write_bytes(b"scratch bytes")
            self.assertFalse(success.exists())
            with (
                self.assertRaisesRegex(RuntimeError, "install failed"),
                scratch_directory(parent, "failed-") as failure,
            ):
                (failure / "install.log").write_text("actual error")
                raise RuntimeError("install failed")
            self.assertEqual((failure / "install.log").read_text(), "actual error")
            self.assertTrue(
                json.loads((failure / "scratch-result.json").read_text())["retained"]
            )

    def test_compaction_preserves_exact_locks_and_refuses_failed_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "checkout"
            root.mkdir()
            (root / "Cargo.lock").write_text("resolved dependencies\n")
            (root / "source.rs").write_text("discardable copied source\n")
            record = {
                "result": "failed",
                "locks": {"Cargo.lock": digest(root / "Cargo.lock")},
            }
            (root / "msrv-evidence.json").write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, "failed MSRV"):
                compact_msrv_snapshot(root)
            self.assertTrue((root / "source.rs").exists())
            record["result"] = "success"
            (root / "msrv-evidence.json").write_text(json.dumps(record))
            retained = compact_msrv_snapshot(root)
            self.assertFalse(root.exists())
            self.assertEqual(
                digest(retained / "Cargo.lock"), record["locks"]["Cargo.lock"]
            )
            self.assertEqual(
                json.loads((retained / "msrv-evidence.json").read_text()), record
            )

    def test_retrieval_rejects_changed_bundle_before_creating_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = root / "bundle.tar.gz"
            bundle.write_bytes(b"changed bundle")
            destination = root / "restored"
            with self.assertRaisesRegex(ValueError, "digest differs"):
                retrieve(bundle, destination, "a" * 40, "b" * 64)
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
