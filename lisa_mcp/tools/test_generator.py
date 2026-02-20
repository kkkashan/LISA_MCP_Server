"""
Test generator: produce Python source code for new LISA test suites and cases.
"""

from __future__ import annotations

from textwrap import dedent, indent
from typing import Any


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

def _format_requirement(req: dict[str, Any]) -> str:
    """Render a simple_requirement(...) call string from a dict."""
    parts: list[str] = []

    if req.get("environment_status"):
        parts.append(f"environment_status=EnvironmentStatus.{req['environment_status']}")
    if req.get("min_core_count"):
        parts.append(f"min_core_count={req['min_core_count']}")
    if req.get("min_memory_mb"):
        parts.append(f"min_memory_mb={req['min_memory_mb']}")
    if req.get("min_disk_space_gb"):
        parts.append(f"min_disk_space_gb={req['min_disk_space_gb']}")
    if req.get("supported_features"):
        features = ", ".join(req["supported_features"])
        parts.append(f"supported_features=[{features}]")
    if req.get("unsupported_os"):
        oses = ", ".join(req["unsupported_os"])
        parts.append(f"unsupported_os=[{oses}]")
    if req.get("supported_platform_type"):
        platforms = ", ".join(req["supported_platform_type"])
        parts.append(f"supported_platform_type=[{platforms}]")

    if not parts:
        return "simple_requirement()"
    inner = ",\n        ".join(parts)
    return f"simple_requirement(\n        {inner}\n    )"


def generate_test_case_code(
    method_name: str,
    description: str,
    priority: int = 2,
    timeout: int = 3600,
    use_new_environment: bool = False,
    requirement: dict[str, Any] | None = None,
    body_lines: list[str] | None = None,
) -> str:
    """Return the source code for a single test-case method."""
    req_str = _format_requirement(requirement or {})
    body = "\n        ".join(body_lines) if body_lines else 'node.execute("echo hello", expected_exit_code=0)'

    code = f'''\
    @TestCaseMetadata(
        description="{description}",
        priority={priority},
        timeout={timeout},
        use_new_environment={use_new_environment},
        requirement={req_str},
    )
    def {method_name}(
        self,
        case_name: str,
        node: Node,
        environment: Environment,
        log: Logger,
    ) -> None:
        {body}
'''
    return code


def generate_test_suite(
    suite_class_name: str,
    area: str,
    category: str,
    description: str,
    owner: str,
    test_cases: list[dict[str, Any]],
    file_name: str | None = None,
) -> str:
    """
    Generate a complete Python source file containing a LISA test suite.

    Parameters
    ----------
    suite_class_name: PascalCase class name, e.g. "StorageVerification"
    area: functional domain, e.g. "storage"
    category: "functional" | "performance" | "stress" | "community"
    description: Human-readable description of the suite
    owner: Owner/team name
    test_cases: list of dicts, each with keys:
        - method_name (str, required)
        - description (str, required)
        - priority (int, default 2)
        - timeout (int, default 3600)
        - use_new_environment (bool, default False)
        - requirement (dict, optional)
        - body_lines (list[str], optional)
    file_name: Optional filename hint for the module docstring
    """
    # Collect feature/os imports that may be needed
    all_features: set[str] = set()
    all_os: set[str] = set()
    all_platforms: set[str] = set()

    for tc in test_cases:
        req = tc.get("requirement") or {}
        all_features.update(req.get("supported_features") or [])
        all_os.update(req.get("unsupported_os") or [])
        all_platforms.update(req.get("supported_platform_type") or [])

    # Build feature imports comment
    feature_comment = ""
    if all_features:
        feature_comment = (
            "# Import features you declared in requirements:\n"
            + "".join(f"# from lisa.features import {f}\n" for f in sorted(all_features))
        )

    # Build test method blocks
    methods_code = "\n".join(
        generate_test_case_code(
            method_name=tc["method_name"],
            description=tc.get("description", "TODO: describe this test"),
            priority=tc.get("priority", 2),
            timeout=tc.get("timeout", 3600),
            use_new_environment=tc.get("use_new_environment", False),
            requirement=tc.get("requirement"),
            body_lines=tc.get("body_lines"),
        )
        for tc in test_cases
    )

    file_header = f'# Generated test suite file: {file_name or suite_class_name.lower() + ".py"}'

    source = f'''\
{file_header}
"""
{description}
"""

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
)
from lisa.environment import EnvironmentStatus
{feature_comment}

@TestSuiteMetadata(
    area="{area}",
    category="{category}",
    description="{description}",
    owner="{owner}",
)
class {suite_class_name}(TestSuite):
    """
    {description}
    """

{methods_code}
    def before_case(self, **kwargs: Any) -> None:
        """Runs before each test case. Raise an exception to skip the case."""
        pass

    def after_case(self, **kwargs: Any) -> None:
        """Runs after each test case regardless of outcome."""
        pass
'''
    return source


