"""Generate a consumer project with explicit, consistent SDK dependency sources."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent


def examples(root: Path = ROOT) -> dict[str, Path]:
    paths = [
        *root.glob("examples/*/.template"),
        *root.glob("crates/r2p-ffi/examples/*/.template"),
    ]
    return {path.parent.name: path.parent for path in sorted(paths)}


def source_configuration(
    mode: str,
    *,
    revision: str | None = None,
    repository: str | None = None,
    checkout: Path | None = None,
    version: str | None = None,
    root: Path = ROOT,
) -> dict:
    product = tomllib.loads((root / "product.toml").read_text())
    sdk_version = tomllib.loads((root / "Cargo.toml").read_text())["package"]["version"]
    if mode == "git":
        if checkout or version:
            raise ValueError("git mode accepts --revision and --repository only")
        revision = revision or product["delivery"]["verified_git_revision"]
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ValueError(
                "Git source requires a full, immutable 40-character commit SHA"
            )
        return {
            "mode": mode,
            "repository": repository or product["source"]["repository"],
            "revision": revision,
            "version": sdk_version,
        }
    if mode == "path":
        if revision or repository or version or not checkout:
            raise ValueError(
                "path mode requires --checkout and no Git/registry options"
            )
        checkout = checkout.resolve()
        sdk = tomllib.loads((checkout / "Cargo.toml").read_text())["package"]
        ffi = tomllib.loads((checkout / "crates/r2p-ffi/Cargo.toml").read_text())[
            "package"
        ]
        if (
            sdk["name"] != "r2p"
            or ffi["name"] != "r2p-ffi"
            or sdk["version"] != ffi["version"]
        ):
            raise ValueError("checkout must contain a consistent r2p SDK and FFI")
        return {"mode": mode, "checkout": str(checkout), "version": sdk["version"]}
    if mode == "registry":
        if revision or repository or checkout:
            raise ValueError("registry mode accepts --version only")
        if (
            not version
            or version not in product["delivery"]["verified_registry_versions"]
        ):
            raise ValueError(
                "registry version has no recorded publication/install verification"
            )
        return {"mode": mode, "version": version}
    raise ValueError(f"unknown source mode: {mode}")


def dependency_fields(package: str, source: dict) -> dict:
    if source["mode"] == "git":
        return {"git": source["repository"], "rev": source["revision"]}
    if source["mode"] == "path":
        path = Path(source["checkout"])
        if package == "r2p-ffi":
            path /= "crates/r2p-ffi"
        return {"path": path.as_posix()}
    return {"version": f"={source['version']}"}


def rewrite_dependencies(manifest: str, source: dict) -> str:
    parsed = tomllib.loads(manifest)
    for section in ("dependencies", "build-dependencies", "dev-dependencies"):
        section_pattern = rf"(?ms)(^\[{re.escape(section)}\]\s*\n)(.*?)(?=^\[|\Z)"
        match = re.search(section_pattern, manifest)
        if match is None:
            continue
        body = match[2]
        for package, value in parsed.get(section, {}).items():
            if package not in {"r2p", "r2p-ffi"}:
                continue
            fields = dependency_fields(package, source)
            if isinstance(value, dict):
                fields.update(
                    (key, item)
                    for key, item in value.items()
                    if key not in {"path", "git", "rev", "branch", "tag", "version"}
                )
            literal = ", ".join(
                f"{key} = {json.dumps(value)}" for key, value in fields.items()
            )
            replacement = f"{package} = {{ {literal} }}"
            body = re.sub(
                rf"(?m)^{re.escape(package)}\s*=.*$",
                lambda _, replacement=replacement: replacement,
                body,
            )
        manifest = manifest[: match.start(2)] + body + manifest[match.end(2) :]
    return manifest


def generate(
    example: str,
    destination: Path,
    *,
    name: str,
    authors: str,
    source: dict,
    root: Path = ROOT,
) -> Path:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", name):
        raise ValueError(
            "project name must start with a letter and use letters, digits, - or _"
        )
    template = examples(root)[example]
    destination = destination.resolve()
    if destination.exists():
        raise ValueError(
            "destination must not exist; generated projects are never overwritten"
        )
    if destination.is_relative_to(template):
        raise ValueError("destination must be outside the template directory")
    # Honor repository ignores, including Meson's staged SDK/dependency trees.
    paths = (
        subprocess.check_output(
            [
                "git",
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
                "--",
                str(template.relative_to(root)),
            ],
            cwd=root,
        )
        .decode()
        .split("\0")
    )
    destination.mkdir(parents=True)
    for relative in sorted(set(filter(None, paths))):
        path = root / relative
        local = path.relative_to(template)
        if ".template" in local.parts or path.name in {
            "Cargo.lock",
            "cargo-generate.toml",
            ".genignore",
        }:
            continue
        if not path.is_file():
            continue
        target = destination / local
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    replacements = {
        "authors": json.dumps(authors, ensure_ascii=False)[1:-1],
        "project-name": name,
        "R2P_VERSION": source["version"],
    }
    for path in (template / ".template").rglob("*"):
        if not path.is_file() or path.name == "pre-script.rhai":
            continue
        target = destination / path.relative_to(template / ".template")
        content = path.read_text()
        for key, value in replacements.items():
            content = content.replace("{{" + key + "}}", value)
        if "{{" in content:
            raise ValueError(f"unexpanded template variable in {path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    for path in destination.rglob("Cargo.toml"):
        path.write_text(rewrite_dependencies(path.read_text(), source))
    manifest = destination / "Cargo.toml"
    if "workspace" not in tomllib.loads(manifest.read_text()):
        with manifest.open("a") as file:
            file.write("\n[workspace]\n")
    # Distribute real license files even when the template used parent links.
    for license_name in ("LICENSE-MIT", "LICENSE-APACHE"):
        target = destination / license_name
        if target.is_symlink():
            target.unlink()
        shutil.copyfile(root / license_name, target)
    record = {
        "schema_version": 1,
        "example": example,
        "source": source,
        "generator_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
    }
    (destination / "r2p-source.json").write_text(json.dumps(record, indent=2) + "\n")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--example", choices=examples(), default="maturin-starter")
    parser.add_argument("--name", help="distribution and Cargo package name")
    parser.add_argument("--authors", default="r2p consumer")
    parser.add_argument("--source", choices=("git", "path", "registry"), default="git")
    parser.add_argument("--revision")
    parser.add_argument("--repository")
    parser.add_argument("--checkout", type=Path)
    parser.add_argument("--version")
    args = parser.parse_args()
    try:
        source = source_configuration(
            args.source,
            revision=args.revision,
            repository=args.repository,
            checkout=args.checkout,
            version=args.version,
        )
        destination = generate(
            args.example,
            args.destination,
            name=args.name or args.destination.name,
            authors=args.authors,
            source=source,
        )
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f"Generated {destination} using {source['mode']} source")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
