"""
Result parser: read LISA test output from JUnit XML, log files, or stdout.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from lisa_mcp.models import TestResult, TestRunSummary


# ---------------------------------------------------------------------------
# JUnit XML parsing (produced by the 'junit' notifier)
# ---------------------------------------------------------------------------

def parse_junit_xml(xml_path: str) -> TestRunSummary:
    """Parse a JUnit XML file produced by LISA's junit notifier."""
    try:
        from junitparser import JUnitXml, Failure, Error, Skipped
    except ImportError:
        raise ImportError("Install 'junitparser' to parse JUnit XML: pip install junitparser")

    path = Path(xml_path)
    if not path.exists():
        raise FileNotFoundError(f"JUnit XML not found: {xml_path}")

    xml = JUnitXml.fromfile(str(path))

    results: list[TestResult] = []
    total = passed = failed = skipped = errors = 0
    total_time = 0.0

    for suite in xml:
        for case in suite:
            total += 1
            name = case.name or ""
            suite_name = suite.name or ""
            duration = float(case.time or 0)
            total_time += duration

            if isinstance(case.result, Failure):
                failed += 1
                status = "failed"
                message = case.result.message or ""
                stack = case.result.text or ""
            elif isinstance(case.result, Error):
                errors += 1
                status = "error"
                message = case.result.message or ""
                stack = case.result.text or ""
            elif isinstance(case.result, Skipped):
                skipped += 1
                status = "skipped"
                message = case.result.message or ""
                stack = ""
            else:
                passed += 1
                status = "passed"
                message = ""
                stack = ""

            results.append(
                TestResult(
                    name=name,
                    status=status,
                    duration_seconds=duration,
                    message=message,
                    stack_trace=stack,
                    suite_name=suite_name,
                )
            )

    return TestRunSummary(
        total=total,
        passed=passed,
        failed=failed,
        skipped=skipped,
        errors=errors,
        duration_seconds=total_time,
        results=results,
    )


# ---------------------------------------------------------------------------
# Console log parsing (fallback)
# ---------------------------------------------------------------------------

# Patterns observed in LISA console output
_PASS_RE = re.compile(r"\[PASS\]\s+(.+?)(?:\s+\((\d+(?:\.\d+)?)s\))?$", re.IGNORECASE)
_FAIL_RE = re.compile(r"\[FAIL\]\s+(.+?)(?:\s+\((\d+(?:\.\d+)?)s\))?$", re.IGNORECASE)
_SKIP_RE = re.compile(r"\[SKIP\]\s+(.+?)(?:\s+\((\d+(?:\.\d+)?)s\))?$", re.IGNORECASE)
_SUMMARY_RE = re.compile(
    r"total:\s*(\d+).*?pass(?:ed)?:\s*(\d+).*?fail(?:ed)?:\s*(\d+).*?skip(?:ped)?:\s*(\d+)",
    re.IGNORECASE | re.DOTALL,
)


def parse_console_output(output: str) -> TestRunSummary:
    """
    Best-effort parse of LISA console output (stdout/stderr from a run).
    Falls back gracefully when patterns are not found.
    """
    results: list[TestResult] = []

    for line in output.splitlines():
        line = line.strip()
        for pattern, status in [(_PASS_RE, "passed"), (_FAIL_RE, "failed"), (_SKIP_RE, "skipped")]:
            m = pattern.match(line)
            if m:
                name = m.group(1).strip()
                duration = float(m.group(2)) if m.group(2) else 0.0
                results.append(TestResult(name=name, status=status, duration_seconds=duration))
                break

    passed = sum(1 for r in results if r.status == "passed")
    failed = sum(1 for r in results if r.status == "failed")
    skipped = sum(1 for r in results if r.status == "skipped")
    total = len(results)

    # Try to find a summary line if no results were parsed
    if not results:
        m = _SUMMARY_RE.search(output)
        if m:
            total = int(m.group(1))
            passed = int(m.group(2))
            failed = int(m.group(3))
            skipped = int(m.group(4))

    return TestRunSummary(
        total=total,
        passed=passed,
        failed=failed,
        skipped=skipped,
        errors=0,
        duration_seconds=sum(r.duration_seconds for r in results),
        results=results,
    )


# ---------------------------------------------------------------------------
# Auto-detect and parse
# ---------------------------------------------------------------------------

def parse_results(source: str) -> TestRunSummary:
    """
    Detect whether *source* is a JUnit XML file path or raw console output
    and parse accordingly.
    """
    p = Path(source)
    if p.exists() and p.suffix.lower() in {".xml", ".junit"}:
        return parse_junit_xml(source)
    # Treat as raw output string
    return parse_console_output(source)


def summarize(summary: TestRunSummary) -> str:
    """Return a one-line human-readable summary string."""
    pct = (summary.passed / summary.total * 100) if summary.total else 0
    return (
        f"Total: {summary.total} | "
        f"Passed: {summary.passed} ({pct:.1f}%) | "
        f"Failed: {summary.failed} | "
        f"Skipped: {summary.skipped} | "
        f"Errors: {summary.errors} | "
        f"Duration: {summary.duration_seconds:.1f}s"
    )
