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
from unittest.mock import patch

from tools.candidate import isolate_cli_workspace
from tools.candidate_artifacts import (
    ROOT,
    SDK,
    crate_metadata,
    digest,
    release_version,
    source_version,
    verify_manifest,
    wheel_metadata,
)
from tools.cli_wheel_acceptance import matches_platform, verify_set
from tools.publish_candidate import main as publish_main
from tools.publish_candidate import upload_body
from tools.release_gate import REPOSITORY, job_policy, required_jobs, validate_run

SHA = "1" * 40
VERSION = "0.30.0"


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def crate(self, *, name="r2p-ffi", version=VERSION, **changes) -> Path:
        files = {
            "Cargo.toml": (
                f'[package]\nname="{name}"\nversion="{version}"\n'
                'license="MIT OR Apache-2.0"\n'
                f'[dependencies.r2p-build-config]\nversion="={version}"\n'
            ).encode(),
            ".cargo_vcs_info.json": json.dumps({"git": {"sha1": SHA}}).encode(),
            "LICENSE-MIT": (ROOT / "LICENSE-MIT").read_bytes(),
            "LICENSE-APACHE": (ROOT / "LICENSE-APACHE").read_bytes(),
        }
        files.update(changes)
        path = self.root / f"{name}-{version}.crate"
        with tarfile.open(path, "w:gz") as archive:
            for filename, content in files.items():
                if content is None:
                    continue
                member = tarfile.TarInfo(path.stem + "/" + filename)
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

    def test_registry_cli_workspace_boundary_preserves_manifest_and_is_idempotent(self):
        manifest = self.root / "Cargo.toml"
        original = '[package]\nname="r2p-introspection"\nversion="0.30.1"\n[dependencies]\nanyhow="1"\n'
        manifest.write_text(original)
        record = isolate_cli_workspace(self.root)
        self.assertEqual(manifest.read_text(), original + "\n[workspace]\n")
        self.assertNotEqual(record["before_sha256"], record["after_sha256"])
        self.assertEqual(
            isolate_cli_workspace(self.root)["before_sha256"], record["after_sha256"]
        )
        manifest.write_text(original + '\n[workspace]\nmembers=["other"]\n')
        with self.assertRaisesRegex(ValueError, "unexpected workspace"):
            isolate_cli_workspace(self.root)

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
        filename_version=VERSION,
        distribution="r2p-introspection",
        license=True,
        binary=True,
    ) -> Path:
        wheel_name = distribution.replace("-", "_")
        path = self.root / f"{wheel_name}-{filename_version}-{tag}.whl"
        with zipfile.ZipFile(path, "w") as archive:
            prefix = f"{wheel_name}-{filename_version}.dist-info/"
            archive.writestr(
                prefix + "METADATA", f"Name: {distribution}\nVersion: {version}\n"
            )
            archive.writestr(prefix + "WHEEL", f"Wheel-Version: 1.0\nTag: {tag}\n")
            if license:
                for name in ("LICENSE-MIT", "LICENSE-APACHE"):
                    archive.writestr(
                        prefix + "licenses/" + name, (ROOT / name).read_bytes()
                    )
            if binary:
                archive.writestr(
                    f"{wheel_name}-{filename_version}.data/scripts/r2p-introspection",
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

    def candidate_manifest(
        self, *, schema=2, version="0.30.1", consumer_version="0.2.0"
    ):
        manifest = {
            "schema_version": schema,
            "source_sha": SHA,
            "consumer_template_sha": SHA,
            "tool_sha": "3" * 40,
            "version_policy": "stable-sdk; cli=sdk; consumer=template",
            "result": "success",
            "public_release": False,
            "variants": {},
            "restoration": {
                "result": "success",
                "source_sha": "2" * 40,
                "from_version": version,
                "to_version": VERSION,
            },
        }
        destination = self.root
        for kind, sdk_version, sha in (
            ("candidate", version, SHA),
            ("baseline", VERSION, "2" * 40),
        ):
            self.root = destination / kind
            self.root.mkdir(exist_ok=True)
            crates = []
            for name in SDK:
                path = self.crate(
                    name=name,
                    version=sdk_version,
                    **{
                        ".cargo_vcs_info.json": json.dumps(
                            {"git": {"sha1": sha}}
                        ).encode()
                    },
                )
                crates.append(
                    crate_metadata(path, name, sdk_version, sha)
                    | {"path": str(path.relative_to(destination))}
                )
            wheels = []
            for abi, tag in (
                ("cli", "py3-none-macosx_11_0_arm64"),
                ("native", "cp314-cp314-macosx_11_0_arm64"),
                ("abi3", "cp39-abi3-macosx_11_0_arm64"),
            ):
                wheel_version = sdk_version if abi == "cli" else consumer_version
                name = "r2p-introspection" if abi == "cli" else "maturin-starter"
                path = self.wheel(
                    tag=tag,
                    version=wheel_version,
                    filename_version=wheel_version,
                    distribution=name,
                )
                wheels.append(
                    wheel_metadata(path, name, wheel_version, tag)
                    | {
                        "path": str(path.relative_to(destination)),
                        "source_sha": sha,
                        "kind": abi,
                    }
                )
            locks = {}
            for name in ("extension.lock", "embedding.lock", "cli.lock"):
                path = self.root / name
                path.write_text("fixture")
                locks[name] = digest(path)
            manifest["variants"][kind] = {
                "source_sha": sha,
                "version": sdk_version,
                "crates": crates,
                "wheels": wheels,
                "locks": locks,
                "consumer": {
                    "name": "maturin-starter",
                    "version": consumer_version,
                    "template_sha": SHA,
                },
                "registry_result": "success",
                "embedding": "success",
                "behavior": {
                    "native": dict.fromkeys(
                        ("function", "class", "exception"), "passed"
                    ),
                    "abi3": dict.fromkeys(("function", "class", "exception"), "passed"),
                    "cli": {"result": "success"},
                },
            }
        manifest["variants"]["candidate"]["negative_admission"] = dict.fromkeys(
            (
                "wrong_version",
                "missing_dependency",
                "tampered_crate",
                "missing_import",
                "wrong_abi",
            ),
            "blocked",
        )
        self.root = destination
        path = destination / "manifest.json"
        path.write_text(json.dumps(manifest))
        return path, manifest

    def test_cross_version_manifest_and_independent_consumer_version(self):
        path, original = self.candidate_manifest()
        self.assertEqual(
            verify_manifest(path, SHA)["variants"]["candidate"]["version"], "0.30.1"
        )
        for mutation in (
            "version",
            "consumer",
            "cli",
            "template",
            "restoration",
            "set",
            "sha",
            "policy",
        ):
            manifest = copy.deepcopy(original)
            candidate = manifest["variants"]["candidate"]
            if mutation == "version":
                candidate["version"] = VERSION
            elif mutation == "consumer":
                candidate["consumer"]["version"] = "0.3.0"
            elif mutation == "cli":
                candidate["wheels"][0]["version"] = VERSION
            elif mutation == "template":
                candidate["consumer"]["template_sha"] = "4" * 40
            elif mutation == "restoration":
                manifest["restoration"]["to_version"] = "0.29.0"
            elif mutation == "set":
                candidate["crates"].pop()
            elif mutation == "sha":
                manifest["variants"]["baseline"]["source_sha"] = "bad"
            else:
                manifest["version_policy"] = "uncontrolled"
            path.write_text(json.dumps(manifest))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                verify_manifest(path, SHA)

    def test_original_manifest_remains_verifiable(self):
        path, _ = self.candidate_manifest(
            schema=1, version=VERSION, consumer_version="0.1.0"
        )
        self.assertEqual(verify_manifest(path, SHA)["schema_version"], 1)

    def test_fixture_is_forbidden_for_external_publishing_before_any_network(self):
        path, manifest = self.candidate_manifest()
        manifest["variants"]["candidate"]["fixture_only"] = True
        path.write_text(json.dumps(manifest))
        with (
            patch(
                "sys.argv",
                ["publish", "--manifest", str(path), "--sha", SHA, "--execute"],
            ),
            patch("sys.stderr", new_callable=io.StringIO) as error,
            patch(
                "urllib.request.urlopen",
                side_effect=AssertionError("unexpected network"),
            ),
            self.assertRaises(SystemExit) as rejected,
        ):
            publish_main()
        self.assertEqual(rejected.exception.code, 2)
        self.assertIn("fixture artifacts are forbidden", error.getvalue())

    def test_stable_versions_and_mixed_source_rejected(self):
        self.assertEqual(release_version("12.3.45"), "12.3.45")
        for value in ("0.30", "v0.30.1", "00.30.1", "0.30.1-rc.1", "0.30.1+meta", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                release_version(value)
        for name in SDK:
            relative = (
                Path("Cargo.toml")
                if name == "r2p"
                else Path("crates") / name / "Cargo.toml"
            )
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())
        cli = self.root / "crates/r2p-introspection/pyproject.toml"
        cli.write_bytes((ROOT / "crates/r2p-introspection/pyproject.toml").read_bytes())
        self.assertEqual(source_version(self.root), VERSION)
        ffi = self.root / "crates/r2p-ffi/Cargo.toml"
        original = ffi.read_text()
        for text in (
            original.replace('version = "0.30.0"', 'version = "0.30.1"', 1),
            original.replace('version = "=0.30.0"', 'version = "0.30.0"', 1),
        ):
            ffi.write_text(text)
            with self.assertRaises(ValueError):
                source_version(self.root)
        ffi.write_text(original)
        cli.write_text('[project]\nname="r2p-introspection"\nversion="0.30.0"\n')
        with self.assertRaises(ValueError):
            source_version(self.root)


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
            for name in sorted(job_policy("1.85"))
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
        jobs = [job for job in self.jobs if job["name"] != future["name"]]
        self.assertEqual(validate_run(self.run, jobs + [future], SHA, "1.85"), [])
        for change in (
            {"conclusion": "cancelled"},
            {"name": "unknown-optional-job"},
            {"status": "in_progress"},
        ):
            self.assertTrue(
                validate_run(self.run, jobs + [future | change], SHA, "1.85")
            )
        self.assertTrue(validate_run(self.run, jobs, SHA, "1.85"))


if __name__ == "__main__":
    unittest.main()
