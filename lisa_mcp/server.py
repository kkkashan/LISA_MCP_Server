"""
LISA MCP Server
===============
Exposes Microsoft LISA (Linux Integration Services Automation) capabilities
through the Model Context Protocol so Claude (or any MCP client) can:

  • Discover and search test cases in a LISA repository
  • Filter tests by tier, priority, OS, platform, area
  • Generate new test suite / test case source code
  • Build and validate runbook YAML files
  • Run tests via the lisa CLI
  • Parse and summarize test results
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from lisa_mcp.models import TIER_PRIORITIES
from lisa_mcp.tools.test_discovery import discover_tests, list_areas, get_test_details
from lisa_mcp.tools.test_generator import generate_test_suite, generate_runbook_yaml
from lisa_mcp.tools.runbook_builder import (
    validate_runbook,
    write_runbook,
    add_test_to_runbook,
    build_tier_runbook,
)
from lisa_mcp.tools.test_runner import run_tests, check_lisa_installed
from lisa_mcp.tools.result_parser import parse_results, summarize

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="lisa-mcp-server",
    instructions=(
        "You are a Linux testing assistant powered by the Microsoft LISA framework. "
        "Use the available tools to discover test cases, build runbooks, generate test "
        "code, run tests, and analyze results. Always confirm destructive operations "
        "like running tests against real cloud infrastructure."
    ),
)


# ============================================================================
# TOOL 1 — discover_test_cases
# ============================================================================

@mcp.tool()
def discover_test_cases(
    lisa_path: str,
    area: str | None = None,
    tier: str | None = None,
    priority: int | None = None,
    platform: str | None = None,
    name_pattern: str | None = None,
    max_results: int = 200,
) -> str:
    """
    Scan a local LISA repository and return all matching test cases.

    Parameters
    ----------
    lisa_path    : Absolute path to the cloned LISA repository root.
    area         : Filter by functional area (e.g. "network", "storage", "cpu").
    tier         : Filter by test tier T0–T4 (maps to priority ranges).
    priority     : Filter by exact priority level 0–5.
    platform     : Filter by supported platform ("azure", "hyperv", etc.).
    name_pattern : Substring or glob pattern matched against test name/description.
    max_results  : Cap on total test cases returned (default 200).

    Returns JSON with a list of test suites, each containing test cases.
    """
    suites = discover_tests(
        lisa_path=lisa_path,
        area=area,
        tier=tier,
        priority=priority,
        platform=platform,
        name_pattern=name_pattern,
    )

    # Flatten and cap
    output: list[dict[str, Any]] = []
    count = 0
    for suite in suites:
        suite_info = {
            "suite": suite.name,
            "area": suite.area,
            "category": suite.category,
            "description": suite.description,
            "owner": suite.owner,
            "file": suite.file_path,
            "test_cases": [],
        }
        for tc in suite.test_cases:
            if count >= max_results:
                break
            suite_info["test_cases"].append(
                {
                    "name": tc.name,
                    "method": tc.method_name,
                    "priority": tc.priority,
                    "description": tc.description,
                    "timeout": tc.timeout,
                    "use_new_environment": tc.use_new_environment,
                    "requirement": {
                        "min_core_count": tc.requirement.min_core_count,
                        "min_memory_mb": tc.requirement.min_memory_mb,
                        "supported_features": tc.requirement.supported_features,
                        "unsupported_os": tc.requirement.unsupported_os,
                        "supported_platform_type": tc.requirement.supported_platform_type,
                    },
                    "tags": tc.tags,
                }
            )
            count += 1
        if suite_info["test_cases"]:
            output.append(suite_info)
        if count >= max_results:
            break

    return json.dumps(
        {
            "total_suites": len(output),
            "total_test_cases": count,
            "truncated": count >= max_results,
            "filters": {
                "area": area,
                "tier": tier,
                "priority": priority,
                "platform": platform,
                "name_pattern": name_pattern,
            },
            "suites": output,
        },
        indent=2,
    )


# ============================================================================
# TOOL 2 — list_test_areas
# ============================================================================

@mcp.tool()
def list_test_areas(lisa_path: str) -> str:
    """
    Return all unique functional areas (domains) in the LISA repository.

    Parameters
    ----------
    lisa_path : Absolute path to the cloned LISA repository root.

    Returns JSON list of area strings, e.g. ["network", "storage", "cpu", ...].
    """
    areas = list_areas(lisa_path)
    return json.dumps({"areas": areas, "count": len(areas)}, indent=2)


# ============================================================================
# TOOL 3 — get_test_case_details
# ============================================================================

@mcp.tool()
def get_test_case_details(lisa_path: str, test_name: str) -> str:
    """
    Get the full metadata for a specific test case.

    Parameters
    ----------
    lisa_path : Absolute path to the cloned LISA repository root.
    test_name : Full test name (SuiteName.method_name) or method name alone.

    Returns JSON with all metadata, or an error message if not found.
    """
    tc = get_test_details(lisa_path, test_name)
    if tc is None:
        return json.dumps({"error": f"Test case '{test_name}' not found in {lisa_path}"})
    return tc.model_dump_json(indent=2)


# ============================================================================
# TOOL 4 — search_tests
# ============================================================================

@mcp.tool()
def search_tests(
    lisa_path: str,
    query: str,
    area: str | None = None,
    tier: str | None = None,
    max_results: int = 50,
) -> str:
    """
    Free-text search across test case names AND descriptions in a LISA repo.

    Parameters
    ----------
    lisa_path   : Absolute path to the cloned LISA repository root.
    query       : Free-text string to match against name and description.
    area        : Optional area filter to narrow scope.
    tier        : Optional tier filter (T0–T4).
    max_results : Maximum number of results (default 50).

    Returns a ranked JSON list of matching test cases.
    """
    suites = discover_tests(
        lisa_path=lisa_path,
        area=area,
        tier=tier,
        name_pattern=query,
    )

    matches: list[dict[str, Any]] = []
    for suite in suites:
        for tc in suite.test_cases:
            if len(matches) >= max_results:
                break
            score = 0
            if query.lower() in tc.name.lower():
                score += 3
            if query.lower() in tc.description.lower():
                score += 2
            if query.lower() in tc.area.lower():
                score += 1
            matches.append(
                {
                    "name": tc.name,
                    "suite": tc.suite_name,
                    "area": tc.area,
                    "priority": tc.priority,
                    "description": tc.description,
                    "file": tc.file_path,
                    "score": score,
                }
            )

    matches.sort(key=lambda x: (-x["score"], x["priority"], x["name"]))
    return json.dumps(
        {"query": query, "total_matches": len(matches), "results": matches}, indent=2
    )


# ============================================================================
# TOOL 5 — generate_test_suite_code
# ============================================================================

@mcp.tool()
def generate_test_suite_code(
    suite_class_name: str,
    area: str,
    category: str,
    description: str,
    owner: str,
    test_cases: list[dict[str, Any]],
    output_path: str | None = None,
) -> str:
    """
    Generate Python source code for a new LISA test suite.

    Parameters
    ----------
    suite_class_name : PascalCase class name, e.g. "MyNetworkTest".
    area             : Functional domain, e.g. "network".
    category         : "functional" | "performance" | "stress" | "community".
    description      : Human-readable description of the suite.
    owner            : Owner or team name.
    test_cases       : List of test case dicts. Each dict may have:
                         - method_name (str, required)
                         - description (str, required)
                         - priority (int, 0–5, default 2)
                         - timeout (int seconds, default 3600)
                         - use_new_environment (bool, default false)
                         - requirement (dict with optional fields:
                             min_core_count, min_memory_mb, min_disk_space_gb,
                             supported_features, unsupported_os,
                             supported_platform_type)
                         - body_lines (list[str]: Python lines for test body)
    output_path      : If provided, write the generated code to this path.

    Returns the generated Python source code as a string.
    """
    code = generate_test_suite(
        suite_class_name=suite_class_name,
        area=area,
        category=category,
        description=description,
        owner=owner,
        test_cases=test_cases,
    )

    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(code, encoding="utf-8")
        return json.dumps(
            {"message": f"Test suite written to {output_path}", "code": code}, indent=2
        )

    return json.dumps({"code": code}, indent=2)


# ============================================================================
# TOOL 6 — build_runbook
# ============================================================================

@mcp.tool()
def build_runbook(
    name: str,
    platform_type: str = "azure",
    tier: str | None = None,
    test_names: list[str] | None = None,
    excluded_names: list[str] | None = None,
    priorities: list[int] | None = None,
    variables: dict[str, str] | None = None,
    notifiers: list[str] | None = None,
    image: str = "ubuntu focal 20.04-lts latest",
    location: str = "westus3",
    concurrency: int = 1,
    output_path: str | None = None,
) -> str:
    """
    Generate a LISA runbook YAML configuration file.

    Parameters
    ----------
    name          : Human-readable runbook name.
    platform_type : "azure" | "hyperv" | "ready" | "qemu" | "baremetal".
    tier          : T0–T4 shortcut to set priority filter automatically.
    test_names    : Specific test names to include.
    excluded_names: Test names to exclude from the run.
    priorities    : Explicit list of priority levels to include [0,1,2,...].
    variables     : Additional runbook variables (name → value).
    notifiers     : Notifier types to enable: "html", "junit" (console is always on).
    image         : OS image for Azure/cloud platforms.
    location      : Azure region.
    concurrency   : Number of parallel test environments.
    output_path   : If provided, write runbook YAML to this path.

    Returns the generated runbook YAML string.
    """
    yaml_str = generate_runbook_yaml(
        name=name,
        platform_type=platform_type,
        tier=tier,
        test_names=test_names,
        excluded_names=excluded_names,
        priorities=priorities,
        variables=variables,
        notifiers=notifiers,
        image=image,
        location=location,
        concurrency=concurrency,
    )

    if output_path:
        write_runbook(yaml_str, output_path)
        return json.dumps(
            {"message": f"Runbook written to {output_path}", "yaml": yaml_str}, indent=2
        )

    return json.dumps({"yaml": yaml_str}, indent=2)


# ============================================================================
# TOOL 7 — validate_runbook_file
# ============================================================================

@mcp.tool()
def validate_runbook_file(runbook_path: str) -> str:
    """
    Validate a LISA runbook YAML file for syntax and structural correctness.

    Parameters
    ----------
    runbook_path : Absolute or relative path to the runbook YAML file.

    Returns JSON with 'valid', 'errors', 'warnings', and a 'summary' dict.
    """
    result = validate_runbook(runbook_path)
    return json.dumps(result, indent=2)


# ============================================================================
# TOOL 8 — add_test_to_existing_runbook
# ============================================================================

@mcp.tool()
def add_test_to_existing_runbook(
    runbook_path: str,
    test_name: str,
    select_action: str = "include",
) -> str:
    """
    Add a test case inclusion/exclusion criterion to an existing runbook file.

    Parameters
    ----------
    runbook_path  : Path to the existing runbook YAML file.
    test_name     : Test name (or substring) to match.
    select_action : "include" | "exclude" | "force-include" | "force-exclude".

    Returns the updated YAML content.
    """
    try:
        updated_yaml = add_test_to_runbook(runbook_path, test_name, select_action)
        return json.dumps(
            {
                "message": f"Added '{test_name}' ({select_action}) to {runbook_path}",
                "yaml": updated_yaml,
            },
            indent=2,
        )
    except Exception as exc:
        return json.dumps({"error": str(exc)}, indent=2)


# ============================================================================
# TOOL 9 — run_lisa_tests
# ============================================================================

@mcp.tool()
def run_lisa_tests(
    lisa_path: str,
    runbook_path: str,
    variables: dict[str, str] | None = None,
    dry_run: bool = False,
    timeout_seconds: int = 7200,
) -> str:
    """
    Execute LISA tests by invoking the lisa CLI with a runbook.

    ⚠️  WARNING: This will deploy real cloud infrastructure if the runbook
    targets Azure or another cloud platform. Confirm before calling.

    Parameters
    ----------
    lisa_path        : Root of the LISA repository (used as working directory).
    runbook_path     : Path to the runbook YAML to run.
    variables        : Additional -v name:value overrides for the run.
    dry_run          : Pass dry_run:true variable (informational; not a LISA flag).
    timeout_seconds  : Subprocess timeout in seconds (default 7200 = 2 hours).

    Returns JSON with success status, return code, stdout, and stderr.
    """
    result = run_tests(
        lisa_path=lisa_path,
        runbook_path=runbook_path,
        variables=variables,
        dry_run=dry_run,
        timeout_seconds=timeout_seconds,
    )
    return json.dumps(result, indent=2)


# ============================================================================
# TOOL 10 — parse_test_results
# ============================================================================

@mcp.tool()
def parse_test_results(source: str) -> str:
    """
    Parse LISA test results from a JUnit XML file path OR raw console output.

    Parameters
    ----------
    source : Either a file path to a JUnit XML file (e.g. ./lisa_results.xml)
             or a raw string of console output from a LISA run.

    Returns JSON with total/passed/failed/skipped counts and per-test details.
    """
    try:
        summary = parse_results(source)
        return json.dumps(
            {
                "summary_line": summarize(summary),
                "total": summary.total,
                "passed": summary.passed,
                "failed": summary.failed,
                "skipped": summary.skipped,
                "errors": summary.errors,
                "duration_seconds": summary.duration_seconds,
                "results": [r.model_dump() for r in summary.results],
            },
            indent=2,
        )
    except Exception as exc:
        return json.dumps({"error": str(exc)}, indent=2)


# ============================================================================
# TOOL 11 — check_lisa_environment
# ============================================================================

@mcp.tool()
def check_lisa_environment() -> str:
    """
    Check whether the LISA CLI is installed and available on PATH.

    Returns JSON with installed status, path, and version information.
    """
    info = check_lisa_installed()
    return json.dumps(info, indent=2)


# ============================================================================
# TOOL 12 — get_tier_info
# ============================================================================

@mcp.tool()
def get_tier_info() -> str:
    """
    Return information about LISA's test tier system (T0–T4).

    Tiers define a priority range and resource budget:
      T0 → P0 only, ~5 min, 1 environment
      T1 → P0–P1, ~2 hours, 2 environments
      T2 → P0–P2, ~8 hours, 2 environments
      T3 → P0–P3, ~16 hours
      T4 → All tests (no time/resource limit)
    """
    tiers = {
        "T0": {
            "priorities": TIER_PRIORITIES["T0"],
            "description": "P0 (critical) tests only — smoke tests, ~5 minutes, 1 environment",
            "use_case": "Fast gate-check before merge or image publishing",
        },
        "T1": {
            "priorities": TIER_PRIORITIES["T1"],
            "description": "P0–P1 tests — ~2 hours, up to 2 environments",
            "use_case": "Daily CI runs and pre-release validation",
        },
        "T2": {
            "priorities": TIER_PRIORITIES["T2"],
            "description": "P0–P2 tests — ~8 hours, up to 2 environments",
            "use_case": "Weekly regression suites",
        },
        "T3": {
            "priorities": TIER_PRIORITIES["T3"],
            "description": "P0–P3 tests — ~16 hours",
            "use_case": "Full pre-GA validation",
        },
        "T4": {
            "priorities": TIER_PRIORITIES["T4"],
            "description": "All tests including community/informational",
            "use_case": "Complete compliance and certification runs",
        },
    }
    return json.dumps(tiers, indent=2)


# ============================================================================
# TOOL 13 — build_tier_runbook_file
# ============================================================================

@mcp.tool()
def build_tier_runbook_file(
    tier: str,
    platform_type: str = "azure",
    output_path: str | None = None,
    image: str = "ubuntu focal 20.04-lts latest",
    extra_variables: dict[str, str] | None = None,
) -> str:
    """
    Build a standard tier-based LISA runbook (the most common use-case).

    Parameters
    ----------
    tier          : "T0" | "T1" | "T2" | "T3" | "T4"
    platform_type : "azure" | "hyperv" | "ready"
    output_path   : If provided, write the YAML to this path.
    image         : OS image/marketplace string.
    extra_variables: Additional variables to embed in the runbook.

    Returns the YAML string (and writes to disk if output_path given).
    """
    yaml_str = build_tier_runbook(
        tier=tier,
        platform_type=platform_type,
        output_path=output_path,
        extra_variables=extra_variables,
        image=image,
    )
    result = {"tier": tier, "yaml": yaml_str}
    if output_path:
        result["written_to"] = output_path
    return json.dumps(result, indent=2)


# ============================================================================
# RESOURCES — static reference material
# ============================================================================

@mcp.resource("lisa://test-case-template")
def test_case_template() -> str:
    """Minimal Python template for a new LISA test case."""
    return """\
