"""
LLM analyzer — call any OpenAI-compatible API to produce structured
failure analyses and run-level summaries.

Supported providers
-------------------
1. Azure OpenAI Responses API (default)
   Endpoint: https://<resource>.openai.azure.com/openai/responses?api-version=...
   Auth:     api-key header

2. OpenAI API
   Endpoint: https://api.openai.com/v1/chat/completions
   Auth:     Authorization: Bearer <key>

3. Azure OpenAI Chat Completions API
   Endpoint: https://<resource>.openai.azure.com/openai/deployments/<model>/chat/completions?api-version=...
   Auth:     api-key header

4. Local / self-hosted (Ollama, LM Studio, Azure AI Foundry, etc.)
   Endpoint: http://localhost:11434/v1/chat/completions  (or any OpenAI-compatible URL)
   Auth:     Authorization: Bearer <key>  (or empty string if not required)

Provider is auto-detected from the endpoint URL:
  • URL contains "openai.azure.com" + path segment "responses" → Azure Responses API
  • Everything else → OpenAI-compatible Chat Completions API

Design
------
- All API calls use function/tool_choice to force structured JSON output.
- The API key is always passed explicitly — never read from the environment.
- Per-failure analysis is bounded by MAX_CHARS_PER_TEST from log_collector.
- Run-level analysis sends a compact digest so token usage scales with
  failure count, not log volume.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from lisa_mcp.models import (
    FailureAnalysis,
    FailureSeverity,
    RootCauseCategory,
    RunAnalysisSummary,
)
from lisa_mcp.tools.log_collector import TestLogContext

# ---------------------------------------------------------------------------
# Pre-configured default — Azure OpenAI Responses API
# ---------------------------------------------------------------------------

_DEFAULT_ENDPOINT = (
    "https://kkopenailearn.openai.azure.com/openai/responses"
    "?api-version=2025-04-01-preview"
)
_DEFAULT_MODEL = "gpt-4o"

# Well-known alternative endpoint templates (shown to users in list_llm_providers)
KNOWN_ENDPOINTS: dict[str, dict[str, str]] = {
    "azure_openai_responses": {
        "name": "Azure OpenAI — Responses API (default)",
        "endpoint_template": "https://<resource>.openai.azure.com/openai/responses?api-version=2025-04-01-preview",
        "auth_header": "api-key",
        "default_model": "gpt-4o",
        "notes": "Supports gpt-4o, gpt-4.1, o3, o4-mini, gpt-5, and more.",
    },
    "openai": {
        "name": "OpenAI API",
        "endpoint_template": "https://api.openai.com/v1/chat/completions",
        "auth_header": "Authorization: Bearer <key>",
        "default_model": "gpt-4o",
        "notes": "Use your OpenAI API key from platform.openai.com",
    },
    "azure_openai_chat": {
        "name": "Azure OpenAI — Chat Completions API",
        "endpoint_template": "https://<resource>.openai.azure.com/openai/deployments/<deployment>/chat/completions?api-version=2024-02-01",
        "auth_header": "api-key",
        "default_model": "<deployment-name>",
        "notes": "Classic Azure OpenAI format. Replace <resource> and <deployment>.",
    },
    "ollama": {
        "name": "Ollama (local)",
        "endpoint_template": "http://localhost:11434/v1/chat/completions",
        "auth_header": "Authorization: Bearer ollama",
        "default_model": "llama3",
        "notes": "Run `ollama serve` first. Any model pulled with `ollama pull` works.",
    },
    "lm_studio": {
        "name": "LM Studio (local)",
        "endpoint_template": "http://localhost:1234/v1/chat/completions",
        "auth_header": "Authorization: Bearer lm-studio",
        "default_model": "<loaded-model-name>",
        "notes": "Enable the Local Server in LM Studio settings.",
    },
    "azure_ai_foundry": {
        "name": "Azure AI Foundry / GitHub Models",
        "endpoint_template": "https://models.inference.ai.azure.com/chat/completions",
        "auth_header": "Authorization: Bearer <github-token-or-azure-key>",
        "default_model": "gpt-4o",
        "notes": "Use a GitHub Personal Access Token or Azure AI Foundry key.",
    },
}


# ---------------------------------------------------------------------------
# Tool schemas — common to both API formats
# ---------------------------------------------------------------------------

_FAILURE_TOOL_PARAMS: dict[str, Any] = {
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
            "description": "Confidence in this analysis (0.0=uncertain, 1.0=certain).",
        },
    },
    "required": [
        "test_name", "root_cause_category", "root_cause_description",
        "recommended_fix", "severity", "relevant_log_lines", "confidence",
    ],
    "additionalProperties": False,
}

_RUN_TOOL_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "overall_health": {
            "type": "string",
            "enum": ["healthy", "degraded", "critical", "unknown"],
        },
        "health_score": {"type": "number"},
        "failure_patterns": {"type": "array", "items": {"type": "string"}},
        "top_priorities": {"type": "array", "items": {"type": "string"}},
        "environment_issues": {"type": "array", "items": {"type": "string"}},
        "recommendations": {"type": "array", "items": {"type": "string"}},
        "executive_summary": {"type": "string"},
    },
    "required": [
        "overall_health", "health_score", "failure_patterns", "top_priorities",
        "environment_issues", "recommendations", "executive_summary",
    ],
    "additionalProperties": False,
}

# Azure Responses API tool format
_FAILURE_TOOL_RESPONSES: dict[str, Any] = {
    "type": "function",
    "name": "report_failure_analysis",
    "description": (
        "Report the structured root-cause analysis for a single LISA test failure. "
        "Call this tool exactly once with all required fields populated."
    ),
    "strict": True,
    "parameters": _FAILURE_TOOL_PARAMS,
}

_RUN_TOOL_RESPONSES: dict[str, Any] = {
    "type": "function",
    "name": "report_run_analysis",
    "description": (
        "Report the structured summary analysis for an entire LISA test run. "
        "Call this tool exactly once."
    ),
    "strict": True,
    "parameters": _RUN_TOOL_PARAMS,
}

# OpenAI Chat Completions tool format
_FAILURE_TOOL_CHAT: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "report_failure_analysis",
        "description": (
            "Report the structured root-cause analysis for a single LISA test failure. "
            "Call this tool exactly once with all required fields populated."
        ),
        "strict": True,
        "parameters": _FAILURE_TOOL_PARAMS,
    },
}

_RUN_TOOL_CHAT: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "report_run_analysis",
        "description": (
            "Report the structured summary analysis for an entire LISA test run. "
            "Call this tool exactly once."
        ),
        "strict": True,
        "parameters": _RUN_TOOL_PARAMS,
    },
}

# System prompt — identical for all providers
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
# Provider detection
# ---------------------------------------------------------------------------

def _is_azure_responses_api(endpoint: str) -> bool:
    """Return True if the endpoint is the Azure OpenAI Responses API format."""
    return "openai.azure.com" in endpoint and "/responses" in endpoint.split("?")[0]


def _build_auth_headers(api_key: str, endpoint: str) -> dict[str, str]:
    """Return the correct auth headers for the given endpoint."""
    if "openai.azure.com" in endpoint:
        return {"api-key": api_key, "Content-Type": "application/json"}
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Low-level HTTP callers
# ---------------------------------------------------------------------------

def _call_responses_api(
    *,
    instructions: str,
    input_text: str,
    tools: list[dict[str, Any]],
    tool_choice: dict[str, str],
    api_key: str,
    model: str,
    endpoint: str,
    timeout: int = 120,
) -> dict[str, Any]:
    """Call the Azure OpenAI Responses API."""
    payload = {
        "model": model,
        "instructions": instructions,
        "input": input_text,
        "tools": tools,
        "tool_choice": tool_choice,
    }
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(endpoint, json=payload, headers=_build_auth_headers(api_key, endpoint))
        resp.raise_for_status()
        return resp.json()


def _call_chat_completions_api(
    *,
    system_prompt: str,
    user_message: str,
    tools: list[dict[str, Any]],
    tool_name: str,
    api_key: str,
    model: str,
    endpoint: str,
    timeout: int = 120,
) -> dict[str, Any]:
    """Call any OpenAI-compatible Chat Completions API."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "tools": tools,
        "tool_choice": {"type": "function", "function": {"name": tool_name}},
    }
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(endpoint, json=payload, headers=_build_auth_headers(api_key, endpoint))
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Unified caller — auto-detects provider from endpoint
# ---------------------------------------------------------------------------

