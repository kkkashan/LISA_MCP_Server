# Quickstart — LISA MCP Server

Get from zero to AI-powered LISA testing in 10 minutes.

---

## Prerequisites

- Python 3.10 or later
- Git
- VS Code with GitHub Copilot (or any MCP-compatible client)

---

## Step 1 — Clone both repositories

```bash
# Clone the LISA framework (the test suite library)
git clone https://github.com/microsoft/lisa.git ~/lisa

# Clone this MCP server
git clone https://github.com/kkkashan/LISA_MCP_Server.git ~/lisa-mcp-server
```

---

## Step 2 — Install the MCP server

```bash
cd ~/lisa-mcp-server
pip install -e .
```

Verify the install:

```bash
python3 -c "from lisa_mcp.server import mcp; print('OK —', mcp.name)"
# OK — lisa-mcp-server
```

---

## Step 3 — Register with VS Code

The repo ships with `.vscode/mcp.json` pre-configured. Open the workspace in
VS Code and it will detect the MCP server automatically.

If you need to set the path manually, edit `.vscode/mcp.json`:

```json
{
 "servers": {
 "lisa": {
 "command": "python3",
 "args": ["-m", "lisa_mcp.server"],
 "cwd": "/absolute/path/to/lisa-mcp-server"
 }
 }
}
```

Get your absolute path with:

```bash
cd ~/lisa-mcp-server && pwd
```

---

## Step 4 — Start the server

In VS Code, open the Command Palette → **MCP: Start Server** → select **lisa**.

Or click the **Start** button that appears above the server entry in `.vscode/mcp.json`.

---

## Step 5 — Your first commands

Open GitHub Copilot Chat (or your MCP client) and try:

### 5a. Check what test areas exist

```
Show me all the functional areas in my LISA repo at ~/lisa
```

The AI calls `list_test_areas(lisa_path="~/lisa")` and returns:

```
network, storage, cpu, memory, nvme, core, provisioning, hyperv, ...
```

### 5b. Discover tests by tier

```
Show me all priority-0 (T0) tests in the network area of ~/lisa
```

The AI calls `discover_test_cases(lisa_path="~/lisa", area="network", tier="T0")`.

### 5c. Build a runbook

```
Build a T1 Azure runbook for Ubuntu 22.04 LTS and save it to ~/my_runbook.yml
```

The AI calls `build_tier_runbook_file(tier="T1", platform_type="azure", output_path="~/my_runbook.yml")`.

### 5d. Generate a new test suite

```
Write a LISA test suite called "KernelSmokeTest" in the "cpu" area
that checks the kernel version is at least 5.15. Priority 0, Azure only.
```

The AI calls `generate_test_suite_code(...)` and returns complete Python source.

---

## Step 6 — Run tests (requires LISA + Azure credentials)

Install LISA itself:

```bash
cd ~/lisa
pip install -e .
lisa --version
```

Then ask:

```
Run the runbook at ~/my_runbook.yml using the LISA repo at ~/lisa.
Pass subscription_id:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
and admin_private_key_file:~/.ssh/id_rsa
```

The AI calls `run_lisa_tests(...)` and returns stdout/stderr + exit code.

---

## Step 7 — Analyze failures with Azure OpenAI (optional)

If tests fail, get AI-powered root cause analysis:

```
Analyze the failures in ~/lisa/lisa_results.xml
Azure OpenAI key: <your-key>
Save the report to ~/reports/
```

The AI calls `generate_analysis_report(...)` and produces an HTML + Markdown report.

> **Azure OpenAI endpoint (pre-configured):**
> `https://kkopenailearn.openai.azure.com/openai/responses?api-version=2025-04-01-preview`
> Pass your API key when calling any `analyze_*` tool.

---

## What's next?

- [INSTALL.md](INSTALL.md) — detailed installation for Windows/WSL/Linux/macOS
- [USAGE.md](USAGE.md) — full usage guide with real examples
- [docs/writing-tests.md](docs/writing-tests.md) — write your own test cases
- [docs/runbook-guide.md](docs/runbook-guide.md) — master runbook configuration
- [docs/llm-analysis.md](docs/llm-analysis.md) — AI-powered failure analysis pipeline
- [docs/tools-reference.md](docs/tools-reference.md) — every tool explained in depth
