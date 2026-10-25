"""Exercise actual Nox command generation without invoking Cargo or Nox."""

from __future__ import annotations

import ast
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.engineering.environment import isolated_source, probe_python
from tools.engineering.matrix import RustTestOptions, feature_sets, select_test_features

ROOT = Path(__file__).resolve().parents[2]


class Session:
    def __init__(self, *arguments):
        self.posargs = list(arguments)
        self.commands = []
        self.env = {}

    def error(self, message):
        raise ValueError(message)

    def run(self, *command, **kwargs):
        self.commands.append((command, kwargs))


def load_sessions():
    # Load the production function bodies, stripping decorators. Matrix tests
    # must not require Cargo metadata, a Rust toolchain, or a Nox installation.
    names = {"test_rust", "_run_cargo_test", "coverage"}
    tree = ast.parse((ROOT / "noxfile.py").read_text())
    nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    for node in nodes:
        node.decorator_list.clear()
    namespace = {
        "RustTestOptions": RustTestOptions,
        "select_test_features": select_test_features,
        "sys": types.SimpleNamespace(
            implementation=types.SimpleNamespace(name="cpython"),
            version_info=(3, 14, 0),
            platform="linux",
        ),
        "os": os,
        "Path": Path,
        "is_rust_nightly": lambda: False,
        "_get_feature_sets": lambda: feature_sets(
            version=(3, 14), free_threaded=False, cargo_target="", nightly=False
        ),
        "_run": lambda session, *args, **kwargs: session.run(*args, **kwargs),
        "_run_cargo": lambda session, *args, **kwargs: session.run(
            "cargo", *args, **kwargs
        ),
    }
    # Only function bodies from this repository's own noxfile are executed.
    exec(  # noqa: S102
        compile(
            ast.Module(body=nodes, type_ignores=[]), str(ROOT / "noxfile.py"), "exec"
        ),
        namespace,
    )
    return namespace


class RustCommandTests(unittest.TestCase):
    def commands(self, *arguments):
        session = Session(*arguments)
        load_sessions()["test_rust"](session)
        return [command for command, _ in session.commands]

    def test_complete_and_quick_commands(self):
        complete = self.commands()
        quick = self.commands("skip-full")
        self.assertEqual(len(complete), 11)
        self.assertEqual(len(quick), 6)
        self.assertEqual(sum(any("full" in arg for arg in c) for c in complete), 3)
        self.assertFalse(any("full" in arg for c in quick for arg in c))
        self.assertTrue(all("--locked" in c for c in complete))

    def test_unknown_fails_before_running_cargo(self):
        session = Session("skip-ful")
        with self.assertRaisesRegex(ValueError, "unknown Rust test argument"):
            load_sessions()["test_rust"](session)
        self.assertEqual(session.commands, [])

    def test_scopes(self):
        self.assertEqual(len(self.commands("scope=components")), 4)
        core = self.commands("scope=core")
        self.assertEqual(len(core), 2)
        self.assertIn("--features=macros", core[1])
        abi = self.commands("scope=abi")
        self.assertEqual(len(abi), 4)
        self.assertTrue(all(any("abi3" in a for a in c) for c in abi))
        ui = self.commands("scope=ui")
        self.assertEqual(len(ui), 2)
        self.assertTrue(all("test_compile_error" in c for c in ui))

    def test_execution_flags_survive(self):
        commands = self.commands("skip-full", "release", "careful")
        tests = [c for c in commands if "test" in c]
        self.assertEqual(len(tests), 6)
        self.assertTrue(all(c[:3] == ("cargo", "careful", "test") for c in tests))
        self.assertTrue(all("--release" in c for c in tests))

    def test_coverage_separates_and_restores_report_arguments(self):
        namespace = load_sessions()
        session = Session("--lcov")
        seen = []
        namespace["_get_coverage_env"] = dict
        namespace["test"] = lambda session: seen.append(session.posargs[:])
        namespace["generate_coverage_report"] = lambda session: seen.append(
            session.posargs[:]
        )
        namespace["coverage"](session)
        self.assertEqual(seen, [[], ["--lcov"]])
        namespace["test"] = lambda _: (_ for _ in ()).throw(RuntimeError())
        with self.assertRaises(RuntimeError):
            namespace["coverage"](session)
        self.assertEqual(session.posargs, ["--lcov"])


class MatrixTests(unittest.TestCase):
    def test_interpreter_platform_and_feature_combinations(self):
        for minor in range(9, 17):
            for gil_disabled in (False, True):
                for target in ("", "wasm32-wasip1", "x86_64-pc-windows-msvc"):
                    for nightly in (False, True):
                        with self.subTest(
                            minor=minor,
                            gil=gil_disabled,
                            target=target,
                            nightly=nightly,
                        ):
                            full = feature_sets(
                                version=(3, minor),
                                free_threaded=gil_disabled,
                                cargo_target=target,
                                nightly=nightly,
                                required=("rust_decimal",),
                            )
                            quick = select_test_features(
                                full, RustTestOptions(skip_full=True)
                            )
                            self.assertEqual(len(full), 2 * len(quick))
                            for features in full:
                                self.assertIn("rust_decimal", features)
                                parts = features.split(",")
                                self.assertEqual(
                                    "abi3" in parts, features.startswith("abi3,")
                                )
                                if gil_disabled:
                                    self.assertNotIn("abi3", parts)
                                if minor < 15:
                                    self.assertNotIn("abi3t", parts)
                                if "full" in parts:
                                    self.assertEqual("nightly" in parts, nightly)
                                    self.assertEqual(
                                        "multiple-pymethods" in parts,
                                        target != "wasm32-wasip1",
                                    )
                            self.assertTrue(all("full" not in f for f in quick))

    def test_invalid_combinations(self):
        for arguments in (
            ("scope=nope",),
            ("scope=abi", "scope=ui"),
            ("scope=ui", "skip-full"),
        ):
            with self.assertRaises(ValueError):
                RustTestOptions.parse(arguments)


class EnvironmentTests(unittest.TestCase):
    def test_probe_reports_actual_executable(self):
        info = probe_python(sys.executable)
        self.assertEqual(info["version"], list(sys.version_info[:3]))
        self.assertEqual(info["implementation"], sys.implementation.name)
        self.assertEqual(Path(info["executable"]), Path(sys.executable))

    def test_snapshot_preserves_pending_edits_and_isolates_locks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Cargo.lock").write_text("original")
            (root / "pending.py").write_text("uncommitted")
            (root / "gone.py").touch()
            (root / "gone.py").unlink()
            with patch(
                "tools.engineering.environment.subprocess.check_output",
                return_value=b"Cargo.lock\0pending.py\0gone.py\0",
            ):
                checkout = isolated_source(root, root / "target")
            self.assertEqual((checkout / "pending.py").read_text(), "uncommitted")
            (checkout / "Cargo.lock").write_text("msrv")
            self.assertEqual((root / "Cargo.lock").read_text(), "original")


if __name__ == "__main__":
    unittest.main()
