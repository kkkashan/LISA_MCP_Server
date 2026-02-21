"""Pydantic models representing LISA framework concepts."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Priority(int, Enum):
    P0 = 0  # Critical — must pass
    P1 = 1  # High
    P2 = 2  # Medium
    P3 = 3  # Low
    P4 = 4  # Informational
    P5 = 5  # Optional


class Category(str, Enum):
    FUNCTIONAL = "functional"
    PERFORMANCE = "performance"
    STRESS = "stress"
    COMMUNITY = "community"


class Tier(str, Enum):
    T0 = "T0"  # P0 only, ≤5 min, 1 env
    T1 = "T1"  # P0-P1, ≤2 h, 2 envs
    T2 = "T2"  # P0-P2, ≤8 h, 2 envs
    T3 = "T3"  # P0-P3, ≤16 h
    T4 = "T4"  # All tests


TIER_PRIORITIES: dict[str, list[int]] = {
    "T0": [0],
    "T1": [0, 1],
    "T2": [0, 1, 2],
    "T3": [0, 1, 2, 3],
    "T4": [0, 1, 2, 3, 4, 5],
}


class Requirement(BaseModel):
    min_core_count: int | None = None
    min_memory_mb: int | None = None
    min_disk_space_gb: int | None = None
    supported_features: list[str] = Field(default_factory=list)
    unsupported_os: list[str] = Field(default_factory=list)
    supported_platform_type: list[str] = Field(default_factory=list)
    environment_status: str | None = None


class TestCaseInfo(BaseModel):
    """Metadata about a single LISA test case."""

    name: str
    method_name: str
    suite_name: str
    file_path: str
    area: str
    category: str
    description: str
    priority: int
    timeout: int = 3600
    use_new_environment: bool = False
    requirement: Requirement = Field(default_factory=Requirement)
    tags: list[str] = Field(default_factory=list)
    owner: str = ""


class TestSuiteInfo(BaseModel):
    """Metadata about a LISA test suite."""

    name: str
    file_path: str
    area: str
    category: str
    description: str
    owner: str
    test_cases: list[TestCaseInfo] = Field(default_factory=list)


class RunbookVariable(BaseModel):
    name: str
    value: Any = None
    file: str | None = None
    is_secret: bool = False


class RunbookTestCriteria(BaseModel):
    name: str | None = None
    area: str | None = None
    priority: list[int] | None = None
    tags: list[str] | None = None
    select_action: str = "include"  # include | exclude
    retry: int = 0
    times: int = 1
    timeout: int | None = None


class RunbookConfig(BaseModel):
    """Complete runbook configuration."""

    name: str
    test_project: str = ""
    test_pass: str = ""
    concurrency: int = 1
    exit_on_first_failure: bool = False
    import_builtin_tests: bool = True
    variables: list[RunbookVariable] = Field(default_factory=list)
    platform_type: str = "azure"
    platform_config: dict[str, Any] = Field(default_factory=dict)
    test_criteria: list[RunbookTestCriteria] = Field(default_factory=list)
    notifiers: list[str] = Field(default_factory=list)
    extensions: list[str] = Field(default_factory=list)


class TestResult(BaseModel):
    """Parsed result for a single test case."""

    name: str
    status: str  # passed | failed | skipped | error
    duration_seconds: float = 0.0
    message: str = ""
    stack_trace: str = ""
    suite_name: str = ""


class TestRunSummary(BaseModel):
    """Summary of a complete test run."""

    total: int
    passed: int
    failed: int
    skipped: int
    errors: int
    duration_seconds: float
    results: list[TestResult] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# LLM analysis models
# ---------------------------------------------------------------------------

class RootCauseCategory(str, Enum):
    """Failure category the LLM selects for each failed test."""
    KERNEL_PANIC       = "kernel_panic"
    NETWORK_TIMEOUT    = "network_timeout"
    DISK_IO_ERROR      = "disk_io_error"
    PERMISSION_DENIED  = "permission_denied"
    PACKAGE_NOT_FOUND  = "package_not_found"
    SERVICE_CRASH      = "service_crash"
    ASSERTION_FAILURE  = "assertion_failure"
    TIMEOUT            = "timeout"
    ENVIRONMENT_SETUP  = "environment_setup"
    FLAKY_TEST         = "flaky_test"
    INFRASTRUCTURE     = "infrastructure"
    UNKNOWN            = "unknown"


class FailureSeverity(str, Enum):
    """Business impact of a single test failure."""
    CRITICAL = "critical"   # Blocks release / data loss
    HIGH     = "high"       # Major feature broken
    MEDIUM   = "medium"     # Partial functionality impacted
    LOW      = "low"        # Minor / informational


# Severity sort key — lower = more severe
_SEVERITY_ORDER: dict[str, int] = {
    "critical": 0, "high": 1, "medium": 2, "low": 3
}


class FailureAnalysis(BaseModel):
    """Structured LLM analysis for a single failed test case."""
    test_name:               str
    root_cause_category:     RootCauseCategory = RootCauseCategory.UNKNOWN
    root_cause_description:  str = ""
    recommended_fix:         str = ""
    severity:                FailureSeverity = FailureSeverity.MEDIUM
    relevant_log_lines:      list[str] = Field(default_factory=list)
    confidence:              float = 0.0

    @property
    def severity_order(self) -> int:
        return _SEVERITY_ORDER.get(self.severity.value, 99)


class RunAnalysisSummary(BaseModel):
    """Run-level summary produced by the LLM after analyzing all failures."""
    overall_health:     str          = "unknown"   # healthy|degraded|critical|unknown
    health_score:       float        = 0.0          # 0.0–1.0 pass-rate weighted by severity
    failure_patterns:   list[str]    = Field(default_factory=list)
    top_priorities:     list[str]    = Field(default_factory=list)
    environment_issues: list[str]    = Field(default_factory=list)
    recommendations:    list[str]    = Field(default_factory=list)
    executive_summary:  str          = ""


class AnalysisReport(BaseModel):
    """Complete analysis report combining run metrics + LLM analysis."""
    run_dir:          str | None    = None
    generated_at:     str           = ""
    total:            int           = 0
    passed:           int           = 0
    failed:           int           = 0
    skipped:          int           = 0
    errors:           int           = 0
    duration_seconds: float         = 0.0
    summary:          RunAnalysisSummary = Field(default_factory=RunAnalysisSummary)
    failure_analyses: list[FailureAnalysis] = Field(default_factory=list)
