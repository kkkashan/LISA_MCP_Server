"""
Runbook builder and validator.
Builds LISA runbook YAML programmatically and validates existing runbooks.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from lisa_mcp.models import TIER_PRIORITIES


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

VALID_PLATFORM_TYPES = {"azure", "hyperv", "ready", "qemu", "baremetal"}
VALID_CATEGORIES = {"functional", "performance", "stress", "community"}
VALID_NOTIFIER_TYPES = {"console", "html", "junit"}
VALID_SELECT_ACTIONS = {"include", "exclude", "force-include", "force-exclude"}


def validate_runbook(runbook_path: str) -> dict[str, Any]:
    """
    Parse and validate a LISA runbook YAML file.

    Returns a dict with:
        valid (bool): True if no critical errors
        errors (list[str]): Critical problems
        warnings (list[str]): Non-blocking issues
        summary (dict): Parsed high-level summary
    """
    path = Path(runbook_path)
    errors: list[str] = []
    warnings: list[str] = []

    if not path.exists():
        return {"valid": False, "errors": [f"File not found: {runbook_path}"], "warnings": [], "summary": {}}

    try:
        with path.open() as fh:
            doc = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        return {"valid": False, "errors": [f"YAML parse error: {exc}"], "warnings": [], "summary": {}}

    if not isinstance(doc, dict):
        return {"valid": False, "errors": ["Runbook must be a YAML mapping at the top level."], "warnings": [], "summary": {}}

    # Required fields
    if "name" not in doc:
        errors.append("Missing required field: 'name'")

    # Platform validation
    platforms = doc.get("platform", [])
    if not platforms:
        warnings.append("No platform defined — LISA will use the default local platform.")
    else:
        for plat in platforms:
            ptype = plat.get("type", "")
            if ptype not in VALID_PLATFORM_TYPES:
                warnings.append(f"Unknown platform type '{ptype}'. Known: {VALID_PLATFORM_TYPES}")

    # Test criteria
    testcases = doc.get("testcase", [])
    for tc in testcases:
        action = tc.get("select_action", "include")
        if action not in VALID_SELECT_ACTIONS:
            errors.append(f"Invalid select_action '{action}'. Valid: {VALID_SELECT_ACTIONS}")
        retry = tc.get("retry", 0)
        if not isinstance(retry, int) or retry < 0:
            errors.append(f"'retry' must be a non-negative integer, got: {retry!r}")

    # Variable resolution (warn on missing $(var) patterns)
    _check_variable_refs(doc, doc.get("variable", []), warnings)

    # Build summary
    summary = {
        "name": doc.get("name"),
        "concurrency": doc.get("concurrency", 1),
        "platform_types": [p.get("type") for p in platforms],
        "test_criteria_count": len(testcases),
        "variable_count": len(doc.get("variable", [])),
        "notifiers": [n.get("type") for n in doc.get("notifier", [])],
        "import_builtin_tests": doc.get("import_builtin_tests", True),
    }

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "summary": summary,
    }


def _check_variable_refs(
    node: Any, defined_vars: list[dict], warnings: list[str], _seen: set[str] | None = None
) -> None:
    """Recursively check that $(var) references have a corresponding definition."""
    if _seen is None:
        _seen = set()
    defined_names = {v["name"] for v in defined_vars if isinstance(v, dict) and "name" in v}
    # Collect all $(ref) patterns in string values
    import re

    pattern = re.compile(r"\$\((\w+)\)")

    def _walk(n: Any) -> None:
        if isinstance(n, str):
            for match in pattern.finditer(n):
                ref = match.group(1)
                if ref not in defined_names and ref not in _seen:
                    _seen.add(ref)
                    warnings.append(
                        f"Variable '$(${ref})' referenced but not defined in 'variable:' block. "
                        "It must be passed via -v on the CLI."
                    )
        elif isinstance(n, dict):
            for v in n.values():
                _walk(v)
        elif isinstance(n, list):
            for item in n:
                _walk(item)

    _walk(node)


# ---------------------------------------------------------------------------
# Runbook file I/O
# ---------------------------------------------------------------------------

def write_runbook(yaml_content: str, output_path: str) -> str:
    """Write runbook YAML to *output_path*, creating parent dirs if needed."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml_content, encoding="utf-8")
    return str(p.resolve())


def read_runbook(runbook_path: str) -> dict[str, Any]:
    """Parse and return a runbook YAML file as a Python dict."""
    with open(runbook_path) as fh:
        return yaml.safe_load(fh) or {}


def add_test_to_runbook(runbook_path: str, test_name: str, select_action: str = "include") -> str:
    """
    Add (or exclude) a test case to an existing runbook file in-place.
    Returns the updated YAML string.
    """
    doc = read_runbook(runbook_path)
    criteria_list = doc.setdefault("testcase", [])
    criteria_list.append({"criteria": {"name": test_name}, "select_action": select_action})
    yaml_str = yaml.dump(doc, default_flow_style=False, sort_keys=False)
    write_runbook(yaml_str, runbook_path)
    return yaml_str


def build_tier_runbook(
    tier: str,
    platform_type: str = "azure",
    output_path: str | None = None,
    extra_variables: dict[str, str] | None = None,
    image: str = "ubuntu focal 20.04-lts latest",
) -> str:
    """
    Convenience function: build a standard tier runbook.
    Returns the YAML string (and writes to disk if output_path given).
    """
    from lisa_mcp.tools.test_generator import generate_runbook_yaml

    yaml_str = generate_runbook_yaml(
        name=f"LISA {tier} Run",
        platform_type=platform_type,
        tier=tier,
        variables=extra_variables,
        notifiers=["html", "junit"],
        image=image,
    )
    if output_path:
        write_runbook(yaml_str, output_path)
    return yaml_str