def generate_runbook_yaml(
    name: str,
    platform_type: str = "azure",
    tier: str | None = None,
    test_names: list[str] | None = None,
    excluded_names: list[str] | None = None,
    priorities: list[int] | None = None,
    variables: dict[str, str] | None = None,
    notifiers: list[str] | None = None,
    subscription_id: str = "$(subscription_id)",
    location: str = "westus3",
    image: str = "ubuntu focal 20.04-lts latest",
    concurrency: int = 1,
    output_path: str | None = None,
) -> str:
    """
    Generate a LISA runbook YAML string.

    Returns the YAML source as a string so the caller can write it to disk
    or pass it back to the LLM.
    """
    from lisa_mcp.models import TIER_PRIORITIES
    import yaml  # only needed at call time

    doc: dict[str, Any] = {
        "name": name,
        "concurrency": concurrency,
        "exit_on_first_failure": False,
        "import_builtin_tests": True,
    }

    # Variables
    var_list: list[Any] = []
    if platform_type == "azure":
        var_list.append({"name": "location", "value": location})
        var_list.append({"name": "subscription_id", "value": subscription_id})
    if variables:
        for k, v in variables.items():
            var_list.append({"name": k, "value": v})
    if var_list:
        doc["variable"] = var_list

    # Platform
    if platform_type == "azure":
        doc["platform"] = [
            {
                "type": "azure",
                "admin_private_key_file": "$(admin_private_key_file)",
                "azure": {
                    "subscription_id": "$(subscription_id)",
                    "marketplace": image,
                },
            }
        ]
    elif platform_type == "ready":
        doc["platform"] = [{"type": "ready"}]
    else:
        doc["platform"] = [{"type": platform_type}]

    # Test criteria
    criteria: list[dict[str, Any]] = []

    # Tier → priority mapping
    effective_priorities = priorities
    if tier and tier.upper() in TIER_PRIORITIES:
        effective_priorities = TIER_PRIORITIES[tier.upper()]

    if effective_priorities is not None:
        criteria.append({"criteria": {"priority": effective_priorities}})

    for tname in test_names or []:
        criteria.append({"criteria": {"name": tname}})

    for ename in excluded_names or []:
        criteria.append({"criteria": {"name": ename}, "select_action": "exclude"})

    if criteria:
        doc["testcase"] = criteria

    # Notifiers
    notifier_list: list[dict[str, Any]] = [{"type": "console", "log_level": "INFO"}]
    for n in notifiers or []:
        if n == "html":
            notifier_list.append({"type": "html", "path": "./lisa_report.html", "auto_open": False})
        elif n == "junit":
            notifier_list.append({"type": "junit", "path": "./lisa_results.xml"})
    doc["notifier"] = notifier_list

    # Dump YAML with sensible formatting
    yaml_str = yaml.dump(doc, default_flow_style=False, sort_keys=False, allow_unicode=True)

    header = f"# LISA Runbook — generated by lisa-mcp-server\n# Platform: {platform_type}\n\n"
    return header + yaml_str
