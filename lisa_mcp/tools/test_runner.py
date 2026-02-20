"""
Test runner: invoke the LISA CLI and stream/capture output.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterator


def _build_lisa_command(
    lisa_path: str,
    runbook_path: str,
    variables: dict[str, str] | None = None,
    dry_run: bool = False,
) -> list[str]:
    """Construct the lisa CLI command list."""
    # Prefer `lisa` on PATH; fallback to `python -m lisa`
    lisa_exe = shutil.which("lisa")
    if lisa_exe:
        cmd = [lisa_exe]
    else:
        cmd = [sys.executable, "-m", "lisa"]

    cmd += ["-r", str(Path(runbook_path).resolve())]

    for name, value in (variables or {}).items():
        cmd += ["-v", f"{name}:{value}"]

    if dry_run:
        # LISA doesn't have a --dry-run flag but we can pass an env override
        # to prevent actual VM provisioning in some setups; document this.
        cmd += ["-v", "dry_run:true"]

    return cmd


def run_tests(
    lisa_path: str,
    runbook_path: str,
    variables: dict[str, str] | None = None,
    dry_run: bool = False,
    timeout_seconds: int = 7200,
    working_dir: str | None = None,
) -> dict:
    """
    Run LISA tests and return a result dict with stdout, stderr, returncode.

    Parameters
    ----------
    lisa_path      : Root of the cloned LISA repository.
    runbook_path   : Path to the runbook YAML file.
    variables      : Additional -v name:value overrides.
    dry_run        : If True, passes dry_run:true variable (informational).
    timeout_seconds: Hard timeout for the subprocess.
    working_dir    : cwd for subprocess; defaults to lisa_path.
    """
    cmd = _build_lisa_command(lisa_path, runbook_path, variables, dry_run)
    cwd = working_dir or lisa_path

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=cwd,
        )
        return {
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "command": " ".join(cmd),
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Timed out after {timeout_seconds}s",
            "command": " ".join(cmd),
        }
    except FileNotFoundError:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": (
                "lisa executable not found. Install LISA with: "
                "pip install lisa  (or clone the repo and run: pip install -e .)"
            ),
            "command": " ".join(cmd),
        }


def check_lisa_installed() -> dict:
    """Check whether the `lisa` CLI is available and return version info."""
    lisa_exe = shutil.which("lisa")
    if lisa_exe:
        try:
            result = subprocess.run(
                [lisa_exe, "--version"], capture_output=True, text=True, timeout=10
            )
            return {
                "installed": True,
                "path": lisa_exe,
                "version_output": result.stdout.strip() or result.stderr.strip(),
            }
        except Exception as exc:
            return {"installed": True, "path": lisa_exe, "version_output": str(exc)}
    # Try python -m lisa
    try:
        result = subprocess.run(
            [sys.executable, "-m", "lisa", "--version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return {
                "installed": True,
                "path": f"{sys.executable} -m lisa",
                "version_output": result.stdout.strip(),
            }
    except Exception:
        pass
    return {"installed": False, "path": None, "version_output": ""}
