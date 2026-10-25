"""Upload the exact accepted .crate bytes; public publishing is disabled by default."""

from __future__ import annotations

import argparse
import json
import os
import struct
import tarfile
from pathlib import Path

import tomllib

from tools.candidate import index_entry
from tools.candidate_artifacts import SDK, digest, verify_manifest
from tools.engineering.registry_upload import Registry, publish


def upload_body(path: Path) -> bytes:
    with tarfile.open(path) as archive:
        (manifest_path,) = [
            member.name
            for member in archive.getmembers()
            if member.name.count("/") == 1 and member.name.endswith("/Cargo.toml")
        ]
        manifest_file = archive.extractfile(manifest_path)
        if manifest_file is None:
            raise ValueError("candidate manifest missing")
        manifest = tomllib.loads(manifest_file.read().decode())
        package = manifest["package"]
        metadata = {
            "name": package["name"],
            "vers": package["version"],
            "deps": [
                {
                    "name": dependency["package"] or dependency["name"],
                    "version_req": dependency["req"],
                    "features": dependency["features"],
                    "optional": dependency["optional"],
                    "default_features": dependency["default_features"],
                    "target": dependency["target"],
                    "kind": dependency["kind"],
                    "registry": dependency["registry"],
                    "explicit_name_in_toml": dependency["name"]
                    if dependency["package"]
                    else None,
                }
                for dependency in index_entry(manifest, "")["deps"]
            ],
            "features": manifest.get("features", {}),
            "authors": package.get("authors", []),
            "description": package.get("description"),
            "documentation": package.get("documentation"),
            "homepage": package.get("homepage"),
            "repository": package.get("repository"),
            "keywords": package.get("keywords", []),
            "categories": package.get("categories", []),
            "license": package.get("license"),
            "license_file": package.get("license-file"),
            "links": package.get("links"),
            "rust_version": package.get("rust-version"),
            "readme_file": package.get("readme"),
            "readme": None,
        }
        if package.get("readme"):
            readme = archive.extractfile(
                manifest_path.removesuffix("Cargo.toml") + package["readme"]
            )
            if readme is None:
                raise ValueError("candidate readme missing")
            metadata["readme"] = readme.read().decode()
    encoded = json.dumps(metadata, separators=(",", ":")).encode()
    crate = path.read_bytes()
    return (
        struct.pack("<I", len(encoded))
        + encoded
        + struct.pack("<I", len(crate))
        + crate
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--gate", type=Path)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--local-registry", help="loopback HTTP fixture only; never an external release"
    )
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--wait-timeout", type=float, default=300)
    parser.add_argument("--poll-interval", type=float, default=2)
    parser.add_argument("--retry-unindexed", action="store_true")
    args = parser.parse_args()
    manifest = verify_manifest(args.manifest, args.sha)
    gate_hash = None
    if not args.local_registry:
        if any(
            variant.get("fixture_only") for variant in manifest["variants"].values()
        ):
            parser.error(
                "release fixture artifacts are forbidden for external publishing"
            )
        if not args.gate:
            parser.error("successful same-source full CI gate is required")
        gate = json.loads(args.gate.read_text())
        if (
            gate.get("source_sha") != args.sha
            or gate.get("result") != "success"
            or gate.get("version") != manifest["variants"]["candidate"]["version"]
            or not isinstance(gate.get("run_id"), int)
            or gate["run_id"] <= 0
        ):
            parser.error("successful same-source full CI gate is required")
        gate_hash = digest(args.gate)
    if (
        args.execute
        and not args.local_registry
        and (
            os.environ.get("R2P_ENABLE_CRATES_IO") != "true"
            or not os.environ.get("CARGO_REGISTRY_TOKEN")
        )
    ):
        parser.error(
            "public release remains disabled or registry credentials are absent"
        )
    try:
        registry = Registry(
            args.local_registry,
            token=os.environ.get("CARGO_REGISTRY_TOKEN")
            if not args.local_registry
            else None,
        )
    except ValueError as error:
        parser.error(str(error))
    rows = sorted(
        manifest["variants"]["candidate"]["crates"],
        key=lambda row: SDK.index(row["name"]),
    )
    for row in rows:
        body = upload_body(args.manifest.parent / row["path"])
        print(
            f"Validated upload body for {row['name']} {row['version']} sha256={row['sha256']} bytes={len(body)}"
        )
    if args.execute:
        publish(
            rows,
            registry=registry,
            journal_path=args.journal or args.manifest.parent / "upload-journal.json",
            binding={
                "source_sha": args.sha,
                "manifest_sha256": digest(args.manifest),
                "gate_sha256": gate_hash,
                "scope": "local-fixture" if args.local_registry else "crates.io",
            },
            body_for=lambda row: upload_body(args.manifest.parent / row["path"]),
            timeout=args.wait_timeout,
            poll=args.poll_interval,
            retry_unindexed=args.retry_unindexed,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
