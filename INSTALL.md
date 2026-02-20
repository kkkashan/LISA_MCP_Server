# Installation Guide — LISA MCP Server

This guide covers installation on every supported platform: Windows (WSL2), Ubuntu/Debian, Fedora/RHEL, and macOS.

---

## Table of Contents

1. [System Requirements](#1-system-requirements)
2. [Install on Windows via WSL2](#2-install-on-windows-via-wsl2)
3. [Install on Ubuntu / Debian](#3-install-on-ubuntu--debian)
4. [Install on Fedora / RHEL / CentOS](#4-install-on-fedora--rhel--centos)
5. [Install on macOS](#5-install-on-macos)
6. [Install the LISA framework itself](#6-install-the-lisa-framework-itself)
7. [Register the MCP server with Claude Code](#7-register-the-mcp-server-with-claude-code)
8. [Verify the installation](#8-verify-the-installation)
9. [Upgrading](#9-upgrading)
10. [Uninstalling](#10-uninstalling)

---

## 1. System Requirements

| Component | Minimum Version |
|-----------|----------------|
| Python | 3.10 |
| pip | 23.0 |
| Claude Code CLI | Latest |
| Git | 2.30 |
| OS | Windows 10/11 (WSL2), Ubuntu 20.04+, Fedora 36+, macOS 12+ |

**For running actual tests** (optional):
- Azure subscription (for Azure platform tests)
- SSH key pair for VM access
- LISA installed (`pip install -e ~/lisa`)

---

## 2. Install on Windows via WSL2

This project is developed on WSL2 (the environment in use). Follow these steps exactly.

### 2a. Enable WSL2 (if not already done)

Open **PowerShell as Administrator**:

```powershell
wsl --install
# Restart your PC when prompted
# After restart, WSL2 installs Ubuntu by default
```

### 2b. Open your WSL2 terminal

```powershell
wsl
```

### 2c. Update system packages

```bash
sudo apt-get update && sudo apt-get upgrade -y
```

### 2d. Install Python 3.10+

```bash
# Ubuntu 22.04+ ships Python 3.10 by default
python3 --version
# Python 3.10.x or later — you're good

# If Python 3.9 or earlier:
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv python3.12-dev
```

### 2e. Install pip

```bash
sudo apt-get install -y python3-pip
# or, if that fails:
curl -sS https://bootstrap.pypa.io/get-pip.py | python3 --user
```

### 2f. Clone and install

```bash
# Clone LISA (the test framework)
git clone https://github.com/microsoft/lisa.git ~/lisa

# Clone this MCP server
git clone <this-repo-url> ~/lisa-mcp-server

# Install the MCP server
cd ~/lisa-mcp-server
pip3 install -e .
```

### 2g. Windows path note

Your Windows home is accessible at `/mnt/c/Users/<YourUsername>/` from WSL2.
You can store the repos anywhere, but WSL2 paths (e.g. `~/lisa`) give much faster
I/O than Windows paths (`/mnt/c/...`).

---

## 3. Install on Ubuntu / Debian

```bash
# 1. System dependencies
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv git

# 2. Verify Python version
python3 --version   # must be 3.10 or later

# 3. Clone repos
git clone https://github.com/microsoft/lisa.git ~/lisa
git clone <this-repo-url> ~/lisa-mcp-server

# 4. (Recommended) create a virtual environment
python3 -m venv ~/lisa-mcp-server/.venv
source ~/lisa-mcp-server/.venv/bin/activate

# 5. Install
cd ~/lisa-mcp-server
pip install -e .

# 6. Make sure the venv is activated whenever you use the server
# Add to ~/.bashrc:
echo 'source ~/lisa-mcp-server/.venv/bin/activate' >> ~/.bashrc
```

---

## 4. Install on Fedora / RHEL / CentOS

```bash
# 1. System dependencies
sudo dnf install -y python3 python3-pip git

# 2. Verify
python3 --version

# 3. Clone repos
git clone https://github.com/microsoft/lisa.git ~/lisa
git clone <this-repo-url> ~/lisa-mcp-server

# 4. Virtual environment (recommended)
python3 -m venv ~/lisa-mcp-server/.venv
source ~/lisa-mcp-server/.venv/bin/activate

# 5. Install
cd ~/lisa-mcp-server
pip install -e .
```

---

## 5. Install on macOS

```bash
# 1. Install Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. Install Python
brew install python@3.12

# 3. Verify
python3 --version

# 4. Clone repos
git clone https://github.com/microsoft/lisa.git ~/lisa
git clone <this-repo-url> ~/lisa-mcp-server

# 5. Virtual environment (recommended)
python3 -m venv ~/lisa-mcp-server/.venv
source ~/lisa-mcp-server/.venv/bin/activate

# 6. Install
cd ~/lisa-mcp-server
pip install -e .
```

---

## 6. Install the LISA framework itself

> This step is required only if you want to **run** tests. Test **discovery**,
> **generation**, and **runbook building** work without LISA installed.

```bash
# Navigate to the LISA repo
cd ~/lisa

# Install LISA and all its dependencies
pip install -e .

# Verify
lisa --version
```

### LISA system dependencies (Ubuntu/WSL2)

LISA needs some additional packages for test execution:

```bash
sudo apt-get install -y \
    gcc \
    libssl-dev \
    libffi-dev \
    build-essential \
    sshpass \
    openssh-client
```

### Azure credentials setup (for Azure tests)

```bash
# Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login
az login

# Set default subscription
az account set --subscription "YOUR_SUBSCRIPTION_ID"

# Generate SSH key for VM access (if you don't have one)
ssh-keygen -t rsa -b 4096 -f ~/.ssh/lisa_id_rsa -N ""
```

---

## 7. Register the MCP server with Claude Code

### Step 1 — Find the settings file

```bash
# The MCP servers configuration file
ls ~/.claude/mcp_servers.json 2>/dev/null || echo "File does not exist yet"
```

### Step 2 — Create or update the file

Replace `/home/YOUR_USER/lisa-mcp-server` with your actual path from `pwd`:

```bash
# Get the absolute path
REPO_PATH=$(cd ~/lisa-mcp-server && pwd)
echo "Use this path: $REPO_PATH"
```

Create `~/.claude/mcp_servers.json`:

```json
{
  "mcpServers": {
    "lisa": {
      "command": "python3",
      "args": ["-m", "lisa_mcp.server"],
      "cwd": "/home/YOUR_USER/lisa-mcp-server",
      "env": {}
    }
  }
}
```

### Step 3 — If using a virtual environment

When using a venv, point `command` to the venv's Python:

```json
{
  "mcpServers": {
    "lisa": {
      "command": "/home/YOUR_USER/lisa-mcp-server/.venv/bin/python3",
      "args": ["-m", "lisa_mcp.server"],
      "cwd": "/home/YOUR_USER/lisa-mcp-server",
      "env": {}
    }
  }
}
```

### Step 4 — If you already have other MCP servers

Merge the `lisa` key into your existing `mcpServers` object:

```json
{
  "mcpServers": {
    "existing-server": { "...": "..." },
    "lisa": {
      "command": "python3",
      "args": ["-m", "lisa_mcp.server"],
      "cwd": "/home/YOUR_USER/lisa-mcp-server"
    }
  }
}
```

### Step 5 — Restart Claude Code

```bash
# Exit any running Claude Code session
# Then start fresh:
claude
```

---

## 8. Verify the installation

### Check MCP connectivity

In Claude Code, run:

```
/mcp
```

Expected output includes `lisa` in the server list with status `connected`.

### Test a tool directly

```
Using the LISA MCP server, call check_lisa_environment
```

Expected:

```json
{
  "installed": false,   // or true if LISA is installed
  "path": null,
  "version_output": ""
}
```

### Test discovery (no LISA needed)

```
List all test areas in ~/lisa
```

Expected: a JSON list of area names like `["network", "storage", "cpu", ...]`.

### Full smoke test

```bash
# Run this in a terminal to confirm everything is wired correctly
python3 -c "
from lisa_mcp.server import mcp
tools = mcp._tool_manager.list_tools()
print(f'Server: {mcp.name}')
print(f'Tools registered: {len(tools)}')
for t in tools:
    print(f'  {t.name}')
"
```

Expected output:

```
Server: lisa-mcp-server
Tools registered: 13
  discover_test_cases
  list_test_areas
  get_test_case_details
  search_tests
  generate_test_suite_code
  build_runbook
  build_tier_runbook_file
  validate_runbook_file
  add_test_to_existing_runbook
  run_lisa_tests
  parse_test_results
  check_lisa_environment
  get_tier_info
```

---

## 9. Upgrading

```bash
cd ~/lisa-mcp-server

# Pull latest changes
git pull origin main

# Reinstall (editable install updates automatically, but reinstall if pyproject.toml changed)
pip install -e .

# Restart Claude Code
```

---

## 10. Uninstalling

```bash
# Remove the package
pip uninstall lisa-mcp-server

# Remove repos (optional)
rm -rf ~/lisa-mcp-server

# Remove the MCP server registration
# Edit ~/.claude/mcp_servers.json and remove the "lisa" key
```

---

## Dependency Reference

All dependencies are declared in `pyproject.toml` and installed automatically:

| Package | Purpose |
|---------|---------|
| `mcp>=1.0.0` | Model Context Protocol SDK (FastMCP) |
| `pyyaml>=6.0` | Parse and generate runbook YAML |
| `pydantic>=2.0` | Data validation for models |
| `rich>=13.0` | Terminal formatting |
| `click>=8.0` | CLI entry point |
| `junitparser>=3.0` | Parse JUnit XML test results |

---

## Troubleshooting Installation

See [docs/troubleshooting.md](docs/troubleshooting.md) for common issues.

Quick fixes:

```bash
# "ModuleNotFoundError: No module named 'lisa_mcp'"
pip install -e ~/lisa-mcp-server

# "command not found: python3"
sudo apt-get install python3    # Ubuntu
brew install python@3.12        # macOS

# MCP server shows as "disconnected" in Claude Code
# Check the cwd path is absolute and the Python path is correct
python3 ~/lisa-mcp-server/lisa_mcp/server.py   # run directly to see errors
```
