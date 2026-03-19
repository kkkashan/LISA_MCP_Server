# Quickstart — LISA MCP Server

Get from zero to the AI running LISA tests in 10 minutes.

---

## Prerequisites

- Python 3.10 or later
- - Git

---

## Step 1 — Clone both repositories

```bash
# Clone the LISA framework (the test suite library)
git clone https://github.com/microsoft/lisa.git ~/lisa

# Clone this MCP server
git clone <this-repo-url> ~/lisa-mcp-server
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

Open or create `.vscode/mcp.json` and add:

```json
{
  "mcpServers": {
    "lisa": {
      "command": "python3",
      "args": ["-m", "lisa_mcp.server"],
      "cwd": "/home/YOUR_USER/lisa-mcp-server"
    }
  }
}
```

Replace `/home/YOUR_USER/lisa-mcp-server` with the real absolute path from `pwd`.

Restart VS Code:

```bash
the AI
```

---

## Step 4 — Verify the MCP tools are available

In VS Code, type:

```
/mcp
```

You should see `lisa` listed as a connected server with 13 tools.

---

## Step 5 — Your first commands

### 5a. Check what test areas exist

```
Show me all the functional areas in my LISA repo at ~/lisa
```

The AI calls `list_test_areas(lisa_path="~/lisa")` and returns something like:

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

### 5d. Generate a new test

```
Write a LISA test suite called "KernelSmokeTest" in the "cpu" area
that checks the kernel version is at least 5.15. Priority 0, Azure only.
```

The AI calls `generate_test_suite_code(...)` and returns complete Python source ready to copy into the LISA repo.

---

## Step 6 — Run tests (requires LISA installed + Azure credentials)

Install LISA itself:

```bash
cd ~/lisa
pip install -e .
lisa --version
```

Then ask the AI:

```
Run the runbook at ~/my_runbook.yml using the LISA repo at ~/lisa.
Pass subscription_id:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
and admin_private_key_file:~/.ssh/id_rsa
```

The AI calls `run_lisa_tests(...)` and returns stdout/stderr + exit code.

---

## What's next?

- [INSTALL.md](INSTALL.md) — detailed installation for Windows/WSL/Linux/macOS
- [USAGE.md](USAGE.md) — full usage guide with real examples
- [docs/writing-tests.md](docs/writing-tests.md) — write your own test cases
- [docs/runbook-guide.md](docs/runbook-guide.md) — master runbook configuration
- [docs/tools-reference.md](docs/tools-reference.md) — every tool explained in depth
