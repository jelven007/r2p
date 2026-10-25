"""Negative admission tests for package identity, wheel tags, and full CI results."""

from __future__ import annotations

import copy
import io
import json
import struct
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.candidate_artifacts import ROOT, crate_metadata, wheel_metadata
from tools.cli_wheel_acceptance import matches_platform, verify_set
from tools.publish_candidate import upload_body
from tools.release_gate import REPOSITORY, required_jobs, validate_run

SHA = "1" * 40
VERSION = "0.30.0"


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def crate(self, **changes) -> Path:
        files = {
            "Cargo.toml": (
                b'[package]\nname="r2p-ffi"\nversion="0.30.0"\n'
                b'license="MIT OR Apache-2.0"\n'
                b'[dependencies.r2p-build-config]\nversion="=0.30.0"\n'
            ),
            ".cargo_vcs_info.json": json.dumps({"git": {"sha1": SHA}}).encode(),
            "LICENSE-MIT": (ROOT / "LICENSE-MIT").read_bytes(),
            "LICENSE-APACHE": (ROOT / "LICENSE-APACHE").read_bytes(),
        }
        files.update(changes)
        path = self.root / "r2p-ffi-0.30.0.crate"
        with tarfile.open(path, "w:gz") as archive:
            for name, content in files.items():
                if content is None:
                    continue
                member = tarfile.TarInfo("r2p-ffi-0.30.0/" + name)
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
        return path

    def test_registry_upload_preserves_the_accepted_crate_bytes(self):
        crate = self.crate()
        body = upload_body(crate)
        (metadata_size,) = struct.unpack_from("<I", body)
        metadata = json.loads(body[4 : 4 + metadata_size])
        (crate_size,) = struct.unpack_from("<I", body, 4 + metadata_size)
        self.assertEqual(body[8 + metadata_size :], crate.read_bytes())
        self.assertEqual(crate_size, crate.stat().st_size)
        self.assertEqual((metadata["name"], metadata["vers"]), ("r2p-ffi", VERSION))
        self.assertEqual(metadata["deps"][0]["version_req"], "=0.30.0")

    def test_crate_source_and_exact_dependency(self):
        row = crate_metadata(self.crate(), "r2p-ffi", VERSION, SHA)
        self.assertEqual(row["internal_dependencies"], ["r2p-build-config"])
        for mutation in (
            "source",
            "dirty",
            "version",
            "license",
            "dependency",
            "path",
            "private",
            "content",
        ):
            changes = {}
            if mutation in {"source", "dirty"}:
                changes[".cargo_vcs_info.json"] = json.dumps(
                    {
                        "git": {
                            "sha1": "2" * 40 if mutation == "source" else SHA,
                            "dirty": mutation == "dirty",
                        }
                    }
                ).encode()
            elif mutation == "content":
                changes["LICENSE-MIT"] = b"wrong license"
            else:
                text = (
                    '[package]\nname="r2p-ffi"\nversion="0.30.0"\nlicense="MIT OR Apache-2.0"\n'
                    '[dependencies.r2p-build-config]\nversion="=0.30.0"\n'
                )
                if mutation == "version":
                    text = text.replace('version="0.30.0"', 'version="0.29.0"')
                elif mutation == "license":
                    text = text.replace("MIT OR Apache-2.0", "unlicensed")
                elif mutation == "dependency":
                    text = text.replace('version="=0.30.0"', 'version="0.30.0"')
                elif mutation == "path":
                    text += 'path="../r2p-build-config"\n'
                elif mutation == "private":
                    text += '[dependencies.pyo3-ffi]\nversion="0.30.0"\n'
                changes["Cargo.toml"] = text.encode()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                crate_metadata(self.crate(**changes), "r2p-ffi", VERSION, SHA)
        with self.assertRaises(KeyError):
            crate_metadata(
                self.crate(**{"LICENSE-APACHE": None}), "r2p-ffi", VERSION, SHA
            )

    def wheel(
        self,
        *,
        tag="py3-none-macosx_11_0_arm64",
        version=VERSION,
        license=True,
        binary=True,
    ) -> Path:
        path = self.root / f"r2p_introspection-{VERSION}-{tag}.whl"
        with zipfile.ZipFile(path, "w") as archive:
            prefix = f"r2p_introspection-{VERSION}.dist-info/"
            archive.writestr(
                prefix + "METADATA", f"Name: r2p-introspection\nVersion: {version}\n"
            )
            archive.writestr(prefix + "WHEEL", f"Wheel-Version: 1.0\nTag: {tag}\n")
            if license:
                for name in ("LICENSE-MIT", "LICENSE-APACHE"):
                    archive.writestr(
                        prefix + "licenses/" + name, (ROOT / name).read_bytes()
                    )
            if binary:
                archive.writestr(
                    f"r2p_introspection-{VERSION}.data/scripts/r2p-introspection",
                    b"fixture",
                )
        return path

    def test_wheel_metadata_does_not_replace_execution(self):
        tag = "py3-none-macosx_11_0_arm64"
        self.assertEqual(
            wheel_metadata(self.wheel(), "r2p-introspection", VERSION, tag)["tags"],
            [tag],
        )
        for fields in (
            {"version": "0.29.0"},
            {"tag": "cp39-abi3-macosx_11_0_arm64"},
            {"license": False},
            {"binary": False},
        ):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                wheel_metadata(self.wheel(**fields), "r2p-introspection", VERSION, tag)

    def test_native_platform_and_abi_must_match_the_record(self):
        for platform_id, tag in (
            ("linux-x86_64", "py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64"),
            ("linux-aarch64", "py3-none-manylinux_2_17_aarch64"),
            ("windows-x64", "py3-none-win_amd64"),
            ("windows-x86", "py3-none-win32"),
            ("windows-aarch64", "py3-none-win_arm64"),
            ("macos-x86_64", "py3-none-macosx_10_12_x86_64"),
            ("macos-aarch64", "py3-none-macosx_11_0_arm64"),
        ):
            with self.subTest(platform_id=platform_id):
                self.assertTrue(matches_platform(tag, platform_id))
                self.assertFalse(
                    matches_platform(tag.replace("py3-none", "cp39-abi3"), platform_id)
                )
        self.assertFalse(
            matches_platform("py3-none-macosx_11_0_arm64", "linux-aarch64")
        )
        self.assertFalse(matches_platform("py3-none-macosx_11_0_arm64", "macos-x86_64"))

    def test_publish_set_requires_seven_distinct_accepted_native_wheels(self):
        tags = {
            "linux-x86_64": "manylinux_2_17_x86_64",
            "linux-aarch64": "manylinux_2_17_aarch64",
            "windows-x64": "win_amd64",
            "windows-x86": "win32",
            "windows-aarch64": "win_arm64",
            "macos-x86_64": "macosx_10_12_x86_64",
            "macos-aarch64": "macosx_11_0_arm64",
        }
        records = {}
        for platform_id, platform_tag in tags.items():
            tag = "py3-none-" + platform_tag
            path = self.wheel(tag=tag)
            record = {
                "schema_version": 1,
                "source_sha": SHA,
                "platform_id": platform_id,
                "artifact": wheel_metadata(path, "r2p-introspection", VERSION, tag)
                | {"path": path.name},
                "behavior": {"result": "success"},
                "result": "success",
            }
            record_path = self.root / f"cli-acceptance-{platform_id}.json"
            record_path.write_text(json.dumps(record))
            records[platform_id] = (record_path, record)
        self.assertEqual(len(verify_set(self.root, SHA, VERSION)), 7)
        record_path, original = records["linux-aarch64"]
        for mutation in ("source", "platform", "hash", "behavior", "duplicate"):
            record = copy.deepcopy(original)
            if mutation == "source":
                record["source_sha"] = "2" * 40
            elif mutation == "platform":
                record["artifact"] = records["macos-aarch64"][1]["artifact"]
            elif mutation == "hash":
                record["artifact"]["sha256"] = "0" * 64
            elif mutation == "behavior":
                record["behavior"]["result"] = "failure"
            elif mutation == "duplicate":
                record["platform_id"] = "linux-x86_64"
            record_path.write_text(json.dumps(record))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                verify_set(self.root, SHA, VERSION)
        record_path.unlink()
        with self.assertRaises(ValueError):
            verify_set(self.root, SHA, VERSION)
        record_path.write_text(json.dumps(original))
        self.wheel(tag="py3-none-macosx_12_0_arm64")
        with self.assertRaises(ValueError):
            verify_set(self.root, SHA, VERSION)


