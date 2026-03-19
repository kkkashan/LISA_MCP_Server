# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

- Unit test suite (pytest) for all core modules
- Concurrent LLM failure analysis using `asyncio`
- `AZURE_OPENAI_API_KEY` environment variable fallback (avoid passing key in tool args)
- `compare_test_runs` tool for diffing two JUnit XML files

---

## [0.2.0] — 2025-02-21

### Added

- **LLM analysis pipeline** — three new tools (`analyze_test_run_with_llm`, `analyze_failure_root_cause`, `generate_analysis_report`) and an end-to-end tool (`run_and_analyze`) powered by Azure OpenAI via the Azure OpenAI API
- **`lisa_mcp/tools/llm_analyzer.py`** — structured failure analysis and run-level summary using forced `tool_use` JSON output; models: `gpt-4o`
- **`lisa_mcp/tools/log_collector.py`** — memory-safe seek-based tail reader (256 KB cap), error-context extraction with 15-line windows around error signals, full run-directory walker
- **`lisa_mcp/tools/report_generator.py`** — self-contained HTML report (inline CSS, no CDN) and GitHub-flavored Markdown report; `save_report()` writes both to disk
- **`FailureAnalysis` / `RunAnalysisSummary` / `AnalysisReport` models** — Pydantic v2 models for structured LLM output (`RootCauseCategory`, `FailureSeverity`, severity sort key)
- **`docs/llm-analysis.md`** — complete guide to the LLM analysis pipeline
- **`docs/running-lisa.md`** — step-by-step guide covering system setup through end-to-end MCP analysis (12 steps, quick-reference cheatsheet, troubleshooting table)
- **`CHANGELOG.md`** — this file
- **`CONTRIBUTING.md`** — developer setup, coding standards, PR process

### Changed

- `pyproject.toml`: added `httpx>=0.27.0` dependency
- `README.md`: updated doc map to include all 17 tools, `docs/running-lisa.md`, `docs/llm-analysis.md`, `CHANGELOG.md`, `CONTRIBUTING.md`
- Tool count in README and `docs/tools-reference.md` corrected from 13 → 17

---

## [0.1.0] — 2025-01-15

### Added

- **FastMCP server** (`lisa_mcp/server.py`) with 13 tools, 3 resources, 3 prompts
- **`lisa_mcp/tools/test_discovery.py`** — AST-based scanner; discovers LISA test suites and cases without importing LISA modules; filters by area, tier, priority, platform, name pattern
- **`lisa_mcp/tools/test_generator.py`** — generates Python test suite source code and runbook YAML from structured parameters
- **`lisa_mcp/tools/runbook_builder.py`** — validates, reads, writes, and modifies LISA runbook YAML files; `build_tier_runbook()` shortcut
- **`lisa_mcp/tools/test_runner.py`** — subprocess wrapper for the `lisa` CLI with timeout and variable injection
- **`lisa_mcp/tools/result_parser.py`** — parses JUnit XML (via `junitparser`) and plain console output; auto-detects format
- **`lisa_mcp/models.py`** — Pydantic v2 models: `Priority`, `Category`, `Tier`, `TIER_PRIORITIES`, `Requirement`, `TestCaseInfo`, `TestSuiteInfo`, `RunbookConfig`, `TestResult`, `TestRunSummary`
- **MCP resources**: `lisa://test-case-template`, `lisa://test-suite-template`, `lisa://runbook-template`
- **MCP prompts**: `select_tests_for_scenario`, `create_new_test`, `analyze_test_failure`
- **Documentation**: `README.md`, `QUICKSTART.md`, `INSTALL.md`, `USAGE.md`
- **`docs/`**: `tools-reference.md`, `test-discovery.md`, `writing-tests.md`, `runbook-guide.md`, `automation-guide.md`, `troubleshooting.md`
- **`examples/`**: `azure_t1_runbook.yml`, `custom_selection_runbook.yml`, `new_test_suite_example.py`
- **`.gitignore`**, `LICENSE` (MIT), `mcp_config.json`

---

[Unreleased]: https://github.com/kkkashan/LISA_MCP_Server/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/kkkashan/LISA_MCP_Server/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/kkkashan/LISA_MCP_Server/releases/tag/v0.1.0
