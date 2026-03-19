# Usage Guide — LISA MCP Server

This guide shows real, working examples of every major workflow: discovering tests,
building runbooks, generating test code, running tests, and analyzing results with Azure OpenAI.

---

## Table of Contents

1. [How to use this with an MCP client](#1-how-to-use-this-with-an-mcp-client)
2. [Workflow A — Discover and explore test cases](#workflow-a--discover-and-explore-test-cases)
3. [Workflow B — Select tests for a scenario](#workflow-b--select-tests-for-a-scenario)
4. [Workflow C — Build a runbook](#workflow-c--build-a-runbook)
5. [Workflow D — Write a new test case](#workflow-d--write-a-new-test-case)
6. [Workflow E — Run tests via the CLI](#workflow-e--run-tests-via-the-cli)
7. [Workflow F — Analyze test results](#workflow-f--analyze-test-results)
8. [Workflow G — AI-powered failure analysis (Azure OpenAI)](#workflow-g--ai-powered-failure-analysis-azure-openai)
9. [Workflow H — CI/CD automation](#workflow-h--cicd-automation)
10. [Tips and patterns](#tips-and-patterns)

---

## 1. How to use this with an MCP client

Every tool in this MCP server is available to VS Code (or any MCP client) as a function.
You talk to the AI in natural language; it decides which tools to call and in what order.

**You don't need to remember tool names.** Just describe what you want.

### Starting a LISA session

```
I'm working with LISA (Microsoft's Linux testing framework) cloned at ~/lisa.
My LISA MCP server is connected. Help me [your task here].
```

### Providing the LISA path

Almost every tool needs the path to your LISA repo. Be explicit:

```
lisa_path = ~/lisa (Linux/WSL2)
lisa_path = /mnt/c/Users/YourName/lisa (WSL2 Windows drive)
lisa_path = C:\Users\YourName\lisa (Windows native Python)
```

---

## Workflow A — Discover and explore test cases

### A1. See all test areas

```
What functional test areas exist in ~/lisa?
```

The AI calls `list_test_areas(lisa_path="~/lisa")`.

Sample response:
```
Available test areas (18 total):
 cpu, core, hyperv, kdump, memory, network, nvme, perf_network,
 perf_storage, provisioning, resizing, security, storage, sriov,
 startstop, stress, vhd, xdp
```

---

### A2. List all tests in an area

```
Show me all the storage tests in ~/lisa — include their priority and description.
```

The AI calls `discover_test_cases(lisa_path="~/lisa", area="storage")`.

---

### A3. Filter by tier (T0–T4)

```
Show me only T0 (highest priority) tests across all areas in ~/lisa
```

The AI calls `discover_test_cases(lisa_path="~/lisa", tier="T0")`.

| Tier | Priorities | Typical use |
|------|-----------|------------|
| T0 | P0 only | Pre-merge smoke gate (~5 min) |
| T1 | P0, P1 | Daily CI (~2 hours) |
| T2 | P0, P1, P2 | Weekly regression (~8 hours) |
| T3 | P0, P1, P2, P3 | Pre-GA validation (~16 hours) |
| T4 | All (P0–P5) | Full certification (no limit) |

---

### A4. Filter by platform

```
Show me only tests that support HyperV in ~/lisa
```

The AI calls `discover_test_cases(lisa_path="~/lisa", platform="hyperv")`.

---

### A5. Free-text search

```
Search ~/lisa for any tests related to "NVMe" or "disk performance"
```

The AI calls `search_tests(lisa_path="~/lisa", query="nvme disk performance")`.

---

### A6. Get full details on one test

```
Give me the complete metadata for the test "Provisioning.smoke_test" in ~/lisa
```

The AI calls `get_test_case_details(lisa_path="~/lisa", test_name="Provisioning.smoke_test")`.

---

## Workflow B — Select tests for a scenario

### B1. "I'm releasing a new RHEL 9 image on Azure — which tests should I run?"

```
I'm about to publish a RHEL 9 image to Azure Marketplace.
Which LISA tests should I run to validate it? LISA is at ~/lisa.
```

The AI will discover T1 tests for Azure, suggest suites (provisioning, network, storage,
cpu, memory) and offer to build a runbook.

### B2. "Run only tests that don't require special hardware"

```
Show me all tests in ~/lisa that have no hardware requirements
```

The AI discovers all tests and filters client-side for those with empty requirements.

### B3. "Which tests cover SR-IOV networking?"

```
Find all tests in ~/lisa related to SR-IOV or high-performance networking
```

The AI calls `search_tests(query="sriov SR-IOV accelerated networking")`.

---

## Workflow C — Build a runbook

A **runbook** is the YAML config file that tells LISA which tests to run, on which
platform, with which image, and how to report results.

### C1. Build a standard tier runbook

```
Build a T1 runbook for Azure using Ubuntu 22.04 LTS.
Save it to ~/runbooks/ubuntu22_t1.yml
```

The AI calls `build_tier_runbook_file(tier="T1", platform_type="azure", output_path="~/runbooks/ubuntu22_t1.yml")`.

Generated YAML (excerpt):
```yaml
name: LISA T1 Run
concurrency: 1
exit_on_first_failure: false
import_builtin_tests: true

platform:
 - type: azure
 azure:
 subscription_id: $(subscription_id)
 marketplace: ubuntu jammy 22.04-lts latest

testcase:
 - criteria:
 priority: [0, 1]

notifier:
 - type: html
 path: ./lisa_report.html
 - type: junit
 path: ./lisa_results.xml
```

---

### C2. Build a runbook with specific tests

```
Build a runbook that runs only:
 - Provisioning.smoke_test
 - NetworkConnectivity.verify_ping
 - StorageVerification.verify_disks
On Azure, Ubuntu 20.04, East US region. Save to ~/runbooks/targeted.yml
```

The AI calls `build_runbook(name="Targeted Test Run", platform_type="azure", test_names=[...])`.

---

### C3. Validate an existing runbook

```
Validate the runbook at ~/lisa/microsoft/runbook/azure.yml
```

The AI calls `validate_runbook_file(runbook_path="~/lisa/microsoft/runbook/azure.yml")`.

---

### C4. Add a test to an existing runbook

```
Add "StorageVerification.nvme_basic" to ~/runbooks/ubuntu22_t1.yml
```

The AI calls `add_test_to_existing_runbook(runbook_path="...", test_name="nvme_basic", select_action="include")`.

---

## Workflow D — Write a new test case

### D1. Generate a complete test suite

```
Write a new LISA test suite called "KvpTests" in the "hyperv" area.
It should verify that the Hyper-V Key-Value Pair daemon is running.
Priority 1, functional, Azure and HyperV platforms.
Save to ~/lisa/microsoft/testsuites/kvp_tests.py
```

The AI calls `generate_test_suite_code(...)` and writes the file.

### D2. Generate a minimal test case snippet

```
Give me a test case snippet that checks the number of vCPUs matches
what Azure provisioned. Priority 0.
```

The AI reads the `lisa://test-case-template` resource and generates the snippet.

### D3. Example — network test suite

See [examples/network_connectivity_test.py](examples/network_connectivity_test.py) for
a complete generated network test suite with 6 test cases (P0–P2) covering:
- Default gateway reachability
- DNS resolution
- Interface UP state and IPv4 assignment
- Outbound HTTP connectivity
- MTU size validation
- TCP data transfer

---

## Workflow E — Run tests via the CLI

> **Note:** Running tests requires LISA installed (`pip install -e ~/lisa`) and
> valid Azure credentials. This launches real cloud infrastructure.

### E1. Run a runbook

```
Run the runbook at ~/runbooks/ubuntu22_t1.yml using LISA at ~/lisa.
Subscription ID is xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
SSH key is at ~/.ssh/lisa_id_rsa
```

The AI calls `run_lisa_tests(lisa_path="~/lisa", runbook_path="...", variables={...})`.

This executes:
```bash
lisa -r ~/runbooks/ubuntu22_t1.yml \
 -v subscription_id:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
 -v admin_private_key_file:~/.ssh/lisa_id_rsa
```

### E2. Check LISA environment first

```
Is LISA installed and ready to run tests?
```

The AI calls `check_lisa_environment()`.

### E3. Run with variable overrides

```
Run azure.yml but override location to eastus2 and use Standard_D4s_v5.
```

The AI calls `run_lisa_tests` with the appropriate `variables` dict.

---

## Workflow F — Analyze test results

### F1. Parse a JUnit XML file

```
Parse the test results at ~/lisa/lisa_results.xml and summarize what failed.
```

The AI calls `parse_test_results(source="~/lisa/lisa_results.xml")`.

### F2. Analyze raw console output

```
Here is my LISA run output. What went wrong?

[PASS] Provisioning.smoke_test (12.3s)
[FAIL] NetworkConnectivity.verify_sriov (45.0s) — exit code 1
[FAIL] StorageVerification.disk_io_test (120.0s) — timeout
[PASS] CoreTest.verify_cpu_count (2.8s)
```

The AI calls `parse_test_results(source=<the output text>)` and explains what failed.

---

## Workflow G — AI-powered failure analysis (Azure OpenAI)

The server integrates with **Azure OpenAI** to provide root cause analysis, severity
scoring, and fix recommendations.

**Endpoint (pre-configured):**
`https://kkopenailearn.openai.azure.com/openai/responses?api-version=2025-04-01-preview`

Pass your API key to any analysis tool.

### G1. Analyze failures from a JUnit XML file

```
Analyze the failures in ~/lisa/lisa_results.xml
Azure OpenAI key: <your-key>
Logs are at ~/lisa/runtime/latest/
Save the report to ~/reports/
```

The AI calls `generate_analysis_report(results_source="...", api_key="...", output_dir="~/reports/")`.

Returns:
- `~/reports/lisa_analysis.html` — visual report with failure cards
- `~/reports/lisa_analysis.md` — Markdown version

### G2. Deep-dive on one failure

```
The test StorageVerification.nvme_io_test failed with:
"Expected exit code 0 but got 1"
Log is at ~/lisa/logs/nvme_io_test/console.log
Analyze with Azure OpenAI key: <your-key>
```

The AI calls `analyze_failure_root_cause(test_name="...", failure_message="...", api_key="...")`.

Returns structured `FailureAnalysis`:
```json
{
 "root_cause_category": "disk_io_error",
 "root_cause_description": "The NVMe device /dev/nvme0 was not found...",
 "recommended_fix": "Switch to Lsv3 series VM. Verify: ls /dev/nvme*",
 "severity": "critical",
 "relevant_log_lines": ["ERROR: NVMe device not found at /dev/nvme0"],
 "confidence": 0.88
}
```

### G3. Run tests and analyze in one shot

```
Run the runbook ~/runbooks/ubuntu22_t1.yml using LISA at ~/lisa.
subscription_id: xxxx, admin_private_key_file: ~/.ssh/lisa_key
Azure OpenAI key: <your-key>
Save reports to ~/reports/ubuntu22_t1/
```

The AI calls `run_and_analyze(...)` — end-to-end: run → collect logs → analyze → report.

### G4. Understanding the analysis output

**Per-failure analysis fields:**

| Field | Description |
|-------|-------------|
| `root_cause_category` | One of: `kernel_panic`, `network_timeout`, `disk_io_error`, `permission_denied`, `package_not_found`, `service_crash`, `assertion_failure`, `timeout`, `environment_setup`, `flaky_test`, `infrastructure`, `unknown` |
| `root_cause_description` | 2–4 sentence technical explanation |
| `recommended_fix` | Specific commands, file paths, or settings to investigate |
| `severity` | `critical` / `high` / `medium` / `low` |
| `relevant_log_lines` | Up to 10 most relevant log lines |
| `confidence` | 0.0–1.0 — how certain the model is |

**Run-level summary fields:**

| Field | Description |
|-------|-------------|
| `overall_health` | `healthy` / `degraded` / `critical` / `unknown` |
| `health_score` | 0.0–1.0 weighted pass rate |
| `failure_patterns` | Recurring themes across failures |
| `top_priorities` | Ordered list of most important issues |
| `executive_summary` | 3–5 sentence stakeholder summary |

---

## Workflow H — CI/CD automation

See [docs/automation-guide.md](docs/automation-guide.md) for full CI/CD setup.

Quick GitHub Actions example:

```yaml
- name: Run LISA T0 gate
 run: |
 lisa -r runbook.yml \
 -v subscription_id:${{ secrets.AZURE_SUBSCRIPTION_ID }} \
 -v admin_private_key_file:/tmp/ssh_key

- name: Analyze failures with Azure OpenAI
 if: failure()
 run: |
 python3 -c "
 import json
 from lisa_mcp.tools.result_parser import parse_results
 from lisa_mcp.tools.llm_analyzer import analyze_failure, analyze_run

 summary = parse_results('./lisa_results.xml')
 # analyze failures...
 " \
 AZURE_OPENAI_API_KEY=${{ secrets.AZURE_OPENAI_API_KEY }}

- name: Upload analysis report
 uses: actions/upload-artifact@v4
 with:
 name: lisa-report
 path: reports/
```

---

## Tips and patterns

### Tip 1 — Always specify the lisa_path explicitly

```
# Better — avoids ambiguity
"Scan the LISA repo at /home/kkashanjat/lisa for network tests"
```

### Tip 2 — Use tier names, not priority numbers

```
# Instead of: "show me priority 0, 1, and 2 tests"
# Say: "show me T2 tier tests"
```

### Tip 3 — Combine discovery + runbook in one request

```
Find all NVMe tests in ~/lisa at tier T1, then build a runbook for Azure East US.
Save to ~/nvme_t1.yml
```

The AI will chain `discover_test_cases` → `build_runbook` automatically.

### Tip 4 — Validate before running

```
Validate ~/my_runbook.yml before we run it against Azure
```

### Tip 5 — Use prompts for guided workflows

Three built-in prompts trigger complete multi-step workflows:

```
/select_tests_for_scenario — guided test selection
/create_new_test — guided test authoring
/analyze_test_failure — guided failure analysis
```

### Tip 6 — Dry-run to preview the command

```
Run the runbook with dry_run=true so I can see the command first
```

---

## Reference: tool → natural language mapping

| You say | The AI calls |
|---------|-------------|
| "what areas are in ~/lisa" | `list_test_areas` |
| "show me all T0 tests" | `discover_test_cases(tier="T0")` |
| "find tests about networking" | `search_tests(query="network")` |
| "details on smoke_test" | `get_test_case_details` |
| "build a T1 Azure runbook" | `build_tier_runbook_file` |
| "build a custom runbook" | `build_runbook` |
| "add this test to my runbook" | `add_test_to_existing_runbook` |
| "validate my runbook" | `validate_runbook_file` |
| "write a test suite for X" | `generate_test_suite_code` |
| "run the runbook" | `run_lisa_tests` |
| "parse the results" | `parse_test_results` |
| "is LISA installed?" | `check_lisa_environment` |
| "explain the tier system" | `get_tier_info` |
| "analyze failures with AI" | `analyze_test_run_with_llm` |
| "deep-dive on one failure" | `analyze_failure_root_cause` |
| "generate an analysis report" | `generate_analysis_report` |
| "run and analyze end-to-end" | `run_and_analyze` |

---

## Workflow H — Selecting a Different LLM Provider

By default the AI analysis tools use the pre-configured Azure OpenAI endpoint. To use a different provider, pass `endpoint` and `api_key` explicitly:

**OpenAI:**
```
Analyze failures in lisa_results.xml
API key: sk-...
Endpoint: https://api.openai.com/v1/chat/completions
Model: gpt-4o
```

**Local Ollama (no key needed):**
```
Analyze failures in lisa_results.xml
API key: ollama
Endpoint: http://localhost:11434/v1/chat/completions
Model: llama3
```

**Azure AI Foundry:**
```
Analyze failures in lisa_results.xml
API key: <GitHub Models token>
Endpoint: https://models.inference.ai.azure.com/chat/completions
Model: gpt-4o
```

Call `list_llm_providers` to see all supported providers and their example endpoints at any time.

