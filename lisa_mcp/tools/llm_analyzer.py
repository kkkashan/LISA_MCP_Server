"""
LLM analyzer — use Claude (claude-sonnet-4-6) with tool_use to produce
structured failure analyses and run-level summaries.

Design
------
- All Anthropic API calls use tool_choice to force structured JSON output.
- The API key is always passed explicitly — never read from the environment.
- Per-failure analysis is bounded by MAX_CHARS_PER_TEST from log_collector.
- Run-level analysis sends a compact digest (not raw logs) so token usage
  scales with failure count, not log volume.
"""

from __future__ import annotations

from typing import Any

import anthropic

from lisa_mcp.models import (
    FailureAnalysis,
    FailureSeverity,
    RootCauseCategory,
    RunAnalysisSummary,
)
from lisa_mcp.tools.log_collector import TestLogContext

# ---------------------------------------------------------------------------
# Tool schemas — passed as tools= to the Anthropic API.
# Field names mirror the Pydantic models exactly.
# ---------------------------------------------------------------------------

_FAILURE_TOOL: dict[str, Any] = {
    "name": "report_failure_analysis",
    "description": (
        "Report the structured root-cause analysis for a single LISA test failure. "
        "Call this tool exactly once with all required fields populated."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "test_name": {"type": "string"},
            "root_cause_category": {
                "type": "string",
                "enum": [c.value for c in RootCauseCategory],
                "description": "Primary failure category.",
            },
            "root_cause_description": {
                "type": "string",
                "description": (
                    "2-4 sentence technical explanation of the failure root cause. "
                    "Be specific about which component, command, or configuration failed."
                ),
            },
            "recommended_fix": {
                "type": "string",
                "description": (
                    "Concrete, actionable recommended fix or next debugging step. "
                    "Reference specific commands, files, or settings where possible."
                ),
            },
            "severity": {
                "type": "string",
                "enum": [s.value for s in FailureSeverity],
                "description": (
                    "critical=blocks release, high=major feature broken, "
                    "medium=partial impact, low=minor/informational."
                ),
            },
            "relevant_log_lines": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Up to 10 log lines most relevant to the root cause.",
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Confidence in this analysis (0.0=uncertain, 1.0=certain).",
            },
        },
        "required": [
            "test_name",
            "root_cause_category",
            "root_cause_description",
            "recommended_fix",
            "severity",
            "relevant_log_lines",
            "confidence",
        ],
    },
}

_RUN_TOOL: dict[str, Any] = {
    "name": "report_run_analysis",
    "description": (
        "Report the structured summary analysis for an entire LISA test run. "
        "Call this tool exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "overall_health": {
                "type": "string",
                "enum": ["healthy", "degraded", "critical", "unknown"],
                "description": (
                    "healthy=all P0 tests pass, degraded=some failures but system functional, "
                    "critical=blocking failures present."
                ),
            },
            "health_score": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": (
                    "Weighted pass rate: 1.0 = everything passes, 0.0 = all critical failures."
                ),
            },
            "failure_patterns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Recurring themes observed across multiple failures.",
            },
            "top_priorities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ordered list of the 3-5 most important issues to resolve first.",
            },
            "environment_issues": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Infrastructure or configuration problems (not test code bugs).",
            },
            "recommendations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific, actionable recommended actions for the team.",
            },
            "executive_summary": {
                "type": "string",
                "description": (
                    "3-5 sentence non-technical summary suitable for stakeholders. "
                    "Include overall status, key problems, and next steps."
                ),
            },
        },
        "required": [
            "overall_health",
            "health_score",
            "failure_patterns",
            "top_priorities",
            "environment_issues",
            "recommendations",
            "executive_summary",
        ],
    },
}

