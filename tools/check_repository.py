"""Validate product identity, repository paths and document links (Python 3.11+)."""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import tomllib

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ("crates", "tests", "examples", "benchmarks", "tools", "python")
GENERATED_DIRS = {
    "target",
    ".template",
    "subprojects",
    "node_modules",
    ".nox",
    ".venv",
    "__pycache__",
    "dist",
    "build",
    "book",
}


def source_files(directory: str):
    for parent, directories, files in os.walk(ROOT / directory):
        directories[:] = [name for name in directories if name not in GENERATED_DIRS]
        for name in files:
            yield Path(parent) / name


def manifests() -> list[Path]:
    paths = [ROOT / "Cargo.toml"]
    for directory in SCAN_DIRS:
        paths.extend(
            path for path in source_files(directory) if path.name == "Cargo.toml"
        )
    return sorted(set(paths))


def check_manifest(path: Path) -> list[str]:
    data = tomllib.loads(path.read_text())
    errors = []

    def visit(value: object) -> None:
        if isinstance(value, dict):
            dependency_path = value.get("path")
            if isinstance(dependency_path, str):
                target = path.parent / dependency_path
                # Cargo also uses `path` for library/example/test source files.
                if not target.exists():
                    errors.append(
                        f"{path.relative_to(ROOT)}: missing {dependency_path}"
                    )
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(data)
    for member in data.get("workspace", {}).get("members", []):
        if not list(path.parent.glob(f"{member}/Cargo.toml")):
            errors.append(
                f"{path.relative_to(ROOT)}: missing workspace member {member}"
            )
    readme = data.get("package", {}).get("readme")
    if isinstance(readme, str) and not (path.parent / readme).is_file():
        errors.append(f"{path.relative_to(ROOT)}: missing readme {readme}")
    return errors


def engineering_docs() -> list[Path]:
    paths = [
        ROOT / name
        for name in ("README.md", "Architecture.md", "Contributing.md", "Releasing.md")
    ]
    paths.extend(
        path
        for path in (ROOT / "docs").rglob("*.md")
        if not {"guide", "reference"} & set(path.relative_to(ROOT / "docs").parts)
    )
    paths.extend(ROOT / directory / "README.md" for directory in SCAN_DIRS)
    paths.extend(
        ROOT / directory / "README.md" for directory in ("infrastructure", "assets")
    )
    paths.append(ROOT / "docs" / "reference" / "README.md")
    return sorted({path for path in paths if path.is_file()})


def check_document(path: Path) -> list[str]:
    errors = []
    # Ignore fenced examples; their link syntax can describe fictitious inputs.
    text = re.sub(r"(?ms)^```.*?^```\s*$", "", path.read_text())
    links = re.findall(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+[^)]*)?\)", text)
    links.extend(re.findall(r"(?m)^\[[^\]]+\]:\s*(\S+)", text))
    for link in links:
        url = urlsplit(link.strip("<>"))
        if url.scheme or url.netloc or not url.path:
            continue
        target = (
            ROOT / unquote(url.path.lstrip("/"))
            if url.path.startswith("/")
            else path.parent / unquote(url.path)
        )
        if not target.exists():
            errors.append(f"{path.relative_to(ROOT)}: broken link {link}")
    return errors


def check_includes() -> list[str]:
    errors = []
    for path in (ROOT / "docs" / "guide").rglob("*.md"):
        for target in re.findall(r"\{\{#include\s+([^}\s]+)", path.read_text()):
            # mdBook supports a line range/anchor suffix after the filename.
            if not (path.parent / target.split(":")[0]).is_file():
                errors.append(f"{path.relative_to(ROOT)}: missing include {target}")
    source = (ROOT / "src" / "lib.rs").read_text()
    for target in re.findall(r'"((?:guide/src/|reference/|sdk/)[^"]+\.md)"', source):
        if not (ROOT / "docs" / target).is_file():
            errors.append(f"src/lib.rs: missing doctest input {target}")
    return errors


