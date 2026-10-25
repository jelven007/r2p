"""Validate immutable candidate packages and run the introspection CLI wheel."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
import sys
import tarfile
import zipfile
from email.parser import Parser
from itertools import product
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent
SDK = (
    "r2p-build-config",
    "r2p-macros-backend",
    "r2p-ffi",
    "r2p-macros",
    "r2p",
    "r2p-introspection",
)
LICENSE = "MIT OR Apache-2.0"


def release_version(value: str) -> str:
    """Stable Rust/Python versions share one spelling; prereleases need a policy."""
    if not isinstance(value, str) or not re.fullmatch(
        r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value
    ):
        raise ValueError("candidate requires a canonical stable MAJOR.MINOR.PATCH")
    return value


def source_version(root: Path) -> str:
    """Read each immutable source's SDK version and reject a mixed package set."""
    version = release_version(
        tomllib.loads((root / "Cargo.toml").read_text())["package"]["version"]
    )
    for name in SDK:
        directory = root if name == "r2p" else root / "crates" / name
        manifest = tomllib.loads((directory / "Cargo.toml").read_text())
        if (
            manifest["package"]["name"] != name
            or manifest["package"]["version"] != version
        ):
            raise ValueError(f"SDK source version/name differs: {name}")
        for section in (manifest, *manifest.get("target", {}).values()):
            for key in ("dependencies", "build-dependencies", "dev-dependencies"):
                for alias, fields in section.get(key, {}).items():
                    if (
                        isinstance(fields, dict)
                        and fields.get("package", alias) in SDK
                        and fields.get("version") != f"={version}"
                    ):
                        raise ValueError(
                            f"SDK source dependency is not exact: {name}/{alias}"
                        )
    cli = tomllib.loads((root / "crates/r2p-introspection/pyproject.toml").read_text())[
        "project"
    ]
    if (
        cli["name"] != "r2p-introspection"
        or "version" not in cli.get("dynamic", [])
        or "version" in cli
    ):
        raise ValueError("CLI distribution version must be derived from its SDK crate")
    return version


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def crate_metadata(path: Path, name: str, version: str, sha: str) -> dict:
    with tarfile.open(path) as archive:
        prefix = f"{name}-{version}/"

        def read(relative: str) -> bytes:
            member = archive.extractfile(prefix + relative)
            if member is None:
                raise ValueError(f"missing {relative} in {path}")
            return member.read()

        manifest = tomllib.loads(read("Cargo.toml").decode())
        package = manifest["package"]
        vcs = json.loads(read(".cargo_vcs_info.json"))
        if (
            package["name"] != name
            or package["version"] != version
            or package["license"] != LICENSE
            or vcs["git"]["sha1"] != sha
            or vcs["git"].get("dirty", False)
        ):
            raise ValueError(f"package identity/license/source mismatch: {path}")
        for filename in ("LICENSE-MIT", "LICENSE-APACHE"):
            if read(filename) != (ROOT / filename).read_bytes():
                raise ValueError(f"license content mismatch: {path}")
        dependencies = []
        sections = [manifest]
        sections.extend(manifest.get("target", {}).values())
        for section in sections:
            for kind in ("dependencies", "build-dependencies", "dev-dependencies"):
                for alias, dependency in section.get(kind, {}).items():
                    actual = dependency.get("package", alias)
                    if actual in SDK:
                        if dependency.get("version") != f"={version}" or any(
                            key in dependency for key in ("path", "git")
                        ):
                            raise ValueError(f"unbound SDK dependency in {path}")
                        dependencies.append(actual)
                    elif actual.startswith(("r2p-", "pyo3")):
                        raise ValueError(f"private/legacy dependency in {path}")
        if any(
            member.name.startswith(prefix + directory)
            for member in archive.getmembers()
            for directory in ("tools/", "python/", "benchmarks/")
        ):
            raise ValueError(f"private distribution content in {path}")
    return {
        "name": name,
        "version": version,
        "source_sha": sha,
        "license": package["license"],
        "internal_dependencies": sorted(set(dependencies)),
        "sha256": digest(path),
        "bytes": path.stat().st_size,
    }


