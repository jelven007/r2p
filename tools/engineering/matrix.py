"""Rust test selection, independent of Nox and the running interpreter."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class RustTestOptions:
    skip_full: bool = False
    careful: bool = False
    release: bool = False
    scope: str = "all"

    @classmethod
    def parse(cls, arguments: Iterable[str]) -> RustTestOptions:
        flags = {}
        scope = "all"
        scope_seen = False
        scopes = {"all", "components", "core", "abi", "ui"}
        for argument in arguments:
            if argument in {"skip-full", "careful", "release"}:
                flags[argument.replace("-", "_")] = True
            elif argument.startswith("scope=") and argument[6:] in scopes:
                if scope_seen:
                    raise ValueError("choose only one Rust test scope")
                scope = argument[6:]
                scope_seen = True
            else:
                raise ValueError(
                    f"unknown Rust test argument: {argument!r}; expected skip-full, "
                    "careful, release, or scope=all|components|core|abi|ui"
                )
        if flags.get("skip_full") and scope == "ui":
            raise ValueError("scope=ui and skip-full cannot be combined")
        return cls(scope=scope, **flags)


def feature_sets(
    *,
    version: tuple[int, int],
    free_threaded: bool,
    cargo_target: str,
    nightly: bool,
    required: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Preserve the complete compatibility matrix; never inspect the environment."""
    full = ["full"]
    if "wasm32-wasip1" not in cargo_target:
        full.append("multiple-pymethods")
    if nightly:
        full.append("nightly")
    abi = [()]
    if not free_threaded:
        abi.append(("abi3",))
    if version >= (3, 15):
        abi.append(("abi3t",))
    return tuple(
        ",".join((*variant, *features, *required))
        for features in ((), tuple(full))
        for variant in abi
    )


def select_test_features(
    features: tuple[str, ...], options: RustTestOptions
) -> tuple[str, ...]:
    if options.scope == "components":
        return ()
    if options.scope == "core":
        required = features[0]
        return (required, ",".join(filter(None, ("macros", required))))
    selected = features
    if options.scope == "abi":
        selected = tuple(f for f in selected if {"abi3", "abi3t"} & set(f.split(",")))
    if options.scope == "ui":
        selected = tuple(f for f in selected if "full" in f.split(","))
    if options.skip_full:
        selected = tuple(f for f in selected if "full" not in f.split(","))
    return selected
