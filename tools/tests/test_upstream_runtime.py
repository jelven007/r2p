"""Check runtime replay provenance and preserve the inherited regression body."""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.upstream_runtime import UPSTREAM, mapped_patch, regression_program


class RuntimeReplayTests(unittest.TestCase):
    def test_unknown_source_is_rejected_before_git_or_mapping(self):
        with patch("tools.upstream_runtime.git") as git:
            with self.assertRaisesRegex(ValueError, "source/parent"):
                mapped_patch("a" * 40, ("src/internal/state.rs",))
            git.assert_not_called()

    def test_unchanged_runtime_patch_is_not_accepted_as_a_replay(self):
        with (
            patch(
                "tools.upstream_runtime.git",
                side_effect=[b"6a930e9de1fa7eb3783bfdbb4f7df6e4207cb08e\n", b""],
            ),
            self.assertRaisesRegex(ValueError, "patch is absent"),
        ):
            mapped_patch(UPSTREAM, ("src/internal/state.rs",))

    def test_regression_body_and_shutdown_gc_loop_are_retained(self):
        source = (
            Path(__file__).resolve().parents[2]
            / "tests/python/tests/test_finalization.py"
        )
        original = ast.parse(source.read_text())
        with tempfile.TemporaryDirectory() as temporary:
            program = regression_program(source, Path(temporary))
        generated = ast.parse(program)
        names = {"make_loop", "test_detach_during_finalization"}
        for name in names:
            before = next(
                node
                for node in original.body
                if isinstance(node, ast.FunctionDef) and node.name == name
            )
            after = next(
                node
                for node in generated.body
                if isinstance(node, ast.FunctionDef) and node.name == name
            )
            before.decorator_list.clear()
            self.assertEqual(ast.dump(before), ast.dump(after))
        self.assertNotIn("import pytest", program)
        self.assertIn("resource.RLIMIT_CORE", program)
        self.assertTrue(program.endswith("flush=True)\n"))


if __name__ == "__main__":
    unittest.main()
