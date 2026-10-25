"""Exercise actual GIL states and legacy imports with explicit local interpreters."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from tools.engineering.environment import PYTHON_PROBE, environment_snapshot
from tools.evidence import gil_state

LEGACY_MODULE = """\
#include <Python.h>
static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT, "legacy_gil", NULL, -1, NULL
};
PyMODINIT_FUNC PyInit_legacy_gil(void) { return PyModule_Create(&module); }
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gil-python", type=Path, required=True)
    parser.add_argument("--ft-python", type=Path, required=True)
    parser.add_argument("--legacy-python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    ft_python = args.ft_python.resolve()
    source = output / "legacy_gil.c"
    source.write_text(LEGACY_MODULE)
    suffix = subprocess.check_output(
        [
            str(ft_python),
            "-c",
            "import sysconfig; print(sysconfig.get_config_var('EXT_SUFFIX'))",
        ],
        text=True,
    ).strip()
    # This verifier intentionally targets the current macOS host. The fixture
    # predates Py_mod_gil and exercises CPython's automatic GIL re-enabling.
    compilation = subprocess.run(
        [
            "clang",
            "-bundle",
            "-undefined",
            "dynamic_lookup",
            "-I",
            str(ft_python.parent.parent / "include/python3.14t"),
            str(source),
            "-o",
            str(output / ("legacy_gil" + suffix)),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    (output / "compile.log").write_text(compilation.stdout + compilation.stderr)
    cases = {}
    for label, executable, gil, modules, expected in (
        ("gil", args.gil_python, None, [], "enabled"),
        ("ft-off", ft_python, "0", [], "disabled"),
        ("ft-on", ft_python, "1", [], "enabled"),
        ("ft-auto-import", ft_python, None, ["legacy_gil"], "enabled"),
        ("legacy", args.legacy_python, None, [], "unrecorded"),
        (
            "import-failure",
            ft_python,
            "0",
            ["r2p_missing_module_for_probe"],
            "disabled",
        ),
    ):
        env = os.environ.copy()
        env.pop("PYTHON_GIL", None)
        if gil is not None:
            env["PYTHON_GIL"] = gil
        env["PYTHONPATH"] = str(output)
        process = subprocess.run(
            [str(executable.resolve()), "-c", PYTHON_PROBE, json.dumps(modules)],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        (output / f"{label}.log").write_text(process.stdout + process.stderr)
        snapshot = json.loads(process.stdout)
        assert gil_state(snapshot) == expected, (label, snapshot)
        cases[label] = snapshot
    assert cases["ft-auto-import"]["gil_enabled"] is False
    assert cases["ft-auto-import"]["modules"][0]["gil_after"] is True
    assert cases["import-failure"]["modules"][0]["result"] == "failure"
    assert cases["ft-off"]["free_threaded"] is cases["ft-on"]["free_threaded"] is True
    venv = output / "install-venv"
    subprocess.run(
        ["uv", "venv", str(venv), "--python", str(args.gil_python.resolve())],
        check=True,
    )
    install = subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(venv / "bin/python"),
            "--no-index",
            "r2p-missing-package-for-evidence",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    (output / "install-failure.log").write_text(install.stdout + install.stderr)
    assert install.returncode != 0
    report = environment_snapshot(
        root, sys.executable, str(args.ft_python.resolve()), []
    )
    report.update(
        cases=cases,
        install_failure={"exit_code": install.returncode, "sdk_steps": []},
        result="success",
        exit_code=0,
        finished_at=datetime.now(timezone.utc).isoformat(),
        limitations="macOS local environment probes and legacy C fixture; not SDK cross-platform behavior",
    )
    (output / "evidence.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Observed GIL and failure cases passed: {output / 'evidence.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