def check_traceability() -> list[str]:
    errors = []
    specification = (
        ROOT / "docs" / "requirements" / "system-requirements.md"
    ).read_text()
    requirements = dict(
        re.findall(r"(?m)^\|\s*((?:FR|NFR)-\d{3})\s*\|\s*(P[01])\s*\|", specification)
    )
    gates = set(re.findall(r"(?m)^\|\s*(G\d+)\s*\|", specification))
    matrix = ROOT / "docs" / "requirements" / "traceability.csv"
    with matrix.open(newline="") as file:
        reader = csv.DictReader(file)
        columns = [
            "id",
            "priority",
            "capability_status",
            "source",
            "design",
            "test_evidence",
            "acceptance_gate",
            "owner",
        ]
        if reader.fieldnames != columns:
            return ["traceability.csv: unexpected columns"]
        seen = set()
        for row in reader:
            identifier = row["id"]
            if None in row or any(not row.get(column) for column in columns):
                errors.append(f"traceability.csv: incomplete row {identifier}")
                continue
            if identifier in seen:
                errors.append(f"traceability.csv: duplicate {identifier}")
            seen.add(identifier)
            if requirements.get(identifier) != row["priority"]:
                errors.append(
                    f"traceability.csv: unknown ID or wrong priority {identifier}"
                )
            for column in ("source", "design", "test_evidence"):
                target = (ROOT / row[column]).resolve()
                if not target.is_relative_to(ROOT) or not target.is_file():
                    errors.append(
                        f"traceability.csv: {identifier} missing {column} {row[column]}"
                    )
            for gate in row["acceptance_gate"].split("+"):
                if gate not in gates:
                    errors.append(f"traceability.csv: {identifier} unknown gate {gate}")
        for identifier in sorted(requirements.keys() - seen):
            errors.append(f"traceability.csv: missing requirement {identifier}")
    return errors


def check_symlinks() -> list[str]:
    errors = []
    for directory in (*SCAN_DIRS, "assets", "infrastructure", "docs"):
        for path in source_files(directory):
            if path.is_symlink() and not path.exists():
                errors.append(f"{path.relative_to(ROOT)}: broken symbolic link")
    for name in ("LICENSE-APACHE", "LICENSE-MIT"):
        path = ROOT / "python" / "r2p-runtime" / name
        if not path.is_file() or path.is_symlink():
            errors.append(
                f"{path.relative_to(ROOT)}: Python distribution needs a regular license file"
            )
        elif path.read_bytes() != (ROOT / name).read_bytes():
            errors.append(f"{path.relative_to(ROOT)}: shared license content differs")
    return errors


def check_product_identity() -> list[str]:
    path = ROOT / "product.toml"
    if not path.is_file():
        return ["product.toml: missing product identity"]
    data = tomllib.loads(path.read_text())
    name = data.get("product", {}).get("name")
    if data.get("schema_version") != 1 or not isinstance(name, str) or not name:
        return ["product.toml: invalid schema version or product name"]
    errors = []
    for relative in ("README.md", "docs/README.md"):
        document = ROOT / relative
        if not document.is_file() or not document.read_text().startswith(f"# {name} "):
            errors.append(f"{relative}: product title does not match {name}")
    implementation = data.get("implementation", {})
    cargo = tomllib.loads((ROOT / "Cargo.toml").read_text())
    if implementation.get("rust_package") != cargo["package"]["name"]:
        errors.append(
            "product.toml: Rust implementation package differs from Cargo.toml"
        )
    repository = data.get("source", {}).get("repository")
    if repository != cargo["workspace"]["package"]["repository"]:
        errors.append("product.toml: repository differs from Cargo.toml")
    runtime = tomllib.loads((ROOT / "python/r2p-runtime/pyproject.toml").read_text())
    if implementation.get("python_runtime_package") != runtime["project"]["name"]:
        errors.append(
            "product.toml: Python runtime package differs from pyproject.toml"
        )
    return errors


def check_history() -> list[str]:
    product = tomllib.loads((ROOT / "product.toml").read_text())
    delivery = product.get("delivery", {})
    path = ROOT / delivery.get("history_manifest", "docs/releases/history.json")
    if not path.is_file():
        return ["product.toml: missing history manifest"]
    data = json.loads(path.read_text())
    snapshots = data.get("snapshots", [])
    errors = []
    if (
        data.get("schema_version") != 1
        or data.get("retention_count") != 2
        or delivery.get("history_count") != 2
        or len(snapshots) != 2
        or data.get("repository") != product["source"]["repository"]
    ):
        errors.append("history.json: expected two snapshots and matching identity")
    seen = set()
    for snapshot in snapshots:
        tag = snapshot.get("tag", "")
        revision = snapshot.get("revision", "")
        if (
            not tag.startswith("history/")
            or tag in seen
            or not re.fullmatch(r"[0-9a-f]{40}", revision)
        ):
            errors.append(f"history.json: invalid or duplicate snapshot {tag}")
            continue
        seen.add(tag)
        evidence = ROOT / snapshot.get("evidence", "")
        if not evidence.is_file():
            errors.append(f"history.json: missing evidence for {tag}")
        # Shallow CI checkouts may omit both history tags. Validate available
        # refs; fetch --tags before running this check to audit a full checkout.
        ref = f"refs/tags/{tag}"
        available = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", ref], cwd=ROOT, check=False
        )
        if available.returncode == 0:
            actual = subprocess.check_output(
                ["git", "rev-parse", f"{ref}^{{commit}}"], cwd=ROOT, text=True
            ).strip()
            if actual != revision:
                errors.append(f"history.json: tag {tag} differs from recorded SHA")
    return errors


