# LLM-Powered Test Analysis — Complete Guide

This guide explains how the LISA MCP server uses Azure OpenAI to automatically
analyze test failures, determine root causes, and generate rich reports.

---

## Table of Contents

1. [Overview — how it works](#1-overview--how-it-works)
2. [Prerequisites](#2-prerequisites)
3. [The 4 analysis tools](#3-the-4-analysis-tools)
4. [Step-by-step: analyze a test run](#4-step-by-step-analyze-a-test-run)
5. [Understanding the output](#5-understanding-the-output)
6. [Reading the HTML report](#6-reading-the-html-report)
7. [Root cause categories](#7-root-cause-categories)
8. [Failure severity levels](#8-failure-severity-levels)
9. [Log collection — how context is gathered](#9-log-collection--how-context-is-gathered)
10. [End-to-end pipeline: run_and_analyze](#10-end-to-end-pipeline-run_and_analyze)
11. [API cost guidance](#11-api-cost-guidance)
12. [CI/CD integration](#12-cicd-integration)

---

## 1. Overview — how it works

```
LISA test run output
 │
 ▼
┌─────────────────────────────────────┐
│ Step 1 — Parse results │
│ parse_results() → TestRunSummary │
│ JUnit XML or console output │
└──────────────┬──────────────────────┘
 │
 ▼
┌─────────────────────────────────────┐
│ Step 2 — Collect log context │
│ collect_run_logs() │
│ Tail-reads per-test .log files │
│ Extracts lines near ERROR/FAIL │
│ Hard cap: 256 KB per file │
│ 8,000 chars per test │
└──────────────┬──────────────────────┘
 │
 ▼
┌─────────────────────────────────────┐
│ Step 3 — Per-failure analysis │
│ For each failed test: │
│ analyze_failure() → Azure OpenAI API │
│ Uses tool_use for structured JSON │
│ Returns FailureAnalysis: │
│ • root_cause_category │
│ • root_cause_description │
│ • recommended_fix │
│ • severity (critical/high/…) │
│ • relevant_log_lines │
│ • confidence (0.0–1.0) │
└──────────────┬──────────────────────┘
 │
 ▼
┌─────────────────────────────────────┐
│ Step 4 — Run-level summary │
│ analyze_run() → Azure OpenAI API │
│ Sends compact digest (not logs) │
│ Returns RunAnalysisSummary: │
│ • overall_health │
│ • health_score │
│ • failure_patterns │
│ • top_priorities │
│ • recommendations │
│ • executive_summary │
└──────────────┬──────────────────────┘
 │
 ▼
┌─────────────────────────────────────┐
│ Step 5 — Report generation │
│ generate_html_report() │
│ generate_markdown_report() │
│ Self-contained HTML (no CDN) │
│ GitHub-flavored Markdown │
└─────────────────────────────────────┘
```

**Token usage per run:**
- Per failure: ~1,000–2,000 input tokens + ~500 output tokens
- Run summary: ~800 input tokens + ~800 output tokens
- 10 failures ≈ ~15,000–25,000 tokens total (~$0.05–0.15 at current pricing)

---

## 2. Prerequisites

### Get an Azure OpenAI API key

1. Go to https://portal.azure.com
2. Create an account or sign in
3. Navigate to **API Keys** → **Create Key**
4. Copy the key (starts with `YOUR_AZURE_OPENAI_API_KEY`)

The key is passed directly to the tools — it is never stored on disk by the MCP server.

### LISA installation (for running tests)

If you only want to analyze existing results, no LISA installation is needed.
For end-to-end `run_and_analyze`, LISA must be installed:

```bash
cd ~/lisa
pip install -e .
lisa --version
```

---

## 3. The 4 analysis tools

| Tool | Input | Output | Use case |
|------|-------|--------|---------|
| `analyze_test_run_with_llm` | Results + optional run dir | JSON with all analyses | Analyze results you already have |
| `analyze_failure_root_cause` | Single test name + error | JSON with FailureAnalysis | Deep-dive on one specific failure |
| `generate_analysis_report` | Results + output dir | HTML + Markdown + JSON | Full report to share with team |
| `run_and_analyze` | Runbook + lisa_path | All of the above | One-shot: run tests and get report |

---

## 4. Step-by-step: analyze a test run

### Option A — You have a JUnit XML file

```
I have LISA test results at ~/lisa/lisa_results.xml and LISA logs at ~/lisa/runtime/latest.
My Azure OpenAI API key is YOUR_AZURE_OPENAI_API_KEY
Analyze the failures and generate a report at ~/reports/
```

The AI calls `generate_analysis_report`:
```python
generate_analysis_report(
 results_source="~/lisa/lisa_results.xml",
 api_key="YOUR_AZURE_OPENAI_API_KEY",
 output_dir="~/reports/",
 run_dir="~/lisa/runtime/latest",
 report_base_name="my_run",
)
```

Returns:
```json
{
 "html_path": "/home/user/reports/my_run.html",
 "markdown_path": "/home/user/reports/my_run.md",
 "report": { ... }
}
```

Open `my_run.html` in a browser for the full visual report.

---

### Option B — You have console output

```
Here is my LISA run output. Analyze the failures with my API key YOUR_AZURE_OPENAI_API_KEY:

[PASS] Provisioning.smoke_test (12.3s)
[FAIL] StorageVerification.nvme_io_test (120.5s)
[FAIL] NetworkTest.verify_sriov (45.0s)
[PASS] CoreTest.verify_cpu_count (2.8s)
```

The AI calls `analyze_test_run_with_llm`:
```python
analyze_test_run_with_llm(
 results_source="[PASS] Provisioning...\n[FAIL] StorageVerification...",
 api_key="YOUR_AZURE_OPENAI_API_KEY",
)
```

---

### Option C — Investigate one specific failure

```
The test StorageVerification.nvme_io_test failed with:
"Expected exit code 0 but got 1"
The log is at ~/lisa/logs/StorageVerification/nvme_io_test/console.log
Analyze with API key YOUR_AZURE_OPENAI_API_KEY
```

The AI calls `analyze_failure_root_cause`:
```python
analyze_failure_root_cause(
 test_name="StorageVerification.nvme_io_test",
 failure_message="Expected exit code 0 but got 1",
 api_key="YOUR_AZURE_OPENAI_API_KEY",
 log_file_path="~/lisa/logs/StorageVerification/nvme_io_test/console.log",
)
```

---

### Option D — Run tests and analyze in one shot

```
Run the runbook at ~/runbooks/ubuntu22_t1.yml using LISA at ~/lisa.
Pass subscription_id=xxxx and admin_private_key_file=~/.ssh/lisa_key.
After running, analyze all failures with Azure OpenAI API key YOUR_AZURE_OPENAI_API_KEY
and save the report to ~/reports/ubuntu22_t1/
```

The AI calls `run_and_analyze` — fully automated end-to-end.

---

## 5. Understanding the output

### FailureAnalysis JSON

```json
{
 "test_name": "StorageVerification.nvme_io_test",
 "root_cause_category": "disk_io_error",
 "root_cause_description": "The NVMe device /dev/nvme0 was not found during test
 execution. The PCIe enumeration log shows a timeout at boot, suggesting the
 Azure VM SKU (Standard_D4s_v3) does not provide NVMe storage.",
 "recommended_fix": "Switch to an Lsv3 or Lv3 series VM for NVMe tests.
 Verify with: az vm list-skus --location westus3 | grep nvme
 Alternatively, check if the VM has NVMe: ls /dev/nvme*",
 "severity": "critical",
 "relevant_log_lines": [
 "[ 2.345] pcieport: PCIe Bus Error: severity=Corrected",
 "ERROR: NVMe device not found at /dev/nvme0",
 "FAILED: assert_that('/dev/nvme0').exists() -> False"
 ],
 "confidence": 0.88
}
```

### RunAnalysisSummary JSON

```json
{
 "overall_health": "critical",
 "health_score": 0.72,
 "failure_patterns": [
 "NVMe storage not enumerated on Standard_D4s_v3",
 "SR-IOV VF interface timeout on accelerated networking"
 ],
 "top_priorities": [
 "Switch VM SKU to Lsv3 series for all NVMe tests",
 "Investigate accelerated networking VF timeout",
 "Review kernel version for SR-IOV fixes"
 ],
 "environment_issues": [
 "Standard_D4s_v3 does not support NVMe — use Lsv3/Lv3"
 ],
 "recommendations": [
 "Update runbook to use Standard_L8s_v3 for storage tests",
 "Pin kernel to 5.15.0-1040-azure or later",
 "Add retry logic to SR-IOV VF detection (30s retry, 3 attempts)"
 ],
 "executive_summary": "This T1 test run achieved a 72% pass rate with 5 failures,
 2 of which are critical blockers. The NVMe storage failures are caused by the
 wrong VM SKU being used — a simple runbook fix will resolve 8 tests. The SR-IOV
 network failure appears related to a known driver timing issue in kernel 5.14.
 Recommend updating the runbook VM configuration and upgrading the kernel before
 the next run."
}
```

---

## 6. Reading the HTML report

The HTML report (`lisa_analysis.html`) has these sections:

### Header
- Overall health badge: **HEALTHY** / **DEGRADED** / **CRITICAL** / **UNKNOWN**
- Health score percentage (weighted by severity)
- Run directory and generation timestamp

### Metrics grid
Total tests · Passed · Failed · Skipped · Duration

### Pass rate bar
Visual progress bar showing pass rate.

### Executive Summary
3-5 sentence non-technical summary for stakeholders. Safe to paste into
a Jira ticket or email.

### Failure Analysis cards
One card per failed test, sorted by severity (critical first):
- **Badge**: severity level (CRITICAL / HIGH / MEDIUM / LOW)
- **Category badge**: root cause category
- **Confidence**: how certain The model is (0–100%)
- **Root Cause**: technical explanation
- **Recommended Fix**: specific actionable step
- **Log Lines**: most relevant log lines in a code block

### Top Priorities
Numbered list of the most important issues to fix first.

### Recommendations
Specific team actions (updating runbooks, fixing code, changing configs).

### Failure Patterns
Tag cloud of recurring themes across multiple failures.

### Environment / Infrastructure Issues
Problems that are not test code bugs — VM SKU, quota, network config.

---

## 7. Root cause categories

| Category | When used |
|----------|-----------|
| `kernel_panic` | Kernel crash, oops, BUG() call |
| `network_timeout` | SSH timeout, ping failure, SR-IOV VF timeout |
| `disk_io_error` | NVMe not found, I/O error, filesystem unmount |
| `permission_denied` | chmod issues, sudo failures, SELinux denials |
| `package_not_found` | apt/dnf install failure, binary not in PATH |
| `service_crash` | systemd service failed, process died unexpectedly |
| `assertion_failure` | Test assertion failed (expected != actual) |
| `timeout` | Test exceeded timeout, hung process |
| `environment_setup` | cloud-init failure, wrong VM SKU, missing feature |
| `flaky_test` | Race condition, intermittent timing issue |
| `infrastructure` | Azure quota, VM provisioning failure, network glitch |
| `unknown` | The model couldn't determine the root cause from available data |

---

## 8. Failure severity levels

| Severity | Meaning | Action |
|----------|---------|--------|
| `critical` | Blocks release; data loss or system instability risk | Fix before merge/publish |
| `high` | Major feature completely broken | Fix before next release |
| `medium` | Partial functionality impacted | Fix within sprint |
| `low` | Minor issue, informational | Fix when convenient |

Severity determines card color in the HTML report and sort order.

---

## 9. Log collection — how context is gathered

When `run_dir` is provided, the log collector:

1. **Walks** standard LISA output directories:
 - `<run_dir>/logs/<SuiteName>/<test_method>/`
 - `<run_dir>/runtime/<timestamp>/<test_name>/`

2. **Tail-reads** each `.log` file (last 256 KB only — never loads whole file)

3. **Scans** for lines matching these error patterns:
 ```
 ERROR, FAILED, EXCEPTION, Traceback, AssertionError,
 CRITICAL, PANIC, exit code [non-zero], returncode, timeout,
 permission denied, connection refused, no such file
 ```

4. **Extracts** 15 lines of context before and after each error signal

5. **Caps** output at 8,000 characters per test (≈ 150 lines)

6. **Sends** the context snippet to the AI alongside the failure message

### What to do if logs aren't found

If `run_dir` contains no log files:
- Analysis still works using just the failure message and stack trace
- Add `run_dir=None` explicitly to skip log collection
- The AI will note low confidence when logs are insufficient

---

## 10. End-to-end pipeline: `run_and_analyze`

`run_and_analyze` ties everything together:

```
1. run_tests(lisa_path, runbook_path, variables)
 │
 ▼
2. Find results: look for lisa_results.xml in
 - <lisa_path>/runtime/<latest>/
 - <lisa_path>/runs/<latest>/
 - Current working directory
 Fallback: use stdout as results_source
 │
 ▼
3. generate_analysis_report(results_source, api_key, output_dir, run_dir)
 │
 ▼
4. Return: {
 run_result: { success, returncode, command },
 summary_line: "CRITICAL | 13/18 passed (72.2%) | 5 failed",
 html_path: "/path/to/lisa_analysis.html",
 markdown_path: "/path/to/lisa_analysis.md",
 report: { ... full AnalysisReport ... }
 }
```

### Example conversation

```
Run the runbook ~/runbooks/rhel9_t1.yml with:
 - LISA at ~/lisa
 - subscription_id: xxxx
 - admin_private_key_file: ~/.ssh/lisa_key
 - Azure OpenAI API key: YOUR_AZURE_OPENAI_API_KEY
Save reports to ~/reports/rhel9_t1/
```

The AI calls `run_and_analyze` and returns:

```
✅ Run complete.
Health: DEGRADED | 15/18 passed (83.3%) | 3 failed

Reports:
 HTML: ~/reports/rhel9_t1/lisa_analysis.html
 Markdown: ~/reports/rhel9_t1/lisa_analysis.md

Top failures:
 1. [CRITICAL] CoreTest.verify_kdump — kdump service not found on RHEL 9.2
 2. [HIGH] NetworkTest.verify_sriov — SR-IOV VF timeout
 3. [MEDIUM] StorageTest.verify_swap — swap not enabled by default

Executive summary:
 83% of T1 tests passed with 3 failures. The kdump failure is critical for
 kernel crash collection and should be fixed before image publication...
```

---

## 11. API cost guidance

Approximate costs (February 2026 pricing for gpt-4o):

| Scenario | Failures | Approx tokens | Approx cost |
|----------|----------|---------------|-------------|
| T0 smoke run | 1–3 | ~5,000 | ~$0.01 |
| T1 daily CI | 3–10 | ~15,000–30,000 | ~$0.05–0.10 |
| T2 weekly regression | 5–20 | ~25,000–60,000 | ~$0.08–0.20 |
| T4 full certification | 20+ | ~80,000+ | cap at 20 failures |

### Controlling cost

Use `max_failures_to_analyze` to cap the number of LLM calls:
```python
analyze_test_run_with_llm(
 results_source="lisa_results.xml",
 api_key="YOUR_AZURE_OPENAI_API_KEY",
 max_failures_to_analyze=5, # only analyze the 5 worst failures
)
```

The tool analyzes failures in the order they appear in the results file.
Sort by severity in post-processing if needed.

---

## 12. CI/CD integration

### GitHub Actions — analyze after every run

```yaml
- name: Run LISA T1 tests
 run: |
 lisa -r runbook.yml \
 -v subscription_id=${{ secrets.AZURE_SUB_ID }} \
 -v admin_private_key_file=/tmp/lisa_key

- name: Analyze failures with the AI
 if: always() # run even if tests failed
 run: |
 python3 -c "
 import json
 from lisa_mcp.tools.result_parser import parse_junit_xml
 from lisa_mcp.server import generate_analysis_report

 result = generate_analysis_report(
 results_source='./lisa_results.xml',
 api_key='${{ secrets.AZURE_OPENAI_API_KEY }}',
 output_dir='./reports/',
 run_dir='.',
 )
 data = json.loads(result)
 report = data['report']
 health = report['summary']['overall_health'].upper()
 print(f'Health: {health}')
 print(f'Summary: {report[\"summary\"][\"executive_summary\"]}')
 "

- name: Upload analysis report
 if: always()
 uses: actions/upload-artifact@v4
 with:
 name: lisa-analysis-${{ github.run_id }}
 path: reports/
```

### Post analysis in a GitHub comment (on PR)

```python
import json
import subprocess

# Get the analysis
result = json.loads(generate_analysis_report(...))
report = result["report"]
summary = report["summary"]

# Build comment body
comment = f"""## LISA Test Analysis — {summary['overall_health'].upper()}

**Health score:** {int(summary['health_score'] * 100)}%
**Passed:** {report['passed']}/{report['total']}

### Executive Summary
{summary['executive_summary']}

### Top Priorities
""" + "\n".join(f"- {p}" for p in summary['top_priorities'][:3])

# Post via gh CLI
subprocess.run([
 "gh", "pr", "comment", "--body", comment
])
```