# Paste this inside a class decorated with @TestSuiteMetadata

@TestCaseMetadata(
    description="TODO: Describe what this test verifies",
    priority=2,
    timeout=3600,
    use_new_environment=False,
    requirement=simple_requirement(
        # min_core_count=2,
        # supported_platform_type=[AZURE],
    ),
)
def my_test_name(
    self,
    case_name: str,
    node: Node,
    environment: Environment,
    log: Logger,
) -> None:
    result = node.execute("echo 'hello from LISA'", expected_exit_code=0)
    assert_that(result.stdout).contains("hello")
"""


@mcp.resource("lisa://test-suite-template")
def test_suite_template() -> str:
    """Minimal Python template for a new LISA test suite."""
    return """\
from __future__ import annotations

from logging import Logger
from typing import Any

from lisa import (
    Environment,
    Node,
    TestCaseMetadata,
    TestSuite,
    TestSuiteMetadata,
    simple_requirement,
    assert_that,
)


@TestSuiteMetadata(
    area="myarea",
    category="functional",
    description="TODO: Describe this test suite",
    owner="TODO: Your name or team",
)
class MySuiteClassName(TestSuite):

    @TestCaseMetadata(
        description="TODO: Describe this test",
        priority=2,
        timeout=3600,
    )
    def my_first_test(
        self,
        case_name: str,
        node: Node,
        environment: Environment,
        log: Logger,
    ) -> None:
        result = node.execute("uname -r", expected_exit_code=0)
        log.info(f"Kernel version: {result.stdout.strip()}")

    def before_case(self, **kwargs: Any) -> None:
        pass

    def after_case(self, **kwargs: Any) -> None:
        pass