def check_sdk_identity() -> list[str]:
    errors = []
    core = tomllib.loads((ROOT / "Cargo.toml").read_text())
    version = core["package"]["version"]
    expected = (
        "r2p-ffi",
        "r2p-build-config",
        "r2p-macros",
        "r2p-macros-backend",
        "r2p-introspection",
    )
    for name in expected:
        path = ROOT / "crates" / name / "Cargo.toml"
        package = tomllib.loads(path.read_text())["package"]
        if package["name"] != name or package["version"] != version:
            errors.append(f"{path.relative_to(ROOT)}: SDK name/version differs")
    for section in ("dependencies", "build-dependencies", "dev-dependencies"):
        for name, dependency in core.get(section, {}).items():
            package = (
                dependency.get("package", name)
                if isinstance(dependency, dict)
                else name
            )
            if package.startswith("pyo3"):
                errors.append(f"Cargo.toml: legacy SDK dependency {package}")
    ffi = tomllib.loads((ROOT / "crates/r2p-ffi/Cargo.toml").read_text())
    bridge = tomllib.loads((ROOT / "tools/maturin-bridge/Cargo.toml").read_text())
    if (
        bridge["package"]["name"] != "pyo3-ffi"
        or bridge["package"].get("publish") is not False
    ):
        errors.append("tools/maturin-bridge: expected private Maturin protocol package")
    if bridge["package"]["version"] != version:
        errors.append("tools/maturin-bridge: version differs from SDK")
    if bridge["package"].get("metadata") != ffi["package"].get("metadata"):
        errors.append("tools/maturin-bridge: interpreter bounds differ from r2p-ffi")
    for name in ffi["features"]:
        if name.startswith("abi3") and f"r2p-ffi/{name}" not in bridge["features"].get(
            name, []
        ):
            errors.append(f"tools/maturin-bridge: missing ABI forwarding for {name}")
    for directory in (ROOT / "examples", ROOT / "crates/r2p-ffi/examples"):
        for path in directory.glob("*/.template/maturin-bridge/Cargo.toml"):
            template = tomllib.loads(path.read_text())
            if template["package"].get("publish") is not False:
                errors.append(
                    f"{path.relative_to(ROOT)}: template adapter must be private"
                )
            if template["package"].get("metadata") != ffi["package"].get("metadata"):
                errors.append(
                    f"{path.relative_to(ROOT)}: template interpreter bounds differ"
                )
            if template["features"] != bridge["features"]:
                errors.append(
                    f"{path.relative_to(ROOT)}: template ABI forwarding differs"
                )
            hook = (path.parent.parent / "pre-script.rhai").read_text()
            move = 'file::rename(".template/maturin-bridge", "maturin-bridge");'
            delete = 'file::delete(".template");'
            if (
                move not in hook
                or delete not in hook
                or hook.index(move) > hook.index(delete)
            ):
                errors.append(
                    f"{path.relative_to(ROOT)}: adapter must be retained by template hook"
                )
    for path in (
        ROOT / "python/r2p-runtime/src/r2p_runtime/__init__.py",
        ROOT / "docs/sdk/README.md",
    ):
        if not path.is_file():
            errors.append(f"{path.relative_to(ROOT)}: missing SDK namespace entry")
    return errors


def main() -> int:
    cargo_paths = manifests()
    doc_paths = engineering_docs()
    errors = [error for path in cargo_paths for error in check_manifest(path)]
    errors.extend(error for path in doc_paths for error in check_document(path))
    errors.extend(check_includes())
    errors.extend(check_traceability())
    errors.extend(check_symlinks())
    errors.extend(check_product_identity())
    errors.extend(check_history())
    errors.extend(check_sdk_identity())
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(
        f"Repository paths OK: {len(cargo_paths)} Cargo manifests, {len(doc_paths)} engineering documents, guide includes, doctest inputs, requirement traceability, symbolic links, product/SDK identity, two history snapshots and Maturin ABI metadata."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