def wheel_metadata(path: Path, name: str, version: str, expected_tag: str) -> dict:
    with zipfile.ZipFile(path) as archive:
        files = archive.namelist()
        (metadata_file,) = [file for file in files if file.endswith("/METADATA")]
        metadata = Parser().parsestr(archive.read(metadata_file).decode())
        (wheel_file,) = [file for file in files if file.endswith("/WHEEL")]
        wheel = Parser().parsestr(archive.read(wheel_file).decode())
        tags = wheel.get_all("Tag", [])
        expanded_tags = {
            "-".join(parts)
            for parts in product(*(part.split(".") for part in expected_tag.split("-")))
        }
        if (
            metadata["Name"] != name
            or metadata["Version"] != version
            or not path.name.startswith(f"{name.replace('-', '_')}-{version}-")
            or set(tags) not in (expanded_tags, {expected_tag})
            or not path.name.endswith(expected_tag + ".whl")
        ):
            raise ValueError(f"wheel identity/version/ABI/tag mismatch: {path}")
        for filename in ("LICENSE-MIT", "LICENSE-APACHE"):
            matches = [file for file in files if file.endswith("/" + filename)]
            if not matches or not any(
                archive.read(file) == (ROOT / filename).read_bytes() for file in matches
            ):
                raise ValueError(f"missing/incorrect wheel license: {path}")
        if name == "r2p-introspection" and not any(
            ".data/scripts/r2p-introspection" in file for file in files
        ):
            raise ValueError("CLI wheel has no executable")
    return {
        "name": name,
        "version": version,
        "tags": tags,
        "filename_tag": expected_tag,
        "sha256": digest(path),
        "bytes": path.stat().st_size,
    }


def elf_fixture() -> bytes:
    """A non-executable ELF with two exported metadata objects and a PT_LOAD."""
    chunks = [
        {"type": "module", "id": "root", "name": "candidate", "members": ["fn"]},
        {
            "type": "function",
            "id": "fn",
            "name": "answer",
            "arguments": {},
        },
    ]
    binary = bytearray(1408)
    ident = b"\x7fELF\x02\x01\x01" + bytes(9)
    struct.pack_into(
        "<16sHHIQQQIHHHHHH",
        binary,
        0,
        ident,
        3,
        62,
        1,
        0,
        64,
        1024,
        0,
        64,
        56,
        1,
        64,
        4,
        0,
    )
    struct.pack_into("<IIQQQQQQ", binary, 64, 1, 4, 0, 0, 0, 1408, 1408, 8)
    strings = bytearray(b"\0")
    offset = 128
    for index, chunk in enumerate(chunks, 1):
        name_offset = len(strings)
        strings.extend(f"R2P_INTROSPECTION_1_{index}\0".encode())
        payload = json.dumps(chunk, separators=(",", ":")).encode()
        payload = struct.pack("<I", len(payload)) + payload
        binary[offset : offset + len(payload)] = payload
        struct.pack_into(
            "<IBBHQQ",
            binary,
            640 + 24 * index,
            name_offset,
            0x11,
            0,
            1,
            offset,
            len(payload),
        )
        offset += len(payload)
    binary[512 : 512 + len(strings)] = strings
    for index, values in enumerate(
        (
            (0, 1, 2, 128, 128, offset - 128, 0, 0, 4, 0),
            (0, 3, 0, 0, 512, len(strings), 0, 0, 1, 0),
            (0, 2, 0, 0, 640, 72, 2, 1, 8, 24),
        ),
        1,
    ):
        struct.pack_into("<IIQQQQIIQQ", binary, 1024 + 64 * index, *values)
    return bytes(binary)


