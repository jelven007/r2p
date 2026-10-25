"""Replay an observed upstream patch in an isolated checkout and inventory local differences."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "docs/governance/upstream-sync.json"


def git(*arguments: str, cwd: Path = ROOT) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=cwd)


def category(path: str) -> str:
    if path.startswith(
        ("docs/", "assets/", "newsfragments/", "r2p-newsfragments/")
    ) or path.endswith(".md"):
        return "documentation-and-assets"
    if path.startswith(("examples/", "python/", "tools/maturin-bridge/")):
        return "packaging-adapters"
    if path.endswith("Cargo.toml") or path in {"product.toml", "pyproject.toml"}:
        return "identity-and-layout"
    return "local-functionality-and-engineering"


def replay(manifest: dict, upstream_patch: bytes, output: Path) -> dict:
    if hashlib.sha256(upstream_patch).hexdigest() != manifest["source_patch_sha256"]:
        raise ValueError("upstream patch hash mismatch")
    if not upstream_patch.startswith(f"From {manifest['source_sha']} ".encode()):
        raise ValueError("upstream patch source SHA mismatch")
    output.mkdir(parents=True, exist_ok=True)
    checkout = Path(tempfile.mkdtemp(prefix="checkout-", dir=output))
    archive = git("archive", manifest["r2p_before"])
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        source.extractall(checkout, filter="data")
    # A nested directory without its own Git root would silently ignore patch
    # paths outside its prefix in the enclosing repository.
    git("init", "--quiet", cwd=checkout)
    original = subprocess.run(
        ["git", "apply", "--check", "-"],
        input=upstream_patch,
        cwd=checkout,
        capture_output=True,
        check=False,
    )
    paths = sorted({path for change in manifest["changes"] for path in change["files"]})
    before = {path: (checkout / path).read_text() for path in paths}
    after = before.copy()
    for change in manifest["changes"]:
        if change["old"].split("@", 1)[0] in {
            "taiki-e/install-action",
            "CodSpeedHQ/action",
        } and (
            change["old"] not in upstream_patch.decode()
            or change["new"] not in upstream_patch.decode()
        ):
            raise ValueError("mapped pin is absent from the source patch")
        for path, count in change["files"].items():
            if after[path].count(change["old"]) != count:
                raise ValueError(f"unexpected pin/context count in {path}")
            after[path] = after[path].replace(change["old"], change["new"])
    mapped = "".join(
        f"diff --git a/{path} b/{path}\n"
        + "".join(
            difflib.unified_diff(
                before[path].splitlines(keepends=True),
                after[path].splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )
        for path in paths
    ).encode()
    subprocess.run(
        ["git", "apply", "--check", "-"], cwd=checkout, input=mapped, check=True
    )
    subprocess.run(["git", "apply", "-"], cwd=checkout, input=mapped, check=True)
    files = {}
    for path in paths:
        actual = (checkout / path).read_text()
        if actual != after[path]:
            raise ValueError(f"replayed content mismatch: {path}")
        files[path] = {
            "before_sha256": hashlib.sha256(before[path].encode()).hexdigest(),
            "after_sha256": hashlib.sha256(actual.encode()).hexdigest(),
        }
    (output / "upstream.patch").write_bytes(upstream_patch)
    (output / "mapped.patch").write_bytes(mapped)
    differences = (
        git(
            "diff",
            "--name-status",
            "--no-renames",
            manifest["source_parent"],
            manifest["r2p_before"],
        )
        .decode()
        .splitlines()
    )
    inventory = []
    for line in differences:
        state, path = line.split("\t", 1)
        group = category(path)
        inventory.append(
            {
                "path": path,
                "change": state,
                "category": group,
                "owner": manifest["patch_owners"][group],
            }
        )
    (output / "local-differences.json").write_text(
        json.dumps(inventory, indent=2) + "\n"
    )
    evidence = {
        "schema_version": 1,
        "source_sha": manifest["source_sha"],
        "source_parent": manifest["source_parent"],
        "r2p_before": manifest["r2p_before"],
        "owner": manifest["owner"],
        "original_patch_exit_code": original.returncode,
        "original_conflicts": original.stderr.decode(),
        "mapped_patch_sha256": hashlib.sha256(mapped).hexdigest(),
        "mapped_patch_applied": True,
        "files": files,
        "inventory_count": len(inventory),
        "categories": {
            group: sum(row["category"] == group for row in inventory)
            for group in manifest["patch_owners"]
        },
        "scope": manifest["scope"],
        "replaced_local_patches": manifest["replaced_local_patches"],
    }
    (output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--patch", type=Path, required=True, help="exact upstream commit patch"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = replay(
        json.loads(MANIFEST.read_text()), args.patch.read_bytes(), args.output
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
