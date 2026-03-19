# Running LISA: Step-by-Step Guide

This guide walks you through every step needed to run Microsoft LISA tests — from a fresh machine to viewing results — including the full LLM-powered analysis pipeline.

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Ubuntu 20.04+ (or WSL2) | LISA is Linux-native |
| Python 3.10+ | `python3 --version` to check |
| Azure subscription | For cloud-based VM tests |
| SSH key pair | For authenticating to test VMs |
| Azure OpenAI API key | Optional — only for LLM analysis |

---

## Step 1 — Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y \
 python3 python3-pip python3-venv \
 git curl openssh-client \
 libssl-dev libffi-dev build-essential
```

Install the Azure CLI (needed for cloud tests):

```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

Verify installs:

```bash
python3 --version # Python 3.10+
az --version # azure-cli 2.x
git --version
```

---

## Step 2 — Clone the LISA Repository

```bash
git clone https://github.com/microsoft/lisa.git
cd lisa
```

---

## Step 3 — Create a Virtual Environment and Install LISA

```bash
# Create venv inside the repo
python3 -m venv .venv
source .venv/bin/activate

# Install LISA in editable mode (+ extras)
pip install --upgrade pip
pip install -e ".[azure]"
```

> **Tip**: The `[azure]` extra pulls in `azure-identity`, `azure-mgmt-compute`, and other Azure SDK packages needed for cloud tests.

Verify the install:

```bash
lisa --help
```

You should see the LISA CLI help output.

---

## Step 4 — Generate an SSH Key Pair

LISA uses SSH to connect to test VMs. Create a dedicated key pair:

```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/lisa_id_rsa -N ""
```

This creates two files:
- `~/.ssh/lisa_id_rsa` — private key (keep secret)
- `~/.ssh/lisa_id_rsa.pub` — public key (given to VMs by LISA automatically)

---

## Step 5 — Set Up Azure Credentials

Log in to Azure:

```bash
az login
```

List your subscriptions and note the ID you want to use:

```bash
az account list --output table
az account set --subscription "YOUR_SUBSCRIPTION_ID"
```

Export for use in scripts:

```bash
export AZURE_SUBSCRIPTION_ID="YOUR_SUBSCRIPTION_ID"
```

---

## Step 6 — Create Your First Runbook

A **runbook** is a YAML file that tells LISA what to test, where to run it, and how to configure the environment.

Create `my_first_runbook.yml`:

```yaml
name: my_first_run
description: "First LISA test run on Azure"

extension:
 - name: lisa.microsoft.azure

platform:
 - type: azure
 admin_username: lisauser
 admin_private_key_file: "~/.ssh/lisa_id_rsa"
 subscription_id: "$(subscription_id)" # passed via -v flag
 resource_group_name: "lisa-test-rg"
 location: "eastus"
 vm_type: "Standard_D2s_v3"

testcase:
 - criteria:
 priority: 0 # P0 = most critical smoke tests
 area: smoke # only the smoke area
```

> See [docs/runbook-guide.md](runbook-guide.md) for the full YAML reference and all available options.

---

## Step 7 — Run the Tests

Basic run command:

```bash
lisa -r my_first_runbook.yml \
 -v subscription_id:"$AZURE_SUBSCRIPTION_ID"
```

### What happens during a run

1. LISA provisions one or more Azure VMs matching your runbook spec
2. Copies the test suite Python files to the VM
3. SSH-connects and executes each test case
4. Collects logs, dmesg, journalctl output
5. Teardowns and deletes VMs (unless `keep_environment: true`)
6. Writes results to `runtime/` directory

### Useful run flags

| Flag | Description |
|------|-------------|
| `-r <runbook>` | Path to runbook YAML |
| `-v key:value` | Override/inject variables |
| `-d` | Debug logging (very verbose) |
| `--log-level WARNING` | Quieter output |
| `-e <extension>` | Load extra extension |

---

## Step 8 — View the Results

### Console output

LISA prints a live table to stdout:

```
┌───────────────────────────────────────────────────────┐
│ Test Results │
│ Passed: 18 Failed: 2 Skipped: 3 Total: 23 │
└───────────────────────────────────────────────────────┘
```

### Results directory

After the run, find everything under `runtime/`:

```
runtime/
├── <run-id>/
│ ├── lisa.log # main LISA log
│ ├── environment/
│ │ └── <env-id>/
│ │ ├── setup.log
│ │ └── <test-name>/
│ │ ├── test.log # per-test logs
│ │ └── results.xml # JUnit XML
│ └── report/
│ └── junit.xml # aggregate JUnit report
```

Open the JUnit XML in any CI system or IDE test reporter.

### HTML report (via MCP)

If you are using the LISA MCP server, generate an HTML report:

```python
# In your MCP client (e.g., the AI Desktop)
analyze_test_run_with_llm(
 junit_xml_path="runtime/<run-id>/report/junit.xml",
 log_dir="runtime/<run-id>",
 api_key="YOUR_AZURE_OPENAI_API_KEY",
 output_dir="reports/"
)
```

This produces `reports/report.html` and `reports/report.md`.

---

## Step 9 — Common Run Variations

### Run a single specific test

```bash
lisa -r my_first_runbook.yml \
 -v subscription_id:"$AZURE_SUBSCRIPTION_ID" \
 -v "testcase.0.criteria.name:verify_disk_io"
```