"""


@mcp.resource("lisa://runbook-template")
def runbook_template() -> str:
    """Minimal LISA runbook YAML template."""
    return """\
# LISA Runbook Template
name: My Test Run
concurrency: 1
exit_on_first_failure: false
import_builtin_tests: true

variable:
  - name: location
    value: westus3
  - name: subscription_id
    value: $(subscription_id)

platform:
  - type: azure
    admin_private_key_file: $(admin_private_key_file)
    azure:
      subscription_id: $(subscription_id)
      marketplace: ubuntu focal 20.04-lts latest

testcase:
  - criteria:
      priority: [0, 1]       # Run P0 and P1 tests
  # - criteria:
  #     name: my_test_name   # Run a specific test
  # - criteria:
  #     area: network        # Run all network tests

notifier:
  - type: console
    log_level: INFO
  - type: html
    path: ./lisa_report.html
    auto_open: false
  - type: junit
    path: ./lisa_results.xml
"""


# ============================================================================
# PROMPTS — guided workflows
# ============================================================================

@mcp.prompt()
def select_tests_for_scenario(
    scenario: str,
    platform: str = "azure",
    os_name: str = "Ubuntu",
) -> str:
    """
    Prompt that helps the user choose appropriate LISA tests for a scenario.

    Parameters
    ----------
    scenario : Description of what you want to validate (e.g. "network connectivity").
    platform : Target platform (azure, hyperv, etc.).
    os_name  : Target OS distribution.
    """
    return f"""\
