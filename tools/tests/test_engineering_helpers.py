"""Protect documentation routes and native packaging behavior during refactors."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.engineering.documentation import build_redirects, rustdoc_arguments
from tools.engineering.packaging import library_variants
from tools.engineering.platforms import EmscriptenInfo, WasiInfo


class HelperTests(unittest.TestCase):
    def test_docs_options_preserve_caller_flags_and_internal_visibility(self):
        arguments = ["open", "internal", "nightly"]
        command, flags = rustdoc_arguments(
            arguments, "-C opt-level=1", nightly=False, internal=False
        )
        self.assertEqual(command[:2], ["+nightly", "doc"])
        self.assertIn("--open", command)
        self.assertIn("--document-private-items", command)
        self.assertNotIn("--exclude=r2p-macros", command)
        self.assertTrue(flags.endswith("-C opt-level=1"))
        self.assertIn("--html-after-content", flags)
        self.assertEqual(arguments, ["open", "internal", "nightly"])

    def test_routes_preserve_canonical_roots_and_preview_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("main", "v0.30.0", "v0.29.0"):
                (root / name).mkdir()
                (root / name / "index.html").write_text("index")
            build_redirects(
                root,
                preview=True,
                version="0.30.0",
                site_url="https://example.invalid/",
            )
            redirects = (root / "_redirects").read_text()
            headers = (root / "_headers").read_text()
            self.assertIn("/ /main/ 302", redirects)
            self.assertIn("/latest/* /v0.30.0/:splat 302", redirects)
            self.assertIn("/main/\n  Link: <https://example.invalid/main/>", headers)
            self.assertIn("/v0.29.0/*\n  X-Robots-Tag: noindex", headers)
            self.assertIn("/internal/*\n  X-Robots-Tag: noindex", headers)

    def test_platform_metadata_handles_prerelease_and_external_sdk(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            info = EmscriptenInfo(root, "3.15.0rc2 (main)")
            self.assertEqual((info.pymajorminormicro, info.pydev), ("3.15.0", "rc2"))
            wasi = WasiInfo(root, "3.14.9 (main)", {"WASI_SDK_PATH": "/opt/wasi"})
            self.assertEqual(wasi.wasi_sdk, Path("/opt/wasi"))
            self.assertTrue(str(wasi.libdir).endswith("lib.wasi-wasm32-3.14"))

    def test_native_variants_keep_original_and_use_platform_specific_tools(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = root / "module.so"
            library.write_bytes(b"original library bytes")
            for platform, tools in (
                ("linux", ["strip"]),
                ("darwin", ["strip", "lipo"]),
                ("win32", []),
            ):
                commands = []
                variants = library_variants(
                    lambda *args, commands=commands, **kwargs: commands.append(args),
                    library,
                    root,
                    platform,
                )
                self.assertEqual(variants[0], library)
                self.assertEqual([command[0] for command in commands], tools)
                self.assertEqual(library.read_bytes(), b"original library bytes")


if __name__ == "__main__":
    unittest.main()
