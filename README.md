# LISA MCP Server

> **Model Context Protocol server for Microsoft LISA — Linux Integration Services Automation**

Connect any MCP-compatible AI (GitHub Copilot, VS Code, or any MCP client) directly to the [Microsoft LISA](https://github.com/microsoft/lisa) Linux testing framework. Select test cases, generate test code, build runbook configurations, run tests, and analyze failures with AI — all through natural language.

---

## What is LISA?

LISA (Linux Integration Services Automation) is Microsoft's quality validation system for Linux on Azure, HyperV, and bare-metal. It provides:

- A **declarative test framework** built in Python
- Hundreds of **built-in test suites** covering networking, storage, CPU, memory, kernel, hypervisor integration, and more
- **Multi-platform support**: Azure, HyperV, QEMU, bare metal
- **Runbook-driven execution** via YAML configuration files
- **Tier-based test selection** (T0–T4) for different CI/CD stages

---

## What this MCP server adds

| Without MCP | With LISA MCP Server |
|-------------|----------------------|
| Manually grep Python files for test names | *"Show me all storage tests at priority 0"* |
| Hand-write runbook YAML from scratch | *"Build a T2 Azure runbook for RHEL 9"* |
| Copy-paste test suite boilerplate | *"Generate a test suite for NVMe disk throughput"* |
| Manually parse JUnit XML for failures | *"What failed in my last run and why?"* |
| Remember CLI flags and variable syntax | Handled automatically by the AI |

---

## LLM Failure Analysis — Powered by Azure OpenAI

The server integrates with **Azure OpenAI** to provide AI-powered failure analysis:

- **Root cause classification** — categorizes failures (disk I/O, network timeout, kernel panic, etc.)
- **Actionable fix recommendations** — specific commands, file paths, settings to investigate
- **Severity scoring** — critical / high / medium / low prioritization
- **Run-level executive summary** — stakeholder-ready health report
- **HTML + Markdown reports** — shareable analysis artifacts

Configure your Azure OpenAI endpoint and API key when calling any `analyze_*` or `run_and_analyze` tool:

```
Analyze the failures in ~/lisa/lisa_results.xml
Azure OpenAI key: <your-key>
Save the report to ~/reports/
```

---

## Quick Example

```
You: "Scan my LISA repo and show me all network tests at tier T1,
      then build a runbook for Azure that runs them on Ubuntu 22.04"

The AI invokes:
  1. discover_test_cases(lisa_path="~/lisa", area="network", tier="T1")
  2. build_runbook(name="Network T1", platform_type="azure",
                   tier="T1", image="ubuntu jammy 22.04-lts latest")

Result: a filtered list of tests + a ready-to-use runbook.yml
```

---

## Getting Started

### 1 — Install

```bash
git clone https://github.com/kkkashan/LISA_MCP_Server.git ~/lisa-mcp-server
cd ~/lisa-mcp-server
pip install -e .
```

### 2 — Register with VS Code

The repository ships with a `.vscode/mcp.json` that registers the server automatically in VS Code. Open the workspace — VS Code will detect it and offer to start the server.

Alternatively, add it manually to `.vscode/mcp.json`:

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

### 3 — Start asking questions

Open GitHub Copilot Chat (or any MCP client) and start with:

```
Check the LISA environment and show me the available test tiers
```

---

## Documentation

| Document | Description |
|----------|-------------|
| **[QUICKSTART.md](QUICKSTART.md)** | Get running in 10 minutes |
| **[INSTALL.md](INSTALL.md)** | Full installation guide for all platforms |
| **[USAGE.md](USAGE.md)** | Detailed usage examples |
| **[docs/running-lisa.md](docs/running-lisa.md)** | Step-by-step guide to running LISA tests |
| **[docs/tools-reference.md](docs/tools-reference.md)** | Complete reference for all 17 MCP tools |
| **[docs/test-discovery.md](docs/test-discovery.md)** | How test scanning and filtering works |
| **[docs/writing-tests.md](docs/writing-tests.md)** | Step-by-step guide to writing new LISA tests |
| **[docs/runbook-guide.md](docs/runbook-guide.md)** | Complete runbook authoring guide |
| **[docs/llm-analysis.md](docs/llm-analysis.md)** | AI-powered failure analysis pipeline |
| **[docs/automation-guide.md](docs/automation-guide.md)** | CI/CD pipeline integration |
| **[docs/troubleshooting.md](docs/troubleshooting.md)** | Common problems and fixes |
| **[CHANGELOG.md](CHANGELOG.md)** | Version history and release notes |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | How to contribute to this project |

---

## The 17 MCP Tools

| Category | Tool | What it does |
|----------|------|--------------|
| **Discovery** | `discover_test_cases` | Scan LISA repo, filter by area/tier/priority/platform |
| | `list_test_areas` | List all functional areas (network, storage, CPU…) |
| | `get_test_case_details` | Full metadata for one test |
| | `search_tests` | Free-text search across names and descriptions |
| **Generation** | `generate_test_suite_code` | Generate Python source for a new test suite |
| | `build_runbook` | Generate YAML runbook with test criteria |
| | `build_tier_runbook_file` | Quick tier-based runbook builder |
| **Validation** | `validate_runbook_file` | Check YAML syntax & schema |
| | `add_test_to_existing_runbook` | Add include/exclude criteria to existing runbook |
| | `check_lisa_environment` | Verify LISA CLI is installed |
| | `get_tier_info` | T0–T4 tier definitions and priority ranges |
| **Execution** | `run_lisa_tests` | Execute tests via `lisa` CLI subprocess |
| | `parse_test_results` | Parse JUnit XML or console output |
| **AI Analysis** | `analyze_test_run_with_llm` | Analyze all failures with Azure OpenAI |
| | `analyze_failure_root_cause` | Deep-dive AI analysis for one failure |
| | `generate_analysis_report` | Full pipeline → HTML + Markdown report |
| | `run_and_analyze` | End-to-end: run tests → analyze → report |

---

## Project Structure

```
lisa-mcp-server/
├── README.md                         ← You are here
├── QUICKSTART.md                     ← Start here
├── INSTALL.md                        ← Installation guide
├── USAGE.md                          ← Usage guide
├── pyproject.toml                    ← Python package metadata
├── mcp_config.json                   ← MCP client config snippet
├── .vscode/
│   └── mcp.json                      ← VS Code MCP server registration
│
├── lisa_mcp/                         ← Python package
│   ├── server.py                     ← FastMCP server (17 tools, 3 resources, 3 prompts)
│   ├── models.py                     ← Pydantic data models
│   └── tools/
│       ├── test_discovery.py         ← AST-based test scanner
│       ├── test_generator.py         ← Code + YAML generation
│       ├── runbook_builder.py        ← Runbook build/validate/update
│       ├── test_runner.py            ← lisa CLI subprocess wrapper
│       ├── result_parser.py          ← JUnit XML + console output parser
│       ├── log_collector.py          ← Memory-safe log extraction
│       ├── llm_analyzer.py           ← Azure OpenAI failure analysis
│       └── report_generator.py       ← HTML + Markdown report generation
│
├── docs/
│   ├── running-lisa.md               ← Step-by-step run guide
│   ├── tools-reference.md            ← All 17 tools documented
│   ├── test-discovery.md             ← Discovery internals
│   ├── writing-tests.md              ← Test authoring guide
│   ├── runbook-guide.md              ← Runbook authoring guide
│   ├── llm-analysis.md               ← AI analysis pipeline
│   ├── automation-guide.md           ← CI/CD integration
│   └── troubleshooting.md            ← Problem solving
│
└── examples/
    ├── azure_t1_runbook.yml          ← Ready-to-use T1 runbook
    ├── custom_selection_runbook.yml  ← Custom test selection
    ├── new_test_suite_example.py     ← Example test suite
    └── network_connectivity_test.py  ← Generated network test suite
```

---

## License

MIT — see [LICENSE](LICENSE).

Built for [Microsoft LISA](https://github.com/microsoft/lisa) | Powered by [Model Context Protocol](https://modelcontextprotocol.io) | AI analysis via [Azure OpenAI](https://azure.microsoft.com/products/ai-services/openai-service)