def check_cli(executable: Path, directory: Path) -> dict:
    directory.mkdir(parents=True)
    fixture = directory / "fixture.elf"
    fixture.write_bytes(elf_fixture())
    bad = subprocess.run([str(executable)], capture_output=True, text=True, check=False)
    if bad.returncode == 0 or "takes three arguments" not in bad.stderr:
        raise ValueError("CLI did not reject missing arguments")
    malformed = directory / "malformed.bin"
    malformed.write_bytes(b"truncated")
    invalid = subprocess.run(
        [str(executable), str(malformed), "candidate", str(directory / "invalid")],
        capture_output=True,
        text=True,
        check=False,
    )
    if invalid.returncode == 0:
        raise ValueError("CLI accepted malformed input")
    subprocess.run(
        [str(executable), str(fixture), "candidate", str(directory / "stubs")],
        capture_output=True,
        text=True,
        check=True,
    )
    stubs = list((directory / "stubs").rglob("*.pyi"))
    if len(stubs) != 1 or "def answer():" not in stubs[0].read_text():
        raise ValueError("CLI did not generate the expected module/function stub")
    subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import ast,sys; ast.parse(open(sys.argv[1]).read())",
            str(stubs[0]),
        ],
        check=True,
    )
    return {
        "argument_error": bad.returncode,
        "malformed_input": invalid.returncode,
        "fixture_sha256": digest(fixture),
        "stub": stubs[0].read_text(),
        "result": "success",
    }


