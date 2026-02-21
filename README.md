# LISA MCP Server

> **Model Context Protocol server for Microsoft LISA — Linux Integration Services Automation**

Connect Claude (or any MCP-compatible AI) directly to the [Microsoft LISA](https://github.com/microsoft/lisa) Linux testing framework. Select test cases, generate test code, build runbook configurations, run tests, and analyze results — all through natural language.

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
| Manually grep Python files for test names | Ask Claude: *"show me all storage tests at priority 0"* |
| Hand-write runbook YAML from scratch | Ask Claude: *"build a T2 Azure runbook for RHEL 9"* |
| Copy-paste test suite boilerplate | Ask Claude: *"generate a test suite for NVMe disk throughput"* |
| Manually parse JUnit XML for failures | Ask Claude: *"what failed in my last run and why?"* |
| Remember CLI flags and variable syntax | Claude handles all of it |

---

## Documentation

| Document | Description |
|----------|-------------|
| **[QUICKSTART.md](QUICKSTART.md)** | Get running in 10 minutes |
| **[INSTALL.md](INSTALL.md)** | Full installation guide for all platforms |
| **[USAGE.md](USAGE.md)** | Detailed usage with real examples |
| **[docs/running-lisa.md](docs/running-lisa.md)** | Step-by-step guide to running LISA tests |
| **[docs/tools-reference.md](docs/tools-reference.md)** | Complete reference for all 17 MCP tools |
| **[docs/test-discovery.md](docs/test-discovery.md)** | How test scanning and filtering works |
| **[docs/writing-tests.md](docs/writing-tests.md)** | Step-by-step guide to writing new LISA tests |
| **[docs/runbook-guide.md](docs/runbook-guide.md)** | Complete runbook authoring guide |
| **[docs/llm-analysis.md](docs/llm-analysis.md)** | LLM-powered failure analysis pipeline |
| **[docs/automation-guide.md](docs/automation-guide.md)** | CI/CD pipeline integration |
| **[docs/troubleshooting.md](docs/troubleshooting.md)** | Common problems and fixes |
| **[CHANGELOG.md](CHANGELOG.md)** | Version history and release notes |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | How to contribute to this project |

---

## Quick Example

```
You: "Scan my LISA repo and show me all network tests at tier T1,
      then build a runbook for Azure that runs them on Ubuntu 22.04"

Claude calls:
  1. discover_test_cases(lisa_path="~/lisa", area="network", tier="T1")
  2. build_runbook(name="Network T1", platform_type="azure",
                   tier="T1", image="ubuntu jammy 22.04-lts latest")

Result: a filtered list of tests + a ready-to-use runbook.yml
```

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
│
├── lisa_mcp/                         ← Python package
│   ├── server.py                     ← FastMCP server (tools, resources, prompts)
│   ├── models.py                     ← Pydantic data models
│   └── tools/
│       ├── test_discovery.py         ← AST-based test scanner
│       ├── test_generator.py         ← Code + YAML generation
│       ├── runbook_builder.py        ← Runbook build/validate/update
│       ├── test_runner.py            ← lisa CLI subprocess wrapper
│       └── result_parser.py          ← JUnit XML + console output parser
│
├── docs/
│   ├── running-lisa.md               ← Step-by-step run guide
│   ├── tools-reference.md            ← All 17 tools documented
│   ├── test-discovery.md             ← Discovery internals
│   ├── writing-tests.md              ← Test authoring guide
│   ├── runbook-guide.md              ← Runbook authoring guide
│   ├── llm-analysis.md               ← LLM analysis pipeline
│   ├── automation-guide.md           ← CI/CD integration
│   └── troubleshooting.md            ← Problem solving
│
└── examples/
    ├── azure_t1_runbook.yml          ← Ready-to-use T1 runbook
    ├── custom_selection_runbook.yml  ← Custom test selection
    └── new_test_suite_example.py     ← Generated test suite
```

---

## License

MIT — see [LICENSE](LICENSE).

Built for [Microsoft LISA](https://github.com/microsoft/lisa) | Powered by [Model Context Protocol](https://modelcontextprotocol.io)