def _call_llm(
    *,
    tool_name: str,           # "report_failure_analysis" or "report_run_analysis"
    prompt: str,
    api_key: str,
    model: str,
    endpoint: str,
    timeout: int = 120,
) -> dict[str, Any]:
    """
    Dispatch to the correct API format based on the endpoint URL,
    then extract and return the tool arguments dict.
    """
    if _is_azure_responses_api(endpoint):
        tool_obj = _FAILURE_TOOL_RESPONSES if tool_name == "report_failure_analysis" else _RUN_TOOL_RESPONSES
        response = _call_responses_api(
            instructions=_SYSTEM_PROMPT,
            input_text=prompt,
            tools=[tool_obj],
            tool_choice={"type": "function", "name": tool_name},
            api_key=api_key,
            model=model,
            endpoint=endpoint,
            timeout=timeout,
        )
        # Extract from Responses API output array
        for item in response.get("output", []):
            if item.get("type") == "function_call" and item.get("name") == tool_name:
                return json.loads(item["arguments"])
        raise ValueError(
            f"Model did not call tool '{tool_name}'. "
            f"Output types: {[o.get('type') for o in response.get('output', [])]}"
        )
    else:
        tool_obj = _FAILURE_TOOL_CHAT if tool_name == "report_failure_analysis" else _RUN_TOOL_CHAT
        response = _call_chat_completions_api(
            system_prompt=_SYSTEM_PROMPT,
            user_message=prompt,
            tools=[tool_obj],
            tool_name=tool_name,
            api_key=api_key,
            model=model,
            endpoint=endpoint,
            timeout=timeout,
        )
        # Extract from Chat Completions choices[0].message.tool_calls
        choices = response.get("choices", [])
        if choices:
            tool_calls = choices[0].get("message", {}).get("tool_calls", [])
            for tc in tool_calls:
                if tc.get("function", {}).get("name") == tool_name:
                    return json.loads(tc["function"]["arguments"])
        raise ValueError(
            f"Model did not call tool '{tool_name}'. "
            f"Response: {json.dumps(response)[:500]}"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_failure(
    test_name:       str,
    failure_message: str,
    stack_trace:     str,
    log_context:     TestLogContext | None,
    api_key:         str,
    model:           str = _DEFAULT_MODEL,
    max_tokens:      int = 1500,
    endpoint:        str = _DEFAULT_ENDPOINT,
) -> FailureAnalysis:
    """
    Analyze a single test failure using any supported LLM provider.

    Parameters
    ----------
    test_name       : Full name e.g. "StorageTest.verify_disk_io".
    failure_message : Short error from JUnit XML or console output.
    stack_trace     : Full traceback / error output.
    log_context     : Optional TestLogContext from log_collector.
    api_key         : API key for the chosen provider.
    model           : Model name (default gpt-4o).
    max_tokens      : Unused — kept for signature compatibility.
    endpoint        : Full API endpoint URL. Defaults to Azure OpenAI Responses API.
                      Pass a different URL to use OpenAI, Ollama, LM Studio, etc.

    Returns FailureAnalysis populated from the tool call response.
    """
    prompt = _build_failure_prompt(test_name, failure_message, stack_trace, log_context)
    data = _call_llm(
        tool_name="report_failure_analysis",
        prompt=prompt,
        api_key=api_key,
        model=model,
        endpoint=endpoint,
    )
    return FailureAnalysis(
        test_name=data.get("test_name", test_name),
        root_cause_category=RootCauseCategory(
            data.get("root_cause_category", RootCauseCategory.UNKNOWN.value)
        ),
        root_cause_description=data.get("root_cause_description", ""),
        recommended_fix=data.get("recommended_fix", ""),
        severity=FailureSeverity(data.get("severity", FailureSeverity.MEDIUM.value)),
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
    model:    str = _DEFAULT_MODEL,
    max_tokens: int = 2000,
    endpoint:   str = _DEFAULT_ENDPOINT,
) -> RunAnalysisSummary:
    """
    Produce a run-level summary from pre-computed per-failure analyses.

    Parameters mirror analyze_failure(). Sends a compact digest (not raw logs)
    so token usage scales with failure count, not log volume.
    """
    prompt = _build_run_prompt(failure_analyses, total, passed, failed, skipped)
    data = _call_llm(
        tool_name="report_run_analysis",
        prompt=prompt,
        api_key=api_key,
        model=model,
        endpoint=endpoint,
    )
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
        "| Metric | Value |",
        "|--------|-------|",
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

        lines.append("## Individual Recommendations")
        for fa in sorted(failure_analyses, key=lambda x: x.severity_order):
            lines.append(f"- **{fa.test_name}**: {fa.recommended_fix[:120]}")

    lines += [
        "",
        "Analyze this LISA test run. Call the `report_run_analysis` tool "
        "with your structured summary.",
    ]
    return "\n".join(lines)
