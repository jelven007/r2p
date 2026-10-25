"""Upload the exact accepted .crate bytes; public publishing is disabled by default."""

from __future__ import annotations

import argparse
import json
import os
import struct
import tarfile
import urllib.request
from pathlib import Path

import tomllib

from tools.candidate import index_entry
from tools.candidate_artifacts import verify_manifest


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
    parser.add_argument("--gate", required=True, type=Path)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    manifest = verify_manifest(args.manifest, args.sha)
    gate = json.loads(args.gate.read_text())
    if (
        gate.get("source_sha") != args.sha
        or gate.get("result") != "success"
        or gate.get("version") != manifest["variants"]["candidate"]["version"]
        or not gate.get("run_id")
    ):
        parser.error("successful same-source full CI gate is required")
    if args.execute and (
        os.environ.get("R2P_ENABLE_CRATES_IO") != "true"
        or not os.environ.get("CARGO_REGISTRY_TOKEN")
    ):
        parser.error(
            "public release remains disabled or registry credentials are absent"
        )
    for row in manifest["variants"]["candidate"]["crates"]:
        body = upload_body(args.manifest.parent / row["path"])
        if args.execute:
            request = urllib.request.Request(
                "https://crates.io/api/v1/crates/new",
                data=body,
                method="PUT",
                headers={
                    "Authorization": os.environ["CARGO_REGISTRY_TOKEN"],
                    "Content-Type": "application/octet-stream",
                    "User-Agent": "r2p-candidate-release/1",
                },
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                result = json.load(response)
            if result.get("errors"):
                raise RuntimeError(f"registry rejected {row['name']}")
        print(
            f"{'Uploaded' if args.execute else 'Validated upload body for'} {row['name']} {row['version']} sha256={row['sha256']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
