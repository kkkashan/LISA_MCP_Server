# MCP Tools Reference — LISA MCP Server

Complete reference for all 13 tools, 3 resources, and 3 prompts exposed by the server.

---

## Table of Contents

- [Tools](#tools)
  - [discover_test_cases](#1-discover_test_cases)
  - [list_test_areas](#2-list_test_areas)
  - [get_test_case_details](#3-get_test_case_details)
  - [search_tests](#4-search_tests)
  - [generate_test_suite_code](#5-generate_test_suite_code)
  - [build_runbook](#6-build_runbook)
  - [build_tier_runbook_file](#7-build_tier_runbook_file)
  - [validate_runbook_file](#8-validate_runbook_file)
  - [add_test_to_existing_runbook](#9-add_test_to_existing_runbook)
  - [run_lisa_tests](#10-run_lisa_tests)
  - [parse_test_results](#11-parse_test_results)
  - [check_lisa_environment](#12-check_lisa_environment)
  - [get_tier_info](#13-get_tier_info)
- [Resources](#resources)
- [Prompts](#prompts)

---

## Tools

---

### 1. `discover_test_cases`

Scan a LISA repository and return all matching test suites and test cases.

Uses **Python AST parsing** — never imports LISA modules, so no LISA installation is required.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `lisa_path` | string | yes | — | Absolute path to the LISA repository root |
| `area` | string | no | `null` | Filter by functional area (e.g. `"network"`, `"storage"`) |
| `tier` | string | no | `null` | Filter by tier `"T0"`–`"T4"` (maps to priority ranges) |
| `priority` | integer | no | `null` | Filter by exact priority level 0–5 |
| `platform` | string | no | `null` | Filter by supported platform (`"azure"`, `"hyperv"`) |
| `name_pattern` | string | no | `null` | Substring or glob matched against test name and description |
| `max_results` | integer | no | `200` | Maximum number of test cases to return |

#### Returns

JSON object:
```json
{
  "total_suites": 3,
  "total_test_cases": 18,
  "truncated": false,
  "filters": { "area": "network", "tier": "T1", ... },
  "suites": [
    {
      "suite": "NetworkConnectivity",
      "area": "network",
      "category": "functional",
      "description": "...",
      "owner": "Microsoft",
      "file": "/home/user/lisa/lisa/microsoft/testsuites/network.py",
      "test_cases": [
        {
          "name": "NetworkConnectivity.verify_ping",
          "method": "verify_ping",
          "priority": 0,
          "description": "Verifies ICMP connectivity",
          "timeout": 300,
          "use_new_environment": false,
          "requirement": {
            "min_core_count": null,
            "supported_features": [],
            "unsupported_os": [],
            "supported_platform_type": ["AZURE"]
          },
          "tags": []
        }
      ]
    }
  ]
}
```

#### Notes

- `tier` takes precedence over `priority` if both are given
- `name_pattern` is matched case-insensitively against both `name` and `description`
- Files in `.venv`, `__pycache__`, `build`, `dist`, `.git` are skipped
- Setting `max_results=0` returns all results (use with caution on large repos)

---

### 2. `list_test_areas`

Return all unique functional area names in a LISA repository.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `lisa_path` | string | yes | Absolute path to the LISA repository root |

#### Returns

```json
{
  "areas": ["cpu", "core", "hyperv", "memory", "network", "nvme", "storage", ...],
  "count": 18
}
```

#### Notes

Areas are derived from the `area=` argument in `@TestSuiteMetadata`. They correspond to
functional domains within Linux testing (not directory names).

---

### 3. `get_test_case_details`

Return full metadata for a single test case by name.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `lisa_path` | string | yes | Absolute path to the LISA repository root |
| `test_name` | string | yes | Full name (`SuiteName.method_name`) or just `method_name` |

#### Returns

Full `TestCaseInfo` JSON (all fields) on success, or:
```json
{ "error": "Test case 'foo' not found in /path/to/lisa" }
```

#### Example

```
get_test_case_details(
    lisa_path="~/lisa",
    test_name="Provisioning.smoke_test"
)
```

Returns:
```json
{
  "name": "Provisioning.smoke_test",
  "method_name": "smoke_test",
  "suite_name": "Provisioning",
  "file_path": "/home/user/lisa/lisa/microsoft/testsuites/provisioning.py",
  "area": "provisioning",
  "category": "functional",
  "description": "Verifies the VM is accessible and operational after deployment",
  "priority": 0,
  "timeout": 3600,
  "use_new_environment": false,
  "requirement": {
    "min_core_count": null,
    "min_memory_mb": null,
    "min_disk_space_gb": null,
    "supported_features": [],
    "unsupported_os": [],
    "supported_platform_type": ["AZURE"],
    "environment_status": "Deployed"
  },
  "tags": [],
  "owner": "Microsoft"
}
```

---

### 4. `search_tests`

Free-text search across test case names and descriptions with relevance scoring.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `lisa_path` | string | yes | — | Absolute path to the LISA repository root |
| `query` | string | yes | — | Search string |
| `area` | string | no | `null` | Narrow to a specific area before searching |
| `tier` | string | no | `null` | Narrow to a tier before searching |
| `max_results` | integer | no | `50` | Maximum results to return |

#### Returns

```json
{
  "query": "nvme performance",
  "total_matches": 7,
  "results": [
    {
      "name": "NvmeTest.nvme_basic_io",
      "suite": "NvmeTest",
      "area": "nvme",
      "priority": 1,
      "description": "Verifies NVMe disk basic I/O operations and throughput",
      "file": "/home/user/lisa/lisa/microsoft/testsuites/nvme.py",
      "score": 5
    },
    ...
  ]
}
```

#### Scoring

Results are sorted by descending score, then ascending priority:
- `+3` — query appears in the test name
- `+2` — query appears in the description
- `+1` — query appears in the area name

---

### 5. `generate_test_suite_code`

Generate complete, ready-to-use Python source code for a new LISA test suite.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `suite_class_name` | string | yes | PascalCase class name, e.g. `"KvpTests"` |
| `area` | string | yes | Functional area, e.g. `"hyperv"` |
| `category` | string | yes | `"functional"` \| `"performance"` \| `"stress"` \| `"community"` |
| `description` | string | yes | Human-readable description of the suite |
| `owner` | string | yes | Owner or team name |
| `test_cases` | list | yes | List of test case definition dicts (see below) |
| `output_path` | string | no | If given, write generated code to this file path |

##### `test_cases` list item fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `method_name` | string | yes | — | Python method name (snake_case) |
| `description` | string | yes | — | Test description |
| `priority` | integer | no | `2` | Priority 0–5 |
| `timeout` | integer | no | `3600` | Timeout in seconds |
| `use_new_environment` | boolean | no | `false` | Deploy fresh VM just for this test |
| `requirement` | dict | no | `{}` | Requirement fields (see below) |
| `body_lines` | list[string] | no | default stub | Python lines for the test body |

##### `requirement` dict fields

| Field | Type | Description |
|-------|------|-------------|
| `min_core_count` | integer | Minimum vCPU count |
| `min_memory_mb` | integer | Minimum RAM in MB |
| `min_disk_space_gb` | integer | Minimum disk in GB |
| `supported_features` | list[string] | Required features, e.g. `["SerialConsole", "Nvme"]` |
| `unsupported_os` | list[string] | Excluded OSes, e.g. `["BSD", "Windows"]` |
| `supported_platform_type` | list[string] | Platforms, e.g. `["AZURE", "HYPERV"]` |
| `environment_status` | string | e.g. `"Deployed"` |

#### Returns

JSON with `code` (the Python source string) and optionally `written_to` (the path written):

```json
{
  "code": "# Generated test suite file: kvptests.py\n..."
}
```

---

### 6. `build_runbook`

Generate a complete LISA runbook YAML configuration file.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | string | yes | — | Human-readable runbook name |
| `platform_type` | string | no | `"azure"` | `"azure"` \| `"hyperv"` \| `"ready"` \| `"qemu"` \| `"baremetal"` |
| `tier` | string | no | `null` | `"T0"`–`"T4"` shortcut for priority filter |
| `test_names` | list[string] | no | `null` | Specific test names to include |
| `excluded_names` | list[string] | no | `null` | Test names to exclude |
| `priorities` | list[int] | no | `null` | Explicit priority list, e.g. `[0, 1]` |
| `variables` | dict | no | `null` | Additional variable key→value pairs |
| `notifiers` | list[string] | no | `null` | `"html"` and/or `"junit"` (console is always on) |
| `image` | string | no | `"ubuntu focal 20.04-lts latest"` | Marketplace image string |
| `location` | string | no | `"westus3"` | Azure region |
| `concurrency` | integer | no | `1` | Parallel test environments |
| `output_path` | string | no | `null` | Write YAML to this file path |

#### Returns

```json
{
  "yaml": "# LISA Runbook...\nname: ...\n...",
  "written_to": "/home/user/runbooks/my_runbook.yml"  // if output_path given
}
```

---

### 7. `build_tier_runbook_file`

One-step convenience: build a standard T0–T4 tier runbook with sensible defaults.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `tier` | string | yes | — | `"T0"`, `"T1"`, `"T2"`, `"T3"`, or `"T4"` |
| `platform_type` | string | no | `"azure"` | Platform type |
| `output_path` | string | no | `null` | Write to this path |
| `image` | string | no | `"ubuntu focal 20.04-lts latest"` | OS image |
| `extra_variables` | dict | no | `null` | Extra variable overrides |

#### Returns

```json
{
  "tier": "T1",
  "yaml": "...",
  "written_to": "/path/if/output_path/given"
}
```

---

### 8. `validate_runbook_file`

Parse and validate a LISA runbook YAML file for errors and warnings.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `runbook_path` | string | yes | Path to the runbook YAML file |

#### Returns

```json
{
  "valid": true,
  "errors": [],
  "warnings": [
    "Variable '$(subscription_id)' referenced but not defined — pass via -v on the CLI."
  ],
  "summary": {
    "name": "My Runbook",
    "concurrency": 2,
    "platform_types": ["azure"],
    "test_criteria_count": 2,
    "variable_count": 1,
    "notifiers": ["console", "html"],
    "import_builtin_tests": true
  }
}
```

#### What is validated

- YAML syntax
- Top-level mapping structure
- `name` field presence
- Platform type against known values
- `select_action` values against valid set
- `retry` field type
- `$(variable_name)` reference resolution (warns on undefined refs)

---

### 9. `add_test_to_existing_runbook`

Add a test inclusion or exclusion criterion to an existing runbook file in-place.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `runbook_path` | string | yes | — | Path to the existing runbook YAML |
| `test_name` | string | yes | — | Test name (or substring) to match |
| `select_action` | string | no | `"include"` | `"include"` \| `"exclude"` \| `"force-include"` \| `"force-exclude"` |

#### Returns

```json
{
  "message": "Added 'smoke_test' (include) to ~/my_runbook.yml",
  "yaml": "... updated YAML content ..."
}
```

#### `select_action` values explained

| Value | Behaviour |
|-------|-----------|
| `include` | Add to run if criteria match |
| `exclude` | Remove from run if criteria match |
| `force-include` | Include even if another rule excluded it |
| `force-exclude` | Exclude even if another rule included it |

---

### 10. `run_lisa_tests`

Execute LISA tests by running the `lisa` CLI as a subprocess.

> **This tool can deploy real cloud infrastructure. Confirm before calling.**

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `lisa_path` | string | yes | — | LISA repository root (used as working directory) |
| `runbook_path` | string | yes | — | Path to the runbook YAML |
| `variables` | dict | no | `null` | CLI variable overrides (`-v name:value`) |
| `dry_run` | boolean | no | `false` | Adds `dry_run:true` variable (informational) |
| `timeout_seconds` | integer | no | `7200` | Subprocess timeout (2 hours default) |

#### Returns

```json
{
  "success": true,
  "returncode": 0,
  "stdout": "... full LISA output ...",
  "stderr": "",
  "command": "lisa -r ~/my_runbook.yml -v subscription_id:xxxx ..."
}
```

#### Error cases

| Scenario | `success` | `stderr` |
|----------|-----------|---------|
| Tests pass | `true` | `""` |
| Some tests fail | `false` | `""` |
| Timeout | `false` | `"Timed out after 7200s"` |
| LISA not installed | `false` | `"lisa executable not found..."` |

---

### 11. `parse_test_results`

Parse LISA test output from a JUnit XML file or raw console text.

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `source` | string | yes | File path (JUnit XML) **or** raw console output string |

Auto-detection:
- If `source` is a file path ending in `.xml` or `.junit` → parse as JUnit XML
- Otherwise → parse as console output text

#### Returns

```json
{
  "summary_line": "Total: 45 | Passed: 42 (93.3%) | Failed: 3 | Skipped: 0 | Errors: 0 | Duration: 312.5s",
  "total": 45,
  "passed": 42,
  "failed": 3,
  "skipped": 0,
  "errors": 0,
  "duration_seconds": 312.5,
  "results": [
    {
      "name": "StorageVerification.nvme_io_test",
      "status": "failed",
      "duration_seconds": 120.5,
      "message": "Expected exit code 0 but got 1",
      "stack_trace": "...",
      "suite_name": "StorageVerification"
    },
    ...
  ]
}
```

#### Status values

| Status | Meaning |
|--------|---------|
| `passed` | Test completed successfully |
| `failed` | Test assertion or command failed |
| `skipped` | Test was skipped (e.g. requirement not met) |
| `error` | Infrastructure or framework error during test |

---

### 12. `check_lisa_environment`

Check whether the LISA CLI (`lisa`) is installed and available.

#### Parameters

None.

#### Returns

```json
// LISA installed:
{
  "installed": true,
  "path": "/home/user/.local/bin/lisa",
  "version_output": "LISA v0.1.0"
}

// LISA not installed:
{
  "installed": false,
  "path": null,
  "version_output": ""
}
```

---

### 13. `get_tier_info`

Return the definition and use-case for each LISA test tier (T0–T4).

#### Parameters

None.

#### Returns

```json
{
  "T0": {
    "priorities": [0],
    "description": "P0 (critical) tests only — smoke tests, ~5 minutes, 1 environment",
    "use_case": "Fast gate-check before merge or image publishing"
  },
  "T1": {
    "priorities": [0, 1],
    "description": "P0–P1 tests — ~2 hours, up to 2 environments",
    "use_case": "Daily CI runs and pre-release validation"
  },
  "T2": {
    "priorities": [0, 1, 2],
    "description": "P0–P2 tests — ~8 hours, up to 2 environments",
    "use_case": "Weekly regression suites"
  },
  "T3": {
    "priorities": [0, 1, 2, 3],
    "description": "P0–P3 tests — ~16 hours",
    "use_case": "Full pre-GA validation"
  },
  "T4": {
    "priorities": [0, 1, 2, 3, 4, 5],
    "description": "All tests including community/informational",
    "use_case": "Complete compliance and certification runs"
  }
}
```

---

## Resources

Resources are static reference material accessible at fixed URIs.

### `lisa://test-case-template`

A minimal annotated Python code snippet for a single test case method.
Paste it inside a class decorated with `@TestSuiteMetadata`.

```
Read resource: lisa://test-case-template
```

### `lisa://test-suite-template`

A complete, minimal Python source file for a new LISA test suite with imports,
suite class, one test case, and before/after_case hooks.

```
Read resource: lisa://test-suite-template
```

### `lisa://runbook-template`

A minimal YAML runbook template with all major sections commented.
A good starting point for hand-editing.

```
Read resource: lisa://runbook-template
```

---

## Prompts

Prompts trigger multi-step the AI workflows with a single command.

### `select_tests_for_scenario`

Helps you choose appropriate tests and build a runbook for a specific validation goal.

**Parameters:**
- `scenario` — what you want to validate (e.g. `"network performance under load"`)
- `platform` — target platform (default `"azure"`)
- `os_name` — target OS (default `"Ubuntu"`)

**Workflow triggered:**
1. Searches LISA for relevant tests
2. Filters by platform and OS compatibility
3. Recommends a tier
4. Builds a ready-to-run runbook

---

### `create_new_test`

Guides you through writing a new LISA test case from scratch.

**Parameters:**
- `feature_name` — the feature being tested (e.g. `"Hyper-V socket"`)
- `area` — LISA area (e.g. `"hyperv"`)
- `what_to_validate` — what the test should check

**Workflow triggered:**
1. Explains priority levels and asks you to choose
2. Generates test suite Python source
3. Explains the test logic
4. Shows how to add to a runbook

---

### `analyze_test_failure`

Root-causes a test failure from output text.

**Parameters:**
- `failure_output` — the stdout/stderr or error log from a failed LISA run

**Workflow triggered:**
1. Parses structured failure data
2. Identifies root cause categories (configuration, test code, infrastructure, timeout)
3. Proposes fixes
4. Offers corrected runbook or test code if appropriate