# System prompt injected into every API call
_SYSTEM_PROMPT = """\
You are an expert Linux kernel and systems engineer with deep experience in:
- Azure VM infrastructure, Hyper-V integration, and cloud-init
- Linux kernel bugs, driver failures, and dmesg error interpretation
- Network stack failures (SR-IOV, DPDK, TCP/IP timeouts)
- Storage failures (NVMe, virtio-blk, filesystem errors)
- Systemd service failures and kdump analysis
- CI/CD test flakiness patterns

You are analyzing results from the Microsoft LISA (Linux Integration Services Automation)
framework, which runs automated Linux quality tests on Azure and Hyper-V.

When analyzing failures:
1. Look for the ROOT CAUSE, not just the symptom
2. Distinguish between test code bugs, infrastructure issues, and genuine Linux bugs
3. Identify if failures are likely flaky (intermittent timing/network issues)
4. Provide SPECIFIC, ACTIONABLE recommendations (exact commands, file paths, settings)
5. Rate confidence honestly — if the logs are insufficient, say so"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_failure(
    test_name:       str,
    failure_message: str,
    stack_trace:     str,
    log_context:     TestLogContext | None,
    api_key:         str,
    model:           str = "claude-sonnet-4-6",
    max_tokens:      int = 1500,
) -> FailureAnalysis:
    """
    Analyze a single test failure with Claude.

    Parameters
    ----------
    test_name       : Full name e.g. "StorageTest.verify_disk_io".
    failure_message : Short error from JUnit XML or console output.
    stack_trace     : Full traceback / error output.
    log_context     : Optional TestLogContext from log_collector.
    api_key         : Anthropic API key.
    model           : Model to use (default claude-sonnet-4-6).
    max_tokens      : Max response tokens.

    Returns FailureAnalysis populated from tool_use response.
    """
    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_failure_prompt(test_name, failure_message, stack_trace, log_context)

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=_SYSTEM_PROMPT,
        tools=[_FAILURE_TOOL],
        tool_choice={"type": "tool", "name": "report_failure_analysis"},
        messages=[{"role": "user", "content": prompt}],
    )

    data = _extract_tool_input(response, "report_failure_analysis")
    return FailureAnalysis(
        test_name=data.get("test_name", test_name),
        root_cause_category=RootCauseCategory(
            data.get("root_cause_category", RootCauseCategory.UNKNOWN.value)
        ),
        root_cause_description=data.get("root_cause_description", ""),
        recommended_fix=data.get("recommended_fix", ""),
        severity=FailureSeverity(
            data.get("severity", FailureSeverity.MEDIUM.value)
        ),
        relevant_log_lines=data.get("relevant_log_lines", [])[:10],
        confidence=float(data.get("confidence", 0.5)),
    )


def analyze_run(
    failure_analyses: list[FailureAnalysis],
    total:    int,
    passed:   int,
    failed:   int,
    skipped:  int,
    api_key:  str,
    model:    str = "claude-sonnet-4-6",
    max_tokens: int = 2000,
) -> RunAnalysisSummary:
    """
    Produce a run-level summary from pre-computed per-failure analyses.

    Sends a compact digest (not raw logs), so token usage scales with
    failure count, not log volume.
    """
    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_run_prompt(failure_analyses, total, passed, failed, skipped)

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=_SYSTEM_PROMPT,
        tools=[_RUN_TOOL],
        tool_choice={"type": "tool", "name": "report_run_analysis"},
        messages=[{"role": "user", "content": prompt}],
    )

    data = _extract_tool_input(response, "report_run_analysis")
    return RunAnalysisSummary(
        overall_health=data.get("overall_health", "unknown"),
        health_score=float(data.get("health_score", 0.0)),
        failure_patterns=data.get("failure_patterns", []),
        top_priorities=data.get("top_priorities", []),
        environment_issues=data.get("environment_issues", []),
        recommendations=data.get("recommendations", []),
        executive_summary=data.get("executive_summary", ""),
    )


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_failure_prompt(
    test_name:       str,
    failure_message: str,
    stack_trace:     str,
    log_context:     TestLogContext | None,
) -> str:
    parts: list[str] = [
        f"## Failed Test: `{test_name}`",
        "",
        "### Failure Message",
        failure_message.strip() or "(no failure message)",
    ]

    if stack_trace:
        trace = stack_trace[:3_000]
        if len(stack_trace) > 3_000:
            trace += "\n... [stack trace truncated]"
        parts += ["", "### Stack Trace / Error Output", "```", trace, "```"]

    if log_context and log_context.context_snippet:
        parts += [
            "",
            f"### Test Log Context ({log_context.total_log_bytes:,} bytes total"
            + (", truncated" if log_context.truncated else "") + ")",
            "```",
            log_context.context_snippet,
            "```",
        ]

    parts += [
        "",
        "Analyze this LISA test failure. Call the `report_failure_analysis` tool "
        "with your structured analysis.",
    ]
    return "\n".join(parts)


def _build_run_prompt(
    failure_analyses: list[FailureAnalysis],
    total:   int,
    passed:  int,
    failed:  int,
    skipped: int,
) -> str:
    pass_pct = (passed / total * 100) if total else 0

    lines: list[str] = [
        "## LISA Test Run Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total  | {total} |",
        f"| Passed | {passed} ({pass_pct:.1f}%) |",
        f"| Failed | {failed} |",
        f"| Skipped | {skipped} |",
        "",
        "## Per-Failure Analysis",
        "",
    ]

    if not failure_analyses:
        lines.append("No failures recorded.")
    else:
        # Table: test name | category | severity | confidence | root cause (brief)
        lines += [
            "| Test | Category | Severity | Confidence | Root Cause Summary |",
            "|------|----------|----------|------------|-------------------|",
        ]
        for fa in sorted(failure_analyses, key=lambda x: x.severity_order):
            brief = fa.root_cause_description[:90].replace("|", "/")
            if len(fa.root_cause_description) > 90:
                brief += "…"
            lines.append(
                f"| `{fa.test_name}` | {fa.root_cause_category.value} "
                f"| **{fa.severity.value}** | {int(fa.confidence * 100)}% | {brief} |"
            )
        lines.append("")

        # Individual recommendations (brief)
        lines.append("## Individual Recommendations")
        for fa in sorted(failure_analyses, key=lambda x: x.severity_order):
            lines.append(f"- **{fa.test_name}**: {fa.recommended_fix[:120]}")

    lines += [
        "",
        "Analyze this LISA test run. Call the `report_run_analysis` tool "
        "with your structured summary.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _extract_tool_input(
    response: anthropic.types.Message,
    tool_name: str,
) -> dict[str, Any]:
    """Extract input dict from the first ToolUseBlock matching *tool_name*."""
    for block in response.content:
        if hasattr(block, "type") and block.type == "tool_use":
            if block.name == tool_name:
                return block.input  # type: ignore[return-value]
    raise ValueError(
        f"Model did not call tool '{tool_name}'. "
        f"Response content types: {[getattr(b,'type','?') for b in response.content]}"
    )