def verify_manifest(path: Path, sha: str) -> dict:
    manifest = json.loads(path.read_text())
    schema = manifest.get("schema_version")
    if (
        schema not in {1, 2}
        or manifest.get("source_sha") != sha
        or not re.fullmatch(r"[0-9a-f]{40}", sha)
        or manifest.get("result") != "success"
        or manifest.get("public_release") is not False
    ):
        raise ValueError("candidate is incomplete or has a different source")
    if set(manifest.get("variants", {})) != {"candidate", "baseline"}:
        raise ValueError("candidate and retained baseline are required")
    if schema == 2 and (
        manifest.get("version_policy") != "stable-sdk; cli=sdk; consumer=template"
        or manifest.get("consumer_template_sha") != sha
        or not re.fullmatch(r"[0-9a-f]{40}", manifest.get("tool_sha", ""))
    ):
        raise ValueError("candidate template/tool/version policy differs")
    native_prefix = None
    if schema == 2:
        target = manifest.get("target_python", {})
        python_version = target.get("version", [])
        if (
            target.get("implementation") != "cpython"
            or target.get("free_threaded") is not False
            or target.get("gil_enabled") is not True
            or len(python_version) != 3
            or python_version[0] != 3
            or python_version[1] < 9
        ):
            raise ValueError(
                "native/abi3 acceptance requires a recorded GIL CPython target"
            )
        abi = f"cp{python_version[0]}{python_version[1]}"
        native_prefix = f"{abi}-{abi}-"
    for variant_name, variant in manifest["variants"].items():
        version = release_version(variant["version"])
        if schema == 1 and version != "0.30.0":
            raise ValueError("candidate SDK version differs from the accepted contract")
        if not re.fullmatch(r"[0-9a-f]{40}", variant["source_sha"]):
            raise ValueError("variant source is not an immutable SHA")
        consumer = (
            variant.get("consumer", {})
            if schema == 2
            else {"name": "maturin-starter", "version": "0.1.0"}
        )
        consumer_version = release_version(consumer.get("version"))
        if consumer.get("name") != "maturin-starter" or (
            schema == 2 and consumer.get("template_sha") != sha
        ):
            raise ValueError("consumer identity/template differs")
        packages = variant["crates"]
        if {row["name"] for row in packages} != set(SDK) or len(packages) != len(SDK):
            raise ValueError("candidate SDK package set differs")
        if {row["kind"] for row in variant["wheels"]} != {
            "native",
            "abi3",
            "cli",
        } or len(variant["wheels"]) != 3:
            raise ValueError("candidate wheel set differs")
        for row in variant["crates"] + variant["wheels"]:
            artifact = (path.parent / row["path"]).resolve()
            if (
                not artifact.is_relative_to(path.parent.resolve())
                or digest(artifact) != row["sha256"]
            ):
                raise ValueError("candidate artifact hash/path mismatch")
            if row["source_sha"] != variant["source_sha"]:
                raise ValueError("artifact source differs from variant")
            if row in variant["crates"]:
                if artifact.suffix != ".crate" or row["version"] != version:
                    raise ValueError("SDK artifact kind/version differs")
                crate_metadata(artifact, row["name"], version, variant["source_sha"])
            else:
                kind = row["kind"]
                expected_name = (
                    "r2p-introspection" if kind == "cli" else consumer["name"]
                )
                expected_version = version if kind == "cli" else consumer_version
                tag = row["filename_tag"]
                if (
                    artifact.suffix != ".whl"
                    or row["name"] != expected_name
                    or row["version"] != expected_version
                    or (kind == "cli" and not tag.startswith("py3-none-"))
                    or (kind == "abi3" and not tag.startswith("cp39-abi3-"))
                    or (kind == "native" and not re.match(r"cp[0-9]+-cp[0-9]+-", tag))
                    or (
                        kind == "native"
                        and native_prefix
                        and not tag.startswith(native_prefix)
                    )
                ):
                    raise ValueError("candidate wheel distribution/version/ABI differs")
                wheel_metadata(artifact, expected_name, expected_version, tag)
        if len(variant.get("locks", {})) != 3:
            raise ValueError("candidate consumer/embedding/CLI locks are incomplete")
        for name, checksum in variant["locks"].items():
            lock = (path.parent / variant_name / name).resolve()
            if (
                not lock.is_relative_to(path.parent.resolve())
                or digest(lock) != checksum
            ):
                raise ValueError("candidate lock hash/path mismatch")
        if variant.get("registry_result") != "success":
            raise ValueError("candidate registry behavior is incomplete")
        for kind in ("native", "abi3"):
            if any(
                variant.get("behavior", {}).get(kind, {}).get(key) != "passed"
                for key in ("function", "class", "exception")
            ):
                raise ValueError("candidate extension behavior is incomplete")
        if (
            variant.get("embedding") != "success"
            or variant.get("behavior", {}).get("cli", {}).get("result") != "success"
        ):
            raise ValueError("candidate Rust/CLI behavior is incomplete")
    if (
        manifest["variants"]["candidate"]["source_sha"] != sha
        or manifest["variants"]["baseline"]["source_sha"] == sha
    ):
        raise ValueError("candidate and baseline sources differ from the contract")
    if manifest.get("restoration", {}).get("result") != "success":
        raise ValueError("candidate restoration is incomplete")
    if manifest["restoration"]["source_sha"] != manifest["variants"]["baseline"][
        "source_sha"
    ] or manifest["variants"]["candidate"].get("negative_admission") != {
        "wrong_version": "blocked",
        "missing_dependency": "blocked",
        "tampered_crate": "blocked",
        "missing_import": "blocked",
        "wrong_abi": "blocked",
    }:
        raise ValueError("candidate negative admission/restoration differs")
    if schema == 2 and (
        manifest["restoration"].get("from_version")
        != manifest["variants"]["candidate"]["version"]
        or manifest["restoration"].get("to_version")
        != manifest["variants"]["baseline"]["version"]
    ):
        raise ValueError("restoration versions differ from the two variants")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify", "cli"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--sha")
    parser.add_argument("--executable", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "verify":
        if not args.manifest or not args.sha:
            parser.error("--manifest and --sha are required")
        result = verify_manifest(args.manifest, args.sha)
    else:
        if not args.executable:
            parser.error("--executable is required")
        result = check_cli(args.executable, args.output.parent / "cli-behavior")
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