I need to select appropriate LISA test cases for the following scenario:

Scenario : {scenario}
Platform : {platform}
OS       : {os_name}

Please:
1. Use the `discover_test_cases` tool to search for relevant tests
2. Filter by area and platform as appropriate
3. Recommend which tests to include and at what priority tier
4. Generate a runbook YAML using `build_runbook` that covers these tests
5. Explain why each recommended test is relevant to the scenario
"""


@mcp.prompt()
def create_new_test(
    feature_name: str,
    area: str,
    what_to_validate: str,
) -> str:
    """
    Prompt that guides writing a new LISA test case.

    Parameters
    ----------
    feature_name      : Name of the feature being tested.
    area              : LISA area (e.g. "network", "storage", "cpu").
    what_to_validate  : What the test should verify.
    """
    return f"""\
I need to write a new LISA test case for:

Feature         : {feature_name}
Area            : {area}
What to validate: {what_to_validate}

Please:
1. Use `get_tier_info` to understand priority levels and pick the right one
2. Use `generate_test_suite_code` to generate a Python test suite with:
   - A clear @TestSuiteMetadata decorator with area="{area}"
   - At least one test method decorated with @TestCaseMetadata
   - Proper node.execute() calls to validate: {what_to_validate}
   - Appropriate requirements (OS, platform, hardware)
3. Explain the test logic and how it validates {what_to_validate}
4. Show how to add this test to a runbook
"""


@mcp.prompt()
def analyze_test_failure(failure_output: str) -> str:
    """
    Prompt that analyzes LISA test failure output and suggests fixes.

    Parameters
    ----------
    failure_output : The stdout/stderr or error message from the failed test run.
    """
    return f"""\
The following LISA test failure occurred. Please analyze it and provide guidance:

--- FAILURE OUTPUT ---
{failure_output}
--- END OUTPUT ---

Please:
1. Use `parse_test_results` to extract structured failure information
2. Identify the root cause of the failure
3. Suggest specific fixes or debugging steps
4. If it's an environment/configuration issue, show the corrected runbook YAML
5. If it's a test code issue, show the corrected test code
"""


# ============================================================================
# Entry point
# ============================================================================

def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
