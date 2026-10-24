"""Contract tests for standalone templates and consistent SDK dependency sources."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import tomllib

from tools.consumer_smoke import check_graph
from tools.new_project import (
    ROOT,
    dependency_fields,
    examples,
    generate,
    rewrite_dependencies,
    source_configuration,
)


class SourceTests(unittest.TestCase):
    def test_reject_floating_or_unverified_sources(self):
        for arguments in (
            {"mode": "git", "revision": "main"},
            {"mode": "git", "checkout": ROOT},
            {"mode": "path"},
            {"mode": "path", "checkout": ROOT, "revision": "f" * 40},
            {"mode": "registry", "version": "0.30.0"},
        ):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                source_configuration(**arguments)

    def test_local_source_uses_same_checkout(self):
        source = source_configuration("path", checkout=ROOT)
        self.assertEqual(dependency_fields("r2p", source), {"path": ROOT.as_posix()})
        self.assertEqual(
            dependency_fields("r2p-ffi", source),
            {"path": (ROOT / "crates/r2p-ffi").as_posix()},
        )

    def test_preserves_per_section_features(self):
        content = """\
[dependencies]
r2p = { version = "0.30", features = ["macros"], default-features = false }
[dev-dependencies]
r2p = { version = "0.30", features = ["full"] }
"""
        source = source_configuration("git")
        result = tomllib.loads(rewrite_dependencies(content, source))
        self.assertEqual(result["dependencies"]["r2p"]["features"], ["macros"])
        self.assertFalse(result["dependencies"]["r2p"]["default-features"])
        self.assertEqual(result["dev-dependencies"]["r2p"]["features"], ["full"])

    def test_all_generated_templates_use_same_git_source(self):
        source = source_configuration("git")
        with tempfile.TemporaryDirectory() as temporary:
            for example in examples():
                with self.subTest(example=example):
                    project = generate(
                        example,
                        Path(temporary) / example,
                        name="consumer",
                        authors='Example "Author"',
                        source=source,
                    )
                    root = tomllib.loads((project / "Cargo.toml").read_text())
                    self.assertIn("workspace", root)
                    self.assertFalse((project / ".template").exists())
                    self.assertTrue((project / "r2p-source.json").is_file())
                    self.assertEqual(
                        (project / "LICENSE-MIT").read_bytes(),
                        (ROOT / "LICENSE-MIT").read_bytes(),
                    )
                    count = 0
                    for path in project.rglob("Cargo.toml"):
                        manifest = tomllib.loads(path.read_text())
                        for package, dependency in manifest.get(
                            "dependencies", {}
                        ).items():
                            if package in {"r2p", "r2p-ffi"}:
                                count += 1
                                self.assertEqual(
                                    dependency, dependency_fields(package, source)
                                )
                        if manifest["package"]["name"] == "pyo3-ffi":
                            self.assertFalse(manifest["package"]["publish"])
                            self.assertNotIn("workspace", manifest)
                            self.assertEqual(
                                manifest["package"]["version"], source["version"]
                            )
                    self.assertGreater(count, 0)
                    with self.assertRaisesRegex(ValueError, "never overwritten"):
                        generate(
                            example, project, name="consumer", authors="", source=source
                        )

    def test_graph_rejects_duplicate_ffi_and_mixed_source(self):
        source = source_configuration("git")
        package = {
            "name": "r2p-ffi",
            "version": source["version"],
            "source": f"git+{source['repository']}?rev={source['revision']}#{source['revision']}",
            "id": "ffi",
        }
        self.assertEqual(len(check_graph({"packages": [package]}, source)), 1)
        for packages in (
            [],
            [package, package],
            [
                package
                | {"source": "registry+https://github.com/rust-lang/crates.io-index"}
            ],
            [package | {"version": "0.29.0"}],
        ):
            with self.subTest(packages=packages), self.assertRaises(ValueError):
                check_graph({"packages": packages}, source)


if __name__ == "__main__":
    unittest.main()
