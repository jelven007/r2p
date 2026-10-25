"""Export or retrieve accepted candidate bytes without retaining build caches."""

from __future__ import annotations

import argparse
import json
import tarfile
from pathlib import Path

from tools.candidate_artifacts import digest, verify_manifest


def export(manifest_path: Path, destination: Path, sha: str) -> dict:
    manifest = verify_manifest(manifest_path, sha)
    root = manifest_path.parent
    paths = {manifest_path.name}
    for variant_name, variant in manifest["variants"].items():
        paths.update(row["path"] for row in variant["crates"] + variant["wheels"])
        paths.update(f"{variant_name}/{name}" for name in variant["locks"])
    record = {
        "schema_version": 1,
        "source_sha": sha,
        "manifest": manifest_path.name,
        "files": {name: digest(root / name) for name in sorted(paths)},
    }
    if "bundle.json" in paths or destination.exists():
        raise ValueError("bundle name collision or destination already exists")
    # The original manifest remains authoritative; this index covers only the
    # retained manifest, original artifacts and resolved consumer locks.
    import io

    with tarfile.open(destination, "x:gz") as archive:
        for name in sorted(paths):
            archive.add(root / name, arcname=name, recursive=False)
        data = (json.dumps(record, indent=2) + "\n").encode()
        entry = tarfile.TarInfo("bundle.json")
        entry.size = len(data)
        archive.addfile(entry, io.BytesIO(data))
    return record | {"bundle_sha256": digest(destination)}


def retrieve(bundle: Path, destination: Path, sha: str, checksum: str) -> dict:
    if digest(bundle) != checksum:
        raise ValueError("bundle digest differs from retained record")
    if destination.exists():
        raise ValueError("retrieve into a new directory")
    with tarfile.open(bundle, "r:gz") as archive:
        members = archive.getmembers()
        if any(
            not member.isfile()
            or Path(member.name).is_absolute()
            or ".." in Path(member.name).parts
            for member in members
        ) or len({member.name for member in members}) != len(members):
            raise ValueError("bundle contains unsafe or duplicate paths")
        record = json.load(archive.extractfile("bundle.json"))
        if (
            record.get("schema_version") != 1
            or record.get("source_sha") != sha
            or {member.name for member in members}
            != set(record["files"]) | {"bundle.json"}
            or record["manifest"] not in record["files"]
        ):
            raise ValueError("bundle source/index differs")
        destination.mkdir(parents=True)
        archive.extractall(destination, filter="data")
    for name, expected in record["files"].items():
        if digest(destination / name) != expected:
            raise ValueError(f"retrieved file digest differs: {name}")
    verify_manifest(destination / record["manifest"], sha)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("export", "retrieve"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--sha256")
    args = parser.parse_args()
    if args.action == "export":
        if not args.manifest:
            parser.error("export requires --manifest")
        record = export(args.manifest, args.bundle, args.sha)
    else:
        if not args.destination or not args.sha256:
            parser.error("retrieve requires --destination and the retained --sha256")
        record = retrieve(args.bundle, args.destination, args.sha, args.sha256)
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
