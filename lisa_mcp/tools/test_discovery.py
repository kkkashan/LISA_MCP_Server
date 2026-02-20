"""
Test discovery: scan a LISA repository for test suites and cases.

Uses AST parsing to extract @TestSuiteMetadata and @TestCaseMetadata
decorators without importing the module (so no LISA installation is needed).
"""

from __future__ import annotations

import ast
import fnmatch
import os
from pathlib import Path
from typing import Any

from lisa_mcp.models import Requirement, TestCaseInfo, TestSuiteInfo, TIER_PRIORITIES


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

def _get_decorator_kwarg(decorator: ast.Call, key: str) -> Any | None:
    """Extract a keyword argument value from a decorator call node."""
    for kw in decorator.keywords:
        if kw.arg == key:
            return _eval_ast_node(kw.value)
    return None


def _eval_ast_node(node: ast.expr) -> Any:
    """Safely evaluate simple AST constant/list/dict nodes."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [_eval_ast_node(e) for e in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_eval_ast_node(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return {_eval_ast_node(k): _eval_ast_node(v) for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.Name):
        return node.id  # Return identifier name as string
    if isinstance(node, ast.Attribute):
        return f"{_eval_ast_node(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        # e.g. simple_requirement(min_core_count=4, ...)
        func_name = _eval_ast_node(node.func)
        kwargs = {kw.arg: _eval_ast_node(kw.value) for kw in node.keywords}
        return {"__call__": func_name, **kwargs}
    return None


def _find_decorator(node: ast.ClassDef | ast.FunctionDef, name: str) -> ast.Call | None:
    """Return the first Call decorator whose name matches *name*."""
    for dec in node.decorator_list:
        if isinstance(dec, ast.Call):
            func = dec.func
            if isinstance(func, ast.Name) and func.id == name:
                return dec
            if isinstance(func, ast.Attribute) and func.attr == name:
                return dec
    return None


def _parse_requirement(req_raw: Any) -> Requirement:
    """Convert the raw AST value from simple_requirement(...) into a Requirement."""
    if not isinstance(req_raw, dict):
        return Requirement()
    kwargs = {k: v for k, v in req_raw.items() if k != "__call__"}

    def _listify(val: Any) -> list[str]:
        if val is None:
            return []
        if isinstance(val, list):
            return [str(v) for v in val]
        return [str(val)]

    return Requirement(
        min_core_count=kwargs.get("min_core_count"),
        min_memory_mb=kwargs.get("min_memory_mb"),
        min_disk_space_gb=kwargs.get("min_disk_space_gb"),
        supported_features=_listify(kwargs.get("supported_features")),
        unsupported_os=_listify(kwargs.get("unsupported_os")),
        supported_platform_type=_listify(kwargs.get("supported_platform_type")),
        environment_status=str(kwargs["environment_status"])
        if kwargs.get("environment_status")
        else None,
    )


# ---------------------------------------------------------------------------
# File-level parser
# ---------------------------------------------------------------------------

def _parse_file(file_path: Path) -> list[TestSuiteInfo]:
    """Parse a single Python file and return any test suites found."""
    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return []

    suites: list[TestSuiteInfo] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        suite_dec = _find_decorator(node, "TestSuiteMetadata")
        if suite_dec is None:
            continue

        area = _get_decorator_kwarg(suite_dec, "area") or ""
        category = _get_decorator_kwarg(suite_dec, "category") or ""
        description = _get_decorator_kwarg(suite_dec, "description") or ""
        owner = _get_decorator_kwarg(suite_dec, "owner") or ""

        suite = TestSuiteInfo(
            name=node.name,
            file_path=str(file_path),
            area=area,
            category=category,
            description=description,
            owner=owner,
        )

        # Scan methods for @TestCaseMetadata
        for item in node.body:
            if not isinstance(item, ast.FunctionDef):
                continue
            case_dec = _find_decorator(item, "TestCaseMetadata")
            if case_dec is None:
                continue

            case_desc = _get_decorator_kwarg(case_dec, "description") or ""
            priority = _get_decorator_kwarg(case_dec, "priority")
            if priority is None:
                priority = 2  # default
            timeout = _get_decorator_kwarg(case_dec, "timeout") or 3600
            use_new_env = _get_decorator_kwarg(case_dec, "use_new_environment") or False
            req_raw = _get_decorator_kwarg(case_dec, "requirement")
            requirement = _parse_requirement(req_raw)
            tags_raw = _get_decorator_kwarg(case_dec, "tags")
            tags = tags_raw if isinstance(tags_raw, list) else []

            tc = TestCaseInfo(
                name=f"{node.name}.{item.name}",
                method_name=item.name,
                suite_name=node.name,
                file_path=str(file_path),
                area=area,
                category=category,
                description=case_desc,
                priority=int(priority),
                timeout=int(timeout),
                use_new_environment=bool(use_new_env),
                requirement=requirement,
                tags=tags,
                owner=owner,
            )
            suite.test_cases.append(tc)

        suites.append(suite)

    return suites


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def discover_tests(
    lisa_path: str,
    area: str | None = None,
    priority: int | None = None,
    platform: str | None = None,
    name_pattern: str | None = None,
    tier: str | None = None,
) -> list[TestSuiteInfo]:
    """
    Walk *lisa_path* and return all discovered TestSuiteInfo objects,
    optionally filtered by area, priority, platform, name pattern, or tier.
    """
    root = Path(lisa_path)
    if not root.is_dir():
        raise ValueError(f"LISA path does not exist or is not a directory: {lisa_path}")

    # Determine priority filter from tier
    priority_filter: list[int] | None = None
    if tier and tier.upper() in TIER_PRIORITIES:
        priority_filter = TIER_PRIORITIES[tier.upper()]
    elif priority is not None:
        priority_filter = [priority]

    all_suites: list[TestSuiteInfo] = []

    for py_file in root.rglob("*.py"):
        # Skip venv, build directories, etc.
        parts = py_file.parts
        if any(p in parts for p in (".venv", "venv", "__pycache__", "build", "dist", ".git")):
            continue
        suites = _parse_file(py_file)
        all_suites.extend(suites)

    # Apply filters
    filtered: list[TestSuiteInfo] = []
    for suite in all_suites:
        if area and suite.area.lower() != area.lower():
            continue

        matching_cases = suite.test_cases

        if priority_filter is not None:
            matching_cases = [c for c in matching_cases if c.priority in priority_filter]

        if platform:
            matching_cases = [
                c
                for c in matching_cases
                if not c.requirement.supported_platform_type
                or any(
                    p.lower() == platform.lower()
                    for p in c.requirement.supported_platform_type
                )
            ]

        if name_pattern:
            matching_cases = [
                c
                for c in matching_cases
                if fnmatch.fnmatch(c.name.lower(), name_pattern.lower())
                or name_pattern.lower() in c.name.lower()
                or name_pattern.lower() in c.description.lower()
            ]

        if priority_filter is not None or platform or name_pattern:
            if not matching_cases and (priority_filter is not None or platform or name_pattern):
                continue
            suite = suite.model_copy(update={"test_cases": matching_cases})

        filtered.append(suite)

    return filtered


def list_areas(lisa_path: str) -> list[str]:
    """Return all unique test area names in the LISA repository."""
    suites = discover_tests(lisa_path)
    return sorted({s.area for s in suites if s.area})


def get_test_details(lisa_path: str, test_name: str) -> TestCaseInfo | None:
    """Find and return a specific test case by full name (SuiteName.method_name)."""
    suites = discover_tests(lisa_path)
    for suite in suites:
        for tc in suite.test_cases:
            if tc.name.lower() == test_name.lower() or tc.method_name.lower() == test_name.lower():
                return tc
    return None
