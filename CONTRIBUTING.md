# Contributing to LISA MCP Server

Thank you for your interest in contributing. This document covers how to set up your development environment, coding standards, and the pull request process.

---

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Running Tests](#running-tests)
- [Coding Standards](#coding-standards)
- [Adding a New MCP Tool](#adding-a-new-mcp-tool)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Reporting Issues](#reporting-issues)

---

## Development Setup

### Requirements

- Python 3.10 or newer
- Git
- (Optional) An Anthropic API key to test LLM analysis tools

### Steps

```bash
# 1. Fork and clone the repo
git clone https://github.com/<your-username>/LISA_MCP_Server.git
cd LISA_MCP_Server

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install the package in editable mode with dev dependencies
pip install -e ".[dev]"

# 4. Verify the server starts
lisa-mcp --help
```

The `[dev]` extra installs `ruff`, `mypy`, `pytest`, and `pytest-asyncio`.

---

## Project Structure

```
lisa_mcp/
├── server.py          ← FastMCP server — all tool/resource/prompt definitions
├── models.py          ← Pydantic v2 data models (no business logic)
└── tools/
    ├── test_discovery.py   ← AST-based LISA repo scanner
    ├── test_generator.py   ← Python + YAML code generation
    ├── runbook_builder.py  ← Runbook read/write/validate
    ├── test_runner.py      ← lisa CLI subprocess wrapper
    ├── result_parser.py    ← JUnit XML + console output parser
    ├── log_collector.py    ← Memory-safe log tail and error extraction
    ├── llm_analyzer.py     ← Anthropic API calls (structured tool_use)
    └── report_generator.py ← HTML + Markdown report generation
```

**Rule of thumb**: business logic lives in `tools/`; `server.py` only wires tools to MCP and handles JSON serialization; `models.py` holds pure data structures.

---

## Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific module
pytest tests/test_result_parser.py

# Run with coverage
pytest --cov=lisa_mcp --cov-report=term-missing
```

Tests live in `tests/`. Each module in `tools/` should have a corresponding `tests/test_<module>.py`.

---

## Coding Standards

### Linting and formatting

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting.

```bash
# Check for issues
ruff check lisa_mcp/

# Auto-fix safe issues
ruff check --fix lisa_mcp/

# Format code
ruff format lisa_mcp/
```

The configuration is in `pyproject.toml` (`line-length = 100`, `target-version = "py310"`).

### Type checking

```bash
mypy lisa_mcp/
```

All public functions should have type annotations. Use `from __future__ import annotations` at the top of every file.

### Style conventions

- **Docstrings**: every public function and class needs a docstring. MCP tool docstrings are user-visible — write them clearly.
- **No magic numbers**: define constants at the module level with a descriptive name.
- **Error handling**: catch specific exceptions, not bare `except Exception` where possible. Always return a JSON error payload from MCP tools rather than raising.
- **No print statements**: use Python's `logging` module or the MCP server's logging facilities.
- **File I/O**: never load an entire log file into memory. Use seek-based reading (see `log_collector._tail_read_lines`).

---

## Adding a New MCP Tool

1. **Implement the logic** in the appropriate `lisa_mcp/tools/*.py` module (or create a new one if it doesn't fit).

2. **Add data models** to `lisa_mcp/models.py` if the tool returns structured data.

3. **Register the tool** in `lisa_mcp/server.py` with the `@mcp.tool()` decorator:

```python
@mcp.tool()
def my_new_tool(param_a: str, param_b: int = 10) -> str:
    """
    One-line description shown to the MCP client.

    Parameters
    ----------
    param_a : Explanation of param_a.
    param_b : Explanation of param_b (default 10).

    Returns JSON with ...
    """
    try:
        result = do_the_work(param_a, param_b)
        return json.dumps(result, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc), "type": type(exc).__name__}, indent=2)
```

4. **Write tests** in `tests/test_<module>.py`.

5. **Document the tool** in `docs/tools-reference.md` following the existing format.

6. **Update the tool count** in `README.md` if you've added a new tool.

---

## Submitting a Pull Request

1. **Create a branch** from `main`:

```bash
git checkout -b feat/my-feature
```

2. **Make your changes** following the coding standards above.

3. **Run checks** before pushing:

```bash
ruff check lisa_mcp/
mypy lisa_mcp/
pytest
```

4. **Update `CHANGELOG.md`** — add your changes under the `[Unreleased]` section.

5. **Push and open a PR**:

```bash
git push -u origin feat/my-feature
```

Then open a pull request on GitHub. The PR description should explain:
- What the change does
- Why it is needed
- How it was tested

### PR Checklist

- [ ] `ruff check` passes with no errors
- [ ] `mypy` passes with no errors
- [ ] New tests added for new functionality
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] `docs/tools-reference.md` updated if a tool was added/changed
- [ ] `README.md` tool count updated if applicable

---

## Reporting Issues

Please use [GitHub Issues](https://github.com/kkkashan/LISA_MCP_Server/issues) to report bugs or request features. Include:

- Your OS and Python version
- The exact tool call or command that failed
- The full error message or stack trace
- Steps to reproduce

For security vulnerabilities, please do **not** open a public issue — contact the maintainer directly.