class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.run = {
            "head_sha": SHA,
            "name": "CI",
            "path": ".github/workflows/ci.yml",
            "repository": {"full_name": REPOSITORY},
            "status": "completed",
            "conclusion": "success",
        }
        self.jobs = [
            {"name": name, "status": "completed", "conclusion": "success"}
            for name in sorted(required_jobs("1.85"))
        ]

    def test_completed_exact_full_matrix_is_required(self):
        self.assertEqual(validate_run(self.run, self.jobs, SHA, "1.85"), [])
        for name in required_jobs("1.85"):
            for conclusion in ("failure", "cancelled", "skipped", None):
                jobs = copy.deepcopy(self.jobs)
                next(job for job in jobs if job["name"] == name)["conclusion"] = (
                    conclusion
                )
                with self.subTest(name=name, conclusion=conclusion):
                    self.assertTrue(validate_run(self.run, jobs, SHA, "1.85"))
        self.assertTrue(validate_run(self.run, self.jobs[:-1], SHA, "1.85"))
        self.assertTrue(validate_run(self.run, self.jobs + self.jobs[:1], SHA, "1.85"))

    def test_stale_wrong_workflow_and_incomplete_run_block(self):
        for key, value in (
            ("head_sha", "2" * 40),
            ("name", "benches"),
            ("path", ".github/workflows/other.yml"),
            ("repository", {"full_name": "other/repository"}),
            ("status", "in_progress"),
            ("conclusion", "failure"),
        ):
            run = self.run | {key: value}
            with self.subTest(key=key):
                self.assertTrue(validate_run(run, self.jobs, SHA, "1.85"))

    def test_only_declared_forward_toolchains_can_tolerate_failure(self):
        future = {
            "name": "python3.14-x64 ubuntu-latest rust-nightly / build",
            "status": "completed",
            "conclusion": "failure",
        }
        self.assertEqual(validate_run(self.run, self.jobs + [future], SHA, "1.85"), [])
        for change in (
            {"conclusion": "cancelled"},
            {"name": "unknown-optional-job"},
            {"status": "in_progress"},
        ):
            self.assertTrue(
                validate_run(self.run, self.jobs + [future | change], SHA, "1.85")
            )


if __name__ == "__main__":
    unittest.main()
