# Runbook Guide — Complete Reference

A **runbook** is the YAML configuration file that controls every aspect of a LISA
test run: which tests to execute, on which platform, with which OS image, how many
parallel environments, and where to report results.

---

## Table of Contents

1. [Runbook structure overview](#1-runbook-structure-overview)
2. [Top-level fields](#2-top-level-fields)
3. [variable — defining variables](#3-variable--defining-variables)
4. [platform — target environment](#4-platform--target-environment)
5. [testcase — selecting tests](#5-testcase--selecting-tests)
6. [notifier — reporting results](#6-notifier--reporting-results)
7. [transformer — environment setup](#7-transformer--environment-setup)
8. [combinator — grid testing](#8-combinator--grid-testing)
9. [extension — custom code](#9-extension--custom-code)
10. [include — composing runbooks](#10-include--composing-runbooks)
11. [Variable substitution](#11-variable-substitution)
12. [Running a runbook from the CLI](#12-running-a-runbook-from-the-cli)
13. [Complete annotated example](#13-complete-annotated-example)
14. [Building runbooks with the MCP server](#14-building-runbooks-with-the-mcp-server)
15. [Common runbook patterns](#15-common-runbook-patterns)

---

## 1. Runbook structure overview

```yaml
# Metadata
name: My Test Run
test_project: Linux Image Quality
test_pass: T1 BVT
concurrency: 2
exit_on_first_failure: false
import_builtin_tests: true

# Variables and secrets
variable:
 - name: location
 value: westus3
 - name: subscription_id
 value: $(subscription_id)

# Platform (where tests run)
platform:
 - type: azure
 azure:
 subscription_id: $(subscription_id)
 marketplace: ubuntu focal 20.04-lts latest

# Test selection
testcase:
 - criteria:
 priority: [0, 1]

# Output
notifier:
 - type: console
 - type: html
 path: ./report.html
 - type: junit
 path: ./results.xml
```

---

## 2. Top-level fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | required | Human-readable name for this run |
| `test_project` | string | `""` | Project label (used in reports) |
| `test_pass` | string | `""` | Test pass label (e.g. "T1 BVT") |
| `concurrency` | integer | `1` | Number of test environments to run in parallel |
| `exit_on_first_failure` | boolean | `false` | Stop run immediately on first test failure |
| `import_builtin_tests` | boolean | `true` | Include LISA's built-in test suites |
| `log_agent` | boolean | `false` | Enable AI-powered failure analysis via Azure OpenAI |

### `concurrency` guidance

```yaml
concurrency: 1 # Serial (safest, cheapest)
concurrency: 2 # Two parallel environments (2x faster, standard T1/T2 runs)
concurrency: 4 # Four parallel (fast, but more cloud cost and quota)
concurrency: 10 # High parallelism (for large-scale image testing)
```

Each concurrent "slot" can run a different test (or the same test on a different OS
if using a combinator).

---

## 3. `variable` — defining variables

Variables are referenced as `$(variable_name)` anywhere in the runbook.

```yaml
variable:
 # Simple name/value pair
 - name: location
 value: westus3

 # Value that must be passed on CLI (empty default)
 - name: subscription_id
 value: $(subscription_id)

 # Load variables from an external file (e.g. secrets)
 - file: ./secrets.yml

 # Boolean variable
 - name: use_prod
 value: false
```

### Secrets file pattern

Never commit credentials to your runbook. Use a separate file:

```yaml
# secrets.yml (add to .gitignore)
variable:
 - name: subscription_id
 value: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
 - name: admin_private_key_file
 value: /home/user/.ssh/lisa_id_rsa
```

Reference it from your main runbook:
```yaml
variable:
 - file: ./secrets.yml
```

### Overriding variables from CLI

Any variable can be overridden at run time:

```bash
lisa -r my_runbook.yml -v location:eastus2 -v subscription_id:my-id
```

---

## 4. `platform` — target environment

### Azure

```yaml
platform:
 - type: azure
 admin_private_key_file: $(admin_private_key_file) # SSH key for VM access
 azure:
 subscription_id: $(subscription_id)

 # OS image — one of these forms:
 marketplace: ubuntu focal 20.04-lts latest # Ubuntu 20.04
 marketplace: ubuntu jammy 22.04-lts latest # Ubuntu 22.04
 marketplace: redhat rhel 8_5 8.5.2022012415 # RHEL 8.5
 marketplace: debian debian-11 11 latest # Debian 11
 marketplace: microsoftcblmariner cbl-mariner 1-gen2 latest # CBL-Mariner

 # VM size (optional, LISA picks appropriate default)
 vm_size: Standard_D4s_v3

 # Location (can also be set via variable)
 location: westus3

 # Use shared image gallery instead of marketplace
 # shared_gallery: /subscriptions/.../images/myImage/versions/1.0.0
```

### HyperV

```yaml
platform:
 - type: hyperv
 hyperv:
 vhd: \\server\share\images\ubuntu-22.04.vhd
 vm_generation: 2
```

### Ready (existing VMs, no provisioning)

```yaml
platform:
 - type: ready

environment:
 environments:
 - name: existing_vm
 nodes:
 - type: remote
 address: 10.0.0.100
 username: azureuser
 private_key_file: ~/.ssh/id_rsa
```

### QEMU (local virtual machines)

```yaml
platform:
 - type: qemu
 qemu:
 image_path: /var/lib/lisa/images/ubuntu-22.04.qcow2
```

---

## 5. `testcase` — selecting tests

The `testcase` section is a list of criteria blocks. LISA evaluates them in order.

```yaml
testcase:
 - criteria:
 <filter fields>
 select_action: include # default
 retry: 0 # retry count on failure
 times: 1 # how many times to run
 timeout: 3600 # override test timeout
```

### Criteria fields

```yaml
criteria:
 name: smoke_test # match test method name (substring)
 area: network # match area name
 priority: [0, 1] # match priority (list or single value)
 tags: [sriov, performance] # match any tag
```

All specified criteria must match (AND logic). Multiple `testcase` entries are
evaluated in order (OR logic).

### `select_action` values

| Value | Behaviour |
|-------|-----------|
| `include` (default) | Add to test list |
| `exclude` | Remove from test list |
| `force-include` | Include regardless of prior exclude rules |
| `force-exclude` | Exclude regardless of prior include rules |

### Common selection patterns

#### Run all T1 tests

```yaml
testcase:
 - criteria:
 priority: [0, 1]
```

#### Run one specific test

```yaml
testcase:
 - criteria:
 name: smoke_test
```

#### Run all tests in an area

```yaml
testcase:
 - criteria:
 area: network
```

#### Run all T2 tests except stress tests

```yaml
testcase:
 - criteria:
 priority: [0, 1, 2] # T2 = P0-P2
 - criteria:
 area: stress
 select_action: exclude
```

#### Run a specific test multiple times (soak test)

```yaml
testcase:
 - criteria:
 name: nvme_io_test
 times: 10 # run 10 iterations
 retry: 2 # retry up to 2 times on failure
```

#### Retry all failed tests

```yaml
testcase:
 - criteria:
 priority: [0, 1]
 retry: 3 # retry up to 3 times on failure
```

---

## 6. `notifier` — reporting results

```yaml
notifier:
 # Console output (always recommended)
 - type: console
 log_level: INFO # DEBUG | INFO | WARNING | ERROR

 # HTML report (human-readable)
 - type: html
 path: ./reports/results.html
 auto_open: true # open in browser when done (local runs only)

 # JUnit XML (CI/CD integration)
 - type: junit
 path: ./reports/results.xml
```

### Log levels

| Level | Shows |
|-------|-------|
| `DEBUG` | Everything including node command output |
| `INFO` | Test pass/fail + key events |
| `WARNING` | Warnings and above |
| `ERROR` | Errors and failures only |

---

## 7. `transformer` — environment setup

Transformers prepare environments before tests run. The most common use is
building/deploying custom VMs.

```yaml
transformer:
 # Deploy an Azure VM from a VHD
 - type: azure_deploy
 requirement:
 azure:
 vhd: https://mystorage.blob.core.windows.net/vhds/myimage.vhd
 vm_size: Standard_D4s_v3

 # Build a VM from source (custom kernel, etc.)
 - type: azure_build_vhd
 requirement:
 azure:
 location: westus3
```

---

## 8. `combinator` — grid testing

Test the same suite against multiple OS images or configurations automatically.

```yaml
combinator:
 type: grid
 items:
 - name: marketplace
 value:
 - "ubuntu focal 20.04-lts latest"
 - "ubuntu jammy 22.04-lts latest"
 - "redhat rhel 8_5 latest"
 - "debian debian-11 11 latest"

testcase:
 - criteria:
 priority: [0, 1]
```

This creates one test run per image in the list. With `concurrency: 4`, up to 4
images are tested in parallel.

---

## 9. `extension` — custom code

Load custom test suites or tools from outside the main LISA repo:

```yaml
extension:
 - name: my_custom_tests
 path: /home/user/my-lisa-extensions
```

All test suites found in the extension path are loaded alongside built-in ones.

---

## 10. `include` — composing runbooks

Split large runbooks into reusable pieces:

```yaml
# azure_t1.yml
include:
 - path: ./common_variables.yml
 - path: ./azure_platform.yml

testcase:
 - criteria:
 priority: [0, 1]
```

```yaml
# common_variables.yml
variable:
 - name: location
 value: westus3
 - name: concurrency
 value: 2
```

---

## 11. Variable substitution

### Syntax

```yaml
value: $(variable_name)
```

### Resolution order

1. CLI `-v name:value` overrides (highest priority)
2. `variable:` blocks defined in the runbook
3. Variables loaded from `file:` blocks
4. Environment variables (if configured)

### Escaping

To use a literal `$(...)` string without substitution:
```yaml
value: "$$(not_a_variable)" # produces: $(not_a_variable)
```

---

## 12. Running a runbook from the CLI

```bash
# Basic run
lisa -r my_runbook.yml

# With variable overrides
lisa -r my_runbook.yml \
 -v subscription_id:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
 -v admin_private_key_file:~/.ssh/lisa_id_rsa \
 -v location:eastus

# Debug mode (verbose output)
lisa -r my_runbook.yml -d

# Run a specific test by name override
lisa -r my_runbook.yml -v "name:smoke_test"

# Run a specific tier
lisa -r my_runbook.yml -v tier:T0
```

### CLI flag reference

| Flag | Description |
|------|-------------|
| `-r <path>` | Runbook file path (required) |
| `-v name:value` | Override a variable |
| `-d` | Debug mode (very verbose) |
| `--log-path <dir>` | Directory for log files |

---

## 13. Complete annotated example

```yaml
# ============================================================
# azure_t2_rhel9.yml
# T2 test run for RHEL 9 on Azure, East US
# ============================================================

name: RHEL 9 T2 Validation
test_project: RHEL Certification
test_pass: T2 Weekly Regression
concurrency: 2
exit_on_first_failure: false
import_builtin_tests: true

# --- Variables ---
variable:
 # These must be passed via -v on the CLI or set in secrets.yml
 - name: subscription_id
 value: $(subscription_id)
 - name: admin_private_key_file
 value: $(admin_private_key_file)
 # These have defaults you can override
 - name: location
 value: eastus
 - name: vm_size
 value: Standard_D4s_v3

# --- Platform ---
platform:
 - type: azure
 admin_private_key_file: $(admin_private_key_file)
 azure:
 subscription_id: $(subscription_id)
 location: $(location)
 vm_size: $(vm_size)
 # RHEL 9 latest from Red Hat
 marketplace: redhat rhel 9_0 9.0.2022053014

# --- Test selection (T2 = P0 + P1 + P2) ---
testcase:
 # Include all P0–P2 tests
 - criteria:
 priority: [0, 1, 2]
 # Exclude known-flaky network stress test
 - criteria:
 name: network_flood_test
 select_action: exclude
 # Always include smoke test (even if excluded by other rules)
 - criteria:
 name: smoke_test
 select_action: force-include

# --- Reporting ---
notifier:
 - type: console
 log_level: INFO
 - type: html
 path: ./reports/rhel9_t2_results.html
 auto_open: false
 - type: junit
 path: ./reports/rhel9_t2_results.xml
```

Run it:

```bash
lisa -r azure_t2_rhel9.yml \
 -v subscription_id:$SUBSCRIPTION_ID \
 -v admin_private_key_file:~/.ssh/lisa_id_rsa
```

---

## 14. Building runbooks with the MCP server

### Using Azure OpenAI

```
Build a T2 Azure runbook for RHEL 9 in East US with:
- 2 concurrent environments
- JUnit and HTML output
- Exclude any stress tests
Save it to ~/runbooks/rhel9_t2.yml
```

The AI calls `build_runbook(...)` with all the right parameters.

### Using the Python API directly

```python
from lisa_mcp.tools.test_generator import generate_runbook_yaml
from lisa_mcp.tools.runbook_builder import write_runbook

yaml_str = generate_runbook_yaml(
 name="RHEL 9 T2 Validation",
 platform_type="azure",
 tier="T2",
 excluded_names=["network_flood_test"],
 image="redhat rhel 9_0 9.0.2022053014",
 location="eastus",
 concurrency=2,
 notifiers=["html", "junit"],
)

write_runbook(yaml_str, "~/runbooks/rhel9_t2.yml")
```

### Validating a runbook

```
Validate ~/runbooks/rhel9_t2.yml before I run it
```

The AI calls `validate_runbook_file(runbook_path="~/runbooks/rhel9_t2.yml")`.

---

## 15. Common runbook patterns

### Pattern 1 — Pre-merge T0 gate

```yaml
name: Pre-Merge T0 Gate
concurrency: 1
exit_on_first_failure: true # fail fast
testcase:
 - criteria:
 priority: [0] # P0 only
```

### Pattern 2 — Nightly T1 CI

```yaml
name: Nightly T1
concurrency: 2
testcase:
 - criteria:
 priority: [0, 1]
notifier:
 - type: junit
 path: /ci/artifacts/results.xml
```

### Pattern 3 — Multi-distro grid test

```yaml
name: Multi-Distro T1
concurrency: 4
combinator:
 type: grid
 items:
 - name: marketplace
 value:
 - "ubuntu focal 20.04-lts latest"
 - "ubuntu jammy 22.04-lts latest"
 - "redhat rhel 8_5 latest"
testcase:
 - criteria:
 priority: [0, 1]
```

### Pattern 4 — Targeted feature test

```yaml
name: NVMe Feature Validation
concurrency: 1
testcase:
 - criteria:
 area: nvme
```

### Pattern 5 — Performance benchmarking

```yaml
name: Storage Performance
concurrency: 1
testcase:
 - criteria:
 area: perf_storage
 times: 3 # run 3 times for stable averages
 retry: 1
```
