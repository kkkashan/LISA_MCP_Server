# Usage Guide — LISA MCP Server

This guide shows real, working examples of every major workflow: discovering tests,
building runbooks, generating test code, running tests, and analyzing results.

---

## Table of Contents

1. [How to use this with the AI](#1-how-to-use-this-with-the AI)
2. [Workflow A — Discover and explore test cases](#workflow-a--discover-and-explore-test-cases)
3. [Workflow B — Select tests for a scenario](#workflow-b--select-tests-for-a-scenario)
4. [Workflow C — Build a runbook](#workflow-c--build-a-runbook)
5. [Workflow D — Write a new test case](#workflow-d--write-a-new-test-case)
6. [Workflow E — Run tests via the CLI](#workflow-e--run-tests-via-the-cli)
7. [Workflow F — Analyze test results](#workflow-f--analyze-test-results)
8. [Workflow G — CI/CD automation](#workflow-g--cicd-automation)
9. [Tips and patterns](#tips-and-patterns)

---

## 1. How to use this with the AI

Every tool in this MCP server is available to VS Code as a function. You talk
to the AI in natural language; The AI decides which tools to call and in what order.

**You don't need to remember tool names.** Just describe what you want.

### Starting a LISA session

A good opening message that gives the AI the context it needs:

```
I'm working with LISA (Microsoft's Linux testing framework) cloned at ~/lisa.
My LISA MCP server is connected. Help me [your task here].
```

### Providing the LISA path

Almost every tool needs the path to your LISA repo. Be explicit:

```
lisa_path = ~/lisa          (Linux/WSL2)
lisa_path = /mnt/c/Users/YourName/lisa   (WSL2 Windows drive)
lisa_path = C:\Users\YourName\lisa       (Windows, if Python is native)
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

Sample response:
```json
{
  "total_suites": 3,
  "total_test_cases": 22,
  "suites": [
    {
      "suite": "StorageVerification",
      "area": "storage",
      "test_cases": [
        {
          "name": "StorageVerification.verify_disks",
          "priority": 0,
          "description": "Verifies all expected disks are attached and accessible",
          "timeout": 3600,
          "requirement": { "min_disk_space_gb": 20 }
        },
        ...
      ]
    }
  ]
}
```

---

### A3. Filter by tier (T0–T4)

```
Show me only T0 (highest priority) tests across all areas in ~/lisa
```

The AI calls `discover_test_cases(lisa_path="~/lisa", tier="T0")`.

The tier mapping:
| Tier | Priorities included | Typical use |
|------|---------------------|------------|
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

Results are scored by relevance (name match > description match > area match).

---

### A6. Get full details on one test

```
Give me the complete metadata for the test "Provisioning.smoke_test" in ~/lisa
```

The AI calls `get_test_case_details(lisa_path="~/lisa", test_name="Provisioning.smoke_test")`.

Returns:
```json
{
  "name": "Provisioning.smoke_test",
  "method_name": "smoke_test",
  "suite_name": "Provisioning",
  "area": "provisioning",
  "priority": 0,
  "timeout": 3600,
  "description": "Verifies the VM is accessible via SSH",
  "requirement": {
    "supported_platform_type": ["AZURE"],
    "min_core_count": null
  }
}
```

---

## Workflow B — Select tests for a scenario

### B1. "I'm releasing a new RHEL 9 image on Azure — which tests should I run?"

```
I'm about to publish a RHEL 9 image to Azure Marketplace.
Which LISA tests should I run to validate it? LISA is at ~/lisa.
```

The AI will:
1. Call `discover_test_cases` filtering by `platform="azure"` and `tier="T1"`
2. Suggest a set of suites (provisioning, network, storage, cpu, memory)
3. Offer to build a runbook

---

### B2. "Run only tests that don't require special hardware"

```
Show me all tests in ~/lisa that have no hardware requirements
(no min_core_count, no special features needed)
```

The AI discovers all tests and filters client-side for those with empty requirements.

---

### B3. "Which tests cover SR-IOV networking?"

```
Find all tests in ~/lisa related to SR-IOV or high-performance networking
```

The AI calls `search_tests(query="sriov SR-IOV accelerated networking")` to surface all relevant cases.

---

## Workflow C — Build a runbook

A **runbook** is the YAML config file that tells LISA which tests to run, on which
platform, with which image, and how to report results.

### C1. Build a standard tier runbook

```
Build a T1 runbook for Azure using Ubuntu 22.04 LTS.
Save it to ~/runbooks/ubuntu22_t1.yml
```

The AI calls `build_tier_runbook_file`:
- tier: `"T1"`
- platform_type: `"azure"`
- image: `"ubuntu jammy 22.04-lts latest"`
- output_path: `"~/runbooks/ubuntu22_t1.yml"`

Generated file:
```yaml
# LISA Runbook — generated by lisa-mcp-server
# Platform: azure

name: LISA T1 Run
concurrency: 1
exit_on_first_failure: false
import_builtin_tests: true

variable:
  - name: location
    value: westus3
  - name: subscription_id
    value: $(subscription_id)

platform:
  - type: azure
    admin_private_key_file: $(admin_private_key_file)
    azure:
      subscription_id: $(subscription_id)
      marketplace: ubuntu jammy 22.04-lts latest

testcase:
  - criteria:
      priority: [0, 1]

notifier:
  - type: console
    log_level: INFO
  - type: html
    path: ./lisa_report.html
    auto_open: false
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
On Azure, Ubuntu 20.04, East US region.
Save to ~/runbooks/targeted.yml
```

The AI calls `build_runbook`:
```python
build_runbook(
    name="Targeted Test Run",
    platform_type="azure",
    test_names=["smoke_test", "verify_ping", "verify_disks"],
    image="ubuntu focal 20.04-lts latest",
    location="eastus",
    notifiers=["html", "junit"],
    output_path="~/runbooks/targeted.yml"
)
```

---

### C3. Build a runbook with exclusions

```
Build a T2 runbook but exclude anything related to stress tests
and any test named "test_reboot"
```

The AI calls `build_runbook`:
```python
build_runbook(
    name="T2 No Stress",
    tier="T2",
    excluded_names=["test_reboot"],
    # stress tests are filtered by telling the AI to also exclude that area
)
```

---

### C4. Validate an existing runbook

```
Validate the runbook at ~/lisa/microsoft/runbook/azure.yml
```

The AI calls `validate_runbook_file(runbook_path="~/lisa/microsoft/runbook/azure.yml")`.

Returns:
```json
{
  "valid": true,
  "errors": [],
  "warnings": [
    "Variable '$(subscription_id)' referenced but not defined — pass via -v"
  ],
  "summary": {
    "name": "Azure Default",
    "concurrency": 2,
    "platform_types": ["azure"],
    "test_criteria_count": 3,
    "notifiers": ["console", "html", "junit"]
  }
}
```

---

### C5. Add a test to an existing runbook

```
Add "StorageVerification.nvme_basic" to ~/runbooks/ubuntu22_t1.yml
```

The AI calls `add_test_to_existing_runbook`:
```python
add_test_to_existing_runbook(
    runbook_path="~/runbooks/ubuntu22_t1.yml",
    test_name="nvme_basic",
    select_action="include"
)
```

---

## Workflow D — Write a new test case

### D1. Generate a complete test suite

```
Write a new LISA test suite called "KvpTests" in the "hyperv" area.
It should verify that the Hyper-V Key-Value Pair daemon is running
and that we can read/write KVP entries.
Priority 1, functional, Azure and HyperV platforms.
Save to ~/lisa/microsoft/testsuites/kvp_tests.py
```

The AI calls `generate_test_suite_code` with:

```python
generate_test_suite_code(
    suite_class_name="KvpTests",
    area="hyperv",
    category="functional",
    description="Verifies Hyper-V Key-Value Pair (KVP) daemon functionality",
    owner="your-team",
    test_cases=[
        {
            "method_name": "verify_kvp_daemon_running",
            "description": "Verifies the hv_kvp_daemon process is running",
            "priority": 1,
            "requirement": {
                "supported_platform_type": ["AZURE", "HYPERV"]
            },
            "body_lines": [
                'result = node.execute("pgrep hv_kvp_daemon", expected_exit_code=0)',
                'assert_that(result.stdout.strip()).described_as("kvp daemon PID").is_not_empty()'
            ]
        },
        {
            "method_name": "verify_kvp_read",
            "description": "Verifies KVP entries can be read from the host",
            "priority": 2,
            "requirement": {
                "supported_platform_type": ["AZURE", "HYPERV"]
            }
        }
    ],
    output_path="~/lisa/microsoft/testsuites/kvp_tests.py"
)
```

Generated file (excerpt):
```python
@TestSuiteMetadata(
    area="hyperv",
    category="functional",
    description="Verifies Hyper-V Key-Value Pair (KVP) daemon functionality",
    owner="your-team",
)
class KvpTests(TestSuite):

    @TestCaseMetadata(
        description="Verifies the hv_kvp_daemon process is running",
        priority=1,
        timeout=3600,
        use_new_environment=False,
        requirement=simple_requirement(
            supported_platform_type=[AZURE, HYPERV]
        ),
    )
    def verify_kvp_daemon_running(self, case_name, node, environment, log):
        result = node.execute("pgrep hv_kvp_daemon", expected_exit_code=0)
        assert_that(result.stdout.strip()).described_as("kvp daemon PID").is_not_empty()
```

---

### D2. Generate a minimal test case to extend an existing suite

```
Give me a test case snippet that checks the number of vCPUs matches
what Azure provisioned. It should use node.execute and assert_that.
Priority 0.
```

The AI reads the `lisa://test-case-template` resource and generates:

```python
@TestCaseMetadata(
    description="Verifies vCPU count matches the VM size specification",
    priority=0,
    timeout=120,
    requirement=simple_requirement(
        environment_status=EnvironmentStatus.Deployed,
        supported_platform_type=[AZURE],
    ),
)
def verify_vcpu_count(self, case_name, node, environment, log):
    result = node.execute("nproc", expected_exit_code=0)
    actual_cpus = int(result.stdout.strip())
    expected = node.capability.core_count
    assert_that(actual_cpus).described_as("vCPU count").is_equal_to(expected)
```

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

The AI calls `run_lisa_tests`:
```python
run_lisa_tests(
    lisa_path="~/lisa",
    runbook_path="~/runbooks/ubuntu22_t1.yml",
    variables={
        "subscription_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "admin_private_key_file": "~/.ssh/lisa_id_rsa"
    }
)
```

This executes:
```bash
lisa -r ~/runbooks/ubuntu22_t1.yml \
     -v subscription_id:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
     -v admin_private_key_file:~/.ssh/lisa_id_rsa
```

Returns:
```json
{
  "success": true,
  "returncode": 0,
  "stdout": "... test output ...",
  "stderr": "",
  "command": "lisa -r ~/runbooks/ubuntu22_t1.yml ..."
}
```

### E2. Check if LISA is installed first

```
Is LISA installed and ready to run tests?
```

The AI calls `check_lisa_environment()` before attempting a run.

### E3. Run with extra variable overrides

```
Run the azure.yml runbook at ~/lisa/microsoft/runbook/azure.yml
but override the location to eastus2 and use a Standard_D4s_v5 VM size.
```

The AI calls `run_lisa_tests` with:
```python
variables={
    "location": "eastus2",
    "vm_size": "Standard_D4s_v5",
    "subscription_id": "..."
}
```

---

## Workflow F — Analyze test results

### F1. Parse a JUnit XML file

```
Parse the test results at ~/lisa/lisa_results.xml and summarize what failed.
```

The AI calls `parse_test_results(source="~/lisa/lisa_results.xml")`.

Returns:
```json
{
  "summary_line": "Total: 45 | Passed: 42 (93.3%) | Failed: 3 | Skipped: 0",
  "total": 45,
  "passed": 42,
  "failed": 3,
  "skipped": 0,
  "results": [
    {
      "name": "StorageVerification.nvme_io_test",
      "status": "failed",
      "duration_seconds": 120.5,
      "message": "Expected exit code 0, got 1",
      "stack_trace": "AssertionError: ..."
    },
    ...
  ]
}
```

### F2. Analyze raw console output

```
Here is my LISA run output. What went wrong?

[PASS] Provisioning.smoke_test (12.3s)
[FAIL] NetworkConnectivity.verify_sriov (45.0s) — exit code 1
[FAIL] StorageVerification.disk_io_test (120.0s) — timeout
[PASS] CoreTest.verify_cpu_count (2.8s)
```

The AI calls `parse_test_results(source=<the output text>)` and then explains:
- Which tests failed and why
- Whether failures are related
- Suggested next steps

### F3. Use the guided failure analysis prompt

In VS Code, type:

```
/analyze_test_failure
```

The AI prompts you to paste the failure output and then provides a structured analysis.

---

## Workflow G — CI/CD automation

See [docs/automation-guide.md](docs/automation-guide.md) for full CI/CD setup.

Quick GitHub Actions example:

```yaml
- name: Build LISA runbook
  run: |
    python3 -c "
    from lisa_mcp.tools.test_generator import generate_runbook_yaml
    yaml = generate_runbook_yaml(
        name='CI T0 Gate',
        platform_type='azure',
        tier='T0',
        notifiers=['junit'],
        image='ubuntu focal 20.04-lts latest'
    )
    open('ci_runbook.yml', 'w').write(yaml)
    "

- name: Run LISA tests
  run: |
    lisa -r ci_runbook.yml \
         -v subscription_id:${{ secrets.AZURE_SUBSCRIPTION_ID }} \
         -v admin_private_key_file:/tmp/ssh_key

- name: Parse results
  run: |
    python3 -c "
    from lisa_mcp.tools.result_parser import parse_junit_xml, summarize
    s = parse_junit_xml('lisa_results.xml')
    print(summarize(s))
    exit(1 if s.failed > 0 else 0)
    "
```

---

## Tips and patterns

### Tip 1 — Always specify the lisa_path explicitly

```
# Good
"Scan ~/lisa for network tests"

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
Find all NVMe tests in ~/lisa at tier T1, then build a runbook
for Azure East US with JUnit output. Save to ~/nvme_t1.yml
```

The AI will chain `discover_test_cases` → `build_runbook` automatically.

### Tip 4 — Validate before running

Always ask the AI to validate a runbook before running it against real infrastructure:

```
Validate ~/my_runbook.yml before we run it
```

### Tip 5 — Use prompts for guided workflows

Three built-in prompts trigger complete multi-step workflows:

```
/select_tests_for_scenario    — guided test selection
/create_new_test              — guided test authoring
/analyze_test_failure         — guided failure analysis
```

### Tip 6 — Dry-run flag

```
Run the runbook with dry_run=true so I can see the command without executing
```

This sets `dry_run:true` as a LISA variable (for custom use) and returns the
exact CLI command that would be executed.

---

## Reference: tool → natural language mapping

| You say | the AI calls |
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
