# Troubleshooting Guide

Solutions to the most common problems encountered when installing or using the
LISA MCP server.

---

## Table of Contents

1. [Installation problems](#1-installation-problems)
2. [MCP server connection issues](#2-mcp-server-connection-issues)
3. [Test discovery problems](#3-test-discovery-problems)
4. [Runbook issues](#4-runbook-issues)
5. [Test runner issues](#5-test-runner-issues)
6. [Result parsing issues](#6-result-parsing-issues)
7. [LISA framework errors](#7-lisa-framework-errors)
8. [WSL2-specific issues](#8-wsl2-specific-issues)
9. [Azure platform errors](#9-azure-platform-errors)
10. [Debug mode](#10-debug-mode)

---

## 1. Installation problems

---

### `pip: command not found`

```
pip: command not found
```

**Cause:** pip is not in PATH or not installed for the Python version in use.

**Fix:**
```bash
# Use python3's built-in pip module
python3 -m pip install -e .

# Or install pip
curl -sS https://bootstrap.pypa.io/get-pip.py | python3 --user
```

---

### `ModuleNotFoundError: No module named 'mcp'`

```
ModuleNotFoundError: No module named 'mcp'
```

**Cause:** The `mcp` package is not installed, or you're running under a different
Python than the one you installed into.

**Fix:**
```bash
# Check which Python is being used
which python3
python3 -c "import sys; print(sys.executable)"

# Reinstall into the correct Python
python3 -m pip install -e ~/lisa-mcp-server

# If using a venv, activate it first
source ~/lisa-mcp-server/.venv/bin/activate
```

---

### `ModuleNotFoundError: No module named 'lisa_mcp'`

**Cause:** The package isn't installed in editable mode, or the cwd is wrong.

**Fix:**
```bash
cd ~/lisa-mcp-server
pip install -e .

# Verify
python3 -c "from lisa_mcp.server import mcp; print('OK')"
```

---

### `error: metadata-generation-failed` (hatchling build error)

**Cause:** `hatchling` build backend not installed.

**Fix:**
```bash
pip install hatchling
pip install -e ~/lisa-mcp-server
```

---

### Dependency conflict with existing packages

**Fix:** Use a virtual environment to isolate:
```bash
python3 -m venv ~/lisa-mcp-server/.venv
source ~/lisa-mcp-server/.venv/bin/activate
pip install -e ~/lisa-mcp-server
```

---

## 2. MCP server connection issues

---

### the AI shows `lisa` as `disconnected`

**Cause:** The MCP server process failed to start.

**Diagnostic steps:**

**Step 1 — Run the server manually:**
```bash
python3 -m lisa_mcp.server
# or
lisa-mcp
```

Any import errors or startup failures will print here.

**Step 2 — Check the path in `mcp_servers.json`:**
```bash
cat .vscode/mcp.json
```

Make sure `cwd` is the **absolute** path to `lisa-mcp-server`, not a `~` shorthand:
```json
{
 "mcpServers": {
 "lisa": {
 "command": "python3",
 "args": ["-m", "lisa_mcp.server"],
 "cwd": "/home/kkashanjat/lisa-mcp-server" // absolute path
 }
 }
}
```

**Step 3 — Check Python path:**
```bash
which python3
# Use the full path if needed:
{
 "command": "/usr/bin/python3",
 ...
}
```

**Step 4 — Restart VS Code:**
```bash
# Close all VS Code windows, then reopen
The AI
```

---

### MCP server connects but tools return errors immediately

**Cause:** Import failure inside a tool module.

**Fix:**
```bash
python3 -c "
from lisa_mcp.tools.test_discovery import discover_tests
from lisa_mcp.tools.test_generator import generate_runbook_yaml
from lisa_mcp.tools.runbook_builder import validate_runbook
from lisa_mcp.tools.test_runner import run_tests
from lisa_mcp.tools.result_parser import parse_results
print('All tool imports OK')
"
```

If an import fails, install the missing package:
```bash
pip install <missing-package>
```

---

### `mcp_servers.json` not being read

**Cause:** Wrong file location or invalid JSON.

**Fix:**
```bash
# Validate JSON syntax
python3 -m json.tool .vscode/mcp.json

# Check file location
ls -la ~/.vscode/
```

---

## 3. Test discovery problems

---

### `ValueError: LISA path does not exist or is not a directory`

```
ValueError: LISA path does not exist or is not a directory: /path/to/lisa
```

**Cause:** The `lisa_path` argument points to a non-existent or incorrect directory.

**Fix:**
```bash
# Verify the path exists
ls ~/lisa
ls ~/lisa/lisa/microsoft/testsuites # should contain .py files

# Use the absolute path when calling the tool:
discover_test_cases(lisa_path="/home/kkashanjat/lisa")
# NOT:
discover_test_cases(lisa_path="~/lisa") # ~ not expanded in tool calls
```

---

### Discovery returns 0 test suites

**Cause:** No Python files with `@TestSuiteMetadata` found in the given path.

**Diagnostic:**
```bash
grep -r "TestSuiteMetadata" ~/lisa --include="*.py" | head -5
```

If nothing is found:
1. The LISA repo may not be fully cloned: `git clone https://github.com/microsoft/lisa ~/lisa`
2. You may be pointing at the wrong directory — try `~/lisa/lisa/microsoft/testsuites`

---

### Some test suites are missing from discovery

**Cause:** The Python files have syntax errors and are silently skipped.

**Fix:**
```bash
# Find Python files with syntax errors in the LISA repo
python3 -c "
import ast, pathlib, sys
errors = []
for f in pathlib.Path('~/lisa').expanduser().rglob('*.py'):
 if any(p in f.parts for p in ('.venv','__pycache__','build')):
 continue
 try:
 ast.parse(f.read_text(errors='replace'))
 except SyntaxError as e:
 errors.append((str(f), str(e)))
for path, err in errors:
 print(f'SYNTAX ERROR: {path}: {err}')
print(f'{len(errors)} files with syntax errors')
"
```

---

### Discovery is very slow (`/mnt/c/...` path)

**Cause:** I/O to the Windows filesystem from WSL2 is 10–50x slower than native Linux paths.

**Fix:**
```bash
# Clone the LISA repo to a WSL2-native path instead:
git clone https://github.com/microsoft/lisa ~/lisa # fast (~/)
# instead of:
# git clone https://github.com/microsoft/lisa /mnt/c/Users/you/lisa # slow
```

On a WSL2-native path, full LISA repo discovery takes ~3 seconds instead of 30–60 seconds.

---

## 4. Runbook issues

---

### `yaml.YAMLError: mapping values are not allowed here`

**Cause:** Indentation or colon in an unquoted YAML string.

**Fix:** Quote strings that contain colons:
```yaml
# BAD
description: Verifies: the disk is mounted

# GOOD
description: "Verifies: the disk is mounted"
```

---

### `validate_runbook_file` reports `"valid": false`

Read the `errors` list — each entry explains the problem:

| Error | Fix |
|-------|-----|
| `Missing required field: 'name'` | Add `name:` at the top level |
| `Invalid select_action 'inclue'` | Fix the typo: `include` |
| `'retry' must be a non-negative integer` | Use `retry: 0` not `retry: -1` |
| `Unknown platform type 'az'` | Use `azure` not `az` |

---

### Variable `$(subscription_id)` not substituted

**Cause:** The variable is not defined in the runbook and not passed via `-v`.

**Fix:**
```bash
lisa -r my_runbook.yml -v subscription_id:YOUR_SUBSCRIPTION_ID
```

or add to the runbook:
```yaml
variable:
 - name: subscription_id
 value: YOUR_SUBSCRIPTION_ID
```

---

## 5. Test runner issues

---

### `lisa executable not found`

```json
{ "stderr": "lisa executable not found. Install LISA with: pip install lisa..." }
```

**Cause:** `lisa` is not on PATH.

**Fix:**
```bash
# Install LISA
cd ~/lisa
pip install -e .

# Verify
lisa --version

# If still not found, check PATH
echo $PATH
which lisa

# Add ~/.local/bin to PATH if needed
echo 'export PATH=$PATH:~/.local/bin' >> ~/.bashrc
source ~/.bashrc
```

---

### `Timed out after 7200s`

**Cause:** The test run exceeded the default 2-hour timeout.

**Fix:** Increase `timeout_seconds`:
```python
run_lisa_tests(
 lisa_path="~/lisa",
 runbook_path="my_runbook.yml",
 timeout_seconds=14400 # 4 hours
)
```

Or reduce the number of tests (use T0 instead of T2, or fewer parallel tests).

---

### `Permission denied: ~/.ssh/id_rsa`

**Cause:** SSH key file has incorrect permissions.

**Fix:**
```bash
chmod 600 ~/.ssh/lisa_id_rsa
```

---

### Tests fail with `EnvironmentError: Failed to deploy VM`

**Cause:** Azure quota, region capacity, or credential issue.

**Fix:**
```bash
# Check Azure quota
az vm list-usage --location westus3 --output table

# Try a different region
lisa -r my_runbook.yml -v location:eastus

# Verify Azure login
az account show
```

---

## 6. Result parsing issues

---

### `FileNotFoundError: JUnit XML not found`

**Cause:** The test run didn't generate a JUnit XML file, or the path is wrong.

**Fix:**
```bash
# Check if the file exists
ls -la ./lisa_results.xml
# or wherever your runbook writes it:
ls -la ./reports/

# Make sure your runbook has the junit notifier:
notifier:
 - type: junit
 path: ./lisa_results.xml
```

---

### `ImportError: Install 'junitparser' to parse JUnit XML`

**Fix:**
```bash
pip install junitparser
```

---

### `parse_test_results` returns 0 tests from console output

**Cause:** The console output format doesn't match the expected pattern (`[PASS]`/`[FAIL]`/`[SKIP]`).

**Fix:** Use JUnit XML parsing instead — it's more reliable:
```python
parse_test_results(source="./lisa_results.xml")
```

Or pass the raw output text directly:
```python
parse_test_results(source=full_stdout_string)
```

---

## 7. LISA framework errors

---

### `ImportError: cannot import name 'TestSuiteMetadata' from 'lisa'`

**Cause:** Wrong LISA version or broken LISA installation.

**Fix:**
```bash
cd ~/lisa
git pull
pip install -e .
```

---

### `AttributeError: 'NoneType' object has no attribute 'execute'`

**Cause:** `node` is None — the test is running before the environment is deployed.

**Fix:** Add the correct `environment_status` requirement:
```python
requirement=simple_requirement(
 environment_status=EnvironmentStatus.Deployed
)
```

---

### `SkippedException: requirement not met`

**Cause:** The test's `requirement` isn't satisfied by the current environment.
This is **expected behavior** — LISA skips incompatible tests rather than failing them.

**To investigate:** Check the requirement fields on the test:
```
get_test_case_details(lisa_path="~/lisa", test_name="MyTest.my_method")
```

Look at `requirement.supported_platform_type`, `requirement.min_core_count`, etc.

---

## 8. WSL2-specific issues

---

### `Cannot connect to the Docker daemon` (if using containers)

LISA's dev container requires Docker Desktop for Windows with WSL2 backend.

**Fix:**
1. Install Docker Desktop
2. Enable "Use the WSL 2 based engine" in Docker Desktop settings
3. In WSL2: `docker ps` should work

---

### Line ending issues (`\r\n` in Python files)

**Cause:** Files checked out on Windows have CRLF line endings, which break Python imports.

**Fix:**
```bash
# Configure git to use LF on Linux
git config --global core.autocrlf input

# Fix existing files
find ~/lisa -name "*.py" -exec sed -i 's/\r$//' {} \;
```

---

### `OSError: [Errno 22] Invalid argument` when writing runbook to Windows path

**Cause:** Windows path (`/mnt/c/...`) has stricter filename restrictions.

**Fix:** Write to a WSL2-native path first, then copy:
```bash
python3 -c "
from lisa_mcp.tools.runbook_builder import write_runbook
write_runbook(yaml_str, '/home/kkashanjat/runbook.yml') # WSL native
"
cp ~/runbook.yml /mnt/c/Users/kkashanjat/runbook.yml # copy to Windows
```

---

## 9. Azure platform errors

---

### `AuthenticationError` / `AADSTS` errors

**Fix:**
```bash
az login
az account set --subscription YOUR_SUBSCRIPTION_ID
az account show # verify
```

---

### `QuotaExceeded` error

**Fix:**
```bash
# Check vCPU quota in your region
az vm list-usage --location westus3 --query "[?currentValue >= limit]" --output table

# Try a different region or smaller VM size
lisa -r my_runbook.yml -v location:eastus2
```

---

### `ImageNotFound` error

**Cause:** The marketplace image string is incorrect.

**Fix:**
```bash
# Search for correct image strings
az vm image list --publisher Canonical --offer UbuntuServer --all --output table | head -20
az vm image list --publisher RedHat --offer RHEL --all --output table | head -20

# Correct format: publisher offer sku version
# ubuntu focal 20.04-lts latest
# redhat rhel 8_5 8.5.2022012415
```

---

## 10. Debug mode

### Enable verbose output in LISA

```bash
# Maximum verbosity
lisa -r my_runbook.yml -d

# Also saves all logs to a directory
lisa -r my_runbook.yml --log-path ./debug-logs/
```

### Enable debug logging in the MCP server

```python
# At the top of server.py or in your test script:
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Diagnose MCP tool calls

In VS Code, you can ask the AI to show what tools it called:

```
What tools did you just call, with what parameters, and what did they return?
```

### Direct Python testing (bypass MCP)

Test tools directly without the AI:

```python
from lisa_mcp.tools.test_discovery import discover_tests
import json

suites = discover_tests(
 lisa_path="/home/kkashanjat/lisa",
 tier="T0",
)
for s in suites:
 print(f"{s.name}: {len(s.test_cases)} tests")
 for tc in s.test_cases:
 print(f" [{tc.priority}] {tc.name}")
```

### Minimal reproduction

To report a bug, run this and include the output:

```bash
python3 -c "
import sys, platform
print('Python:', sys.version)
print('Platform:', platform.platform())

from lisa_mcp import __version__
print('lisa-mcp version:', __version__)

import mcp
print('mcp version:', mcp.__version__ if hasattr(mcp, '__version__') else 'unknown')

import yaml
print('pyyaml:', yaml.__version__)

import pydantic
print('pydantic:', pydantic.VERSION)
"
```

---

## Getting more help

1. **Check the docs**: [INSTALL.md](../INSTALL.md), [USAGE.md](../USAGE.md), [docs/tools-reference.md](tools-reference.md)
2. **LISA documentation**: https://mslisa.readthedocs.io/
3. **LISA GitHub Issues**: https://github.com/microsoft/lisa/issues
4. **MCP documentation**: https://modelcontextprotocol.io/
