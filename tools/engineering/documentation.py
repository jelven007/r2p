"""Documentation command policy and local Netlify routing."""

from __future__ import annotations

from contextlib import ExitStack
from glob import glob
from pathlib import Path


def rustdoc_arguments(
    arguments: list[str], existing_flags: str, *, nightly: bool, internal: bool
) -> tuple[list[str], str]:
    flags = ["-Dwarnings"]
    toolchain = []
    cargo = []
    nightly = nightly or "nightly" in arguments
    internal = internal or "internal" in arguments
    if "open" in arguments:
        cargo.append("--open")
    if nightly:
        flags.append("--cfg docsrs")
        toolchain.append("+nightly")
        cargo.extend(["-Z", "unstable-options", "-Z", "rustdoc-scrape-examples"])
    if internal:
        flags.extend(
            [
                "--Z unstable-options",
                "--document-hidden-items",
                "--html-after-content",
                "infrastructure/netlify/internal_banner.html",
            ]
        )
        cargo.append("--document-private-items")
    else:
        cargo.extend(["--exclude=r2p-macros", "--exclude=r2p-macros-backend"])
    flags.append(existing_flags)
    return [
        *toolchain,
        "doc",
        "--lib",
        "--no-default-features",
        "--features=full",
        "--no-deps",
        "--workspace",
        *cargo,
    ], " ".join(flags)


def url_path(file_path: str) -> str:
    if file_path.endswith("index.html"):
        return file_path[: -len("index.html")]
    if file_path.endswith(".html"):
        return file_path[: -len(".html")]
    return file_path


def url_and_file_paths(url: str, file_path: str) -> tuple[str, ...]:
    return (url,) if url == file_path else (url, file_path)


def build_redirects(
    directory: Path, *, preview: bool, version: str | None, site_url: str
) -> None:
    site_url = site_url.rstrip("/")
    with ExitStack() as stack:
        redirects = stack.enter_context((directory / "_redirects").open("w"))
        headers = stack.enter_context((directory / "_headers").open("w"))

        def canonical(folder: Path) -> None:
            for file in glob(f"{folder}/**", recursive=True):
                file_path = "/" + file.removeprefix(str(directory) + "/")
                url = url_path(file_path)
                for path in url_and_file_paths(url, file_path):
                    if site_url:
                        headers.write(
                            f'{path}\n  Link: <{site_url}{url}>; rel="canonical"\n'
                        )

        for folder in directory.glob("v*"):
            archived_version = folder.name.removeprefix("v")
            redirects.write(f"/v{archived_version}/doc/* /main/doc/:splat 302\n")
            if archived_version != version:
                headers.write(f"/v{archived_version}/*\n  X-Robots-Tag: noindex\n")
            else:
                canonical(folder)
        canonical(directory / "main")
        headers.write("/internal/*\n  X-Robots-Tag: noindex\n")
        current_exists = (directory / f"v{version}").is_dir()
        if version is not None and current_exists:
            redirects.write(f"/latest/* /v{version}/:splat 302\n")
        else:
            redirects.write("/latest/* /main/:splat 302\n")
        redirects.write(
            """\
/latest/building_and_distribution/* /latest/building-and-distribution/:splat 302
/latest/building_and_distribution/multiple_python_versions/* /latest/building-and-distribution/multiple-python-versions:splat 302
/latest/function/error_handling/* /latest/function/error-handling/:splat 302
/latest/getting_started/* /latest/getting-started/:splat 302
/latest/python_from_rust/* /latest/python-from-rust/:splat 302
/latest/python_typing_hints/* /latest/python-typing-hints/:splat 302
/latest/trait_bounds/* /latest/trait-bounds/:splat 302
"""
        )
        redirects.write(
            "/ /main/ 302\n"
            if preview or not current_exists
            else f"/ /v{version}/ 302\n"
        )
        redirects.write("/main/doc /main/doc/r2p")