### Run a different OS image

Add image override:

```bash
lisa -r my_first_runbook.yml \
 -v subscription_id:"$AZURE_SUBSCRIPTION_ID" \
 -v "platform.0.marketplace_image:Canonical UbuntuServer 22_04-lts-gen2 latest"
```

### Run a different tier

Change priority in the runbook or override:

```bash
# Run T1 (P0+P1) tests
lisa -r my_first_runbook.yml \
 -v subscription_id:"$AZURE_SUBSCRIPTION_ID" \
 -v "testcase.0.criteria.priority:[0,1]"
```

### Debug mode — keep VM alive after failure

```yaml
# In runbook
keep_environment: failed
```

Then SSH in manually to investigate:

```bash
ssh -i ~/.ssh/lisa_id_rsa lisauser@<VM_PUBLIC_IP>
```

The VM IP is printed in `runtime/<run-id>/lisa.log`.

---

## Step 10 — Use LISA's Built-In Runbooks

LISA ships with ready-made runbooks for common scenarios:

```bash
# List built-in runbooks
ls microsoft/runbook/

# Examples:
microsoft/runbook/azure_tier0.yml # P0 smoke tests on Azure
microsoft/runbook/azure_tier1.yml # P0+P1 tests on Azure
microsoft/runbook/stress.yml # stress/performance tests
```

Run a built-in runbook:

```bash
lisa -r microsoft/runbook/azure_tier0.yml \
 -v subscription_id:"$AZURE_SUBSCRIPTION_ID"
```

---

## Step 11 — Use a Secrets File (Recommended)

Avoid passing sensitive values on the command line. Create `secrets.yml` (never commit this):

```yaml
# secrets.yml — DO NOT COMMIT
subscription_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
admin_private_key_file: "~/.ssh/lisa_id_rsa"
azure_openai_api_key: "YOUR_AZURE_OPENAI_API_KEY"
```

Run with the secrets file:

```bash
lisa -r my_first_runbook.yml -r secrets.yml
```

LISA merges multiple runbooks — later files override earlier ones.

Add to `.gitignore`:

```
secrets.yml
*.secret.yml
```

---

## Step 12 — End-to-End with MCP + LLM Analysis

After running LISA, use the MCP server to get AI-powered failure analysis:

### 1. Start the MCP server

```bash
source .venv/bin/activate
pip install lisa-mcp-server
lisa-mcp
```

### 2. Connect your MCP client (the AI Desktop)

Add to `.vscode/mcp.json`:

```json
{
 "mcpServers": {
 "lisa": {
 "command": "lisa-mcp",
 "args": []
 }
 }
}
```

### 3. Run analysis from the AI Desktop

Tell the AI:

> "Analyze the LISA test run at `runtime/2024-01-15_10-30-00/report/junit.xml` with logs at `runtime/2024-01-15_10-30-00/`. My Azure OpenAI API key is YOUR_AZURE_OPENAI_API_KEY"

The AI will invoke the MCP tools to:
- Parse the JUnit XML for failures
- Collect relevant log snippets for each failed test
- Call the AI API for per-test root cause analysis
- Generate a run-level summary with priorities
- Save HTML + Markdown reports to disk

---

## Quick Reference Cheatsheet

```bash
# 1. Activate venv
source .venv/bin/activate

# 2. Verify LISA is available
lisa --help

# 3. Run P0 smoke tests
lisa -r microsoft/runbook/azure_tier0.yml \
 -v subscription_id:"$AZURE_SUBSCRIPTION_ID"

# 4. Run specific test
lisa -r my_runbook.yml -v "testcase.0.criteria.name:verify_network_basic"

# 5. Keep VM alive on failure for debugging
lisa -r my_runbook.yml -v keep_environment:failed

# 6. View results directory
ls runtime/

# 7. Get full run path
LATEST=$(ls -td runtime/*/ | head -1)
cat "$LATEST/lisa.log" | grep -E "PASS|FAIL|SKIP"
```

---

## Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| `lisa: command not found` | Venv not activated | `source .venv/bin/activate` |
| `Authentication failed` | SSH key mismatch | Verify `admin_private_key_file` path in runbook |
| `QuotaExceeded` | Azure quota hit | Try a different region or smaller `vm_type` |
| `ModuleNotFoundError: azure` | Missing Azure extras | `pip install -e ".[azure]"` |
| `Connection timed out` | NSG blocking SSH (port 22) | Check Azure NSG rules for the resource group |
| Tests skipped unexpectedly | Node requirements not met | Check `@TestCaseMetadata(requirement=...)` for the test |
| `lisa.log` says `SKIPPED: environment not ready` | Setup phase failed | Read `environment/<env-id>/setup.log` for details |
| LLM analysis `AuthenticationError` | Bad API key | Verify `azure_openai_api_key` is correct and has credits |

---

## Related Documentation

- [QUICKSTART.md](../QUICKSTART.md) — 6-step getting started
- [docs/runbook-guide.md](runbook-guide.md) — Full runbook YAML reference
- [docs/writing-tests.md](writing-tests.md) — How to write LISA test cases
- [docs/llm-analysis.md](llm-analysis.md) — LLM analysis pipeline details
- [docs/troubleshooting.md](troubleshooting.md) — 30+ common errors with fixes
- [LISA official docs](https://github.com/microsoft/lisa/blob/main/docs/README.md)
