"""
Log collector — walk a LISA run directory and extract per-test error context.

Safety guarantees
-----------------
- Never loads a whole log file into memory.
- Seek-based tail reading: at most MAX_TAIL_BYTES per file.
- Hard cap of MAX_CHARS_PER_TEST on the final context snippet per test.
- All file I/O errors are caught and recorded; collection never crashes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Tuneable constants
# ---------------------------------------------------------------------------

MAX_TAIL_BYTES: int = 256 * 1024        # 256 KB tail per log file
ERROR_CONTEXT_LINES: int = 15           # lines of context around each error signal
MAX_CHARS_PER_TEST: int = 8_000         # hard cap on context_snippet length
MAX_TOTAL_CHARS: int = 120_000          # hard cap across the whole run collection

# Error signals — compiled once at import
_ERROR_RE = re.compile(
    r"(ERROR|FAIL(?:ED)?|EXCEPTION|Traceback|AssertionError|CRITICAL|PANIC"
    r"|command.*exit.*code\s*[^0]|returncode.*[^0]\b|stdout.*mismatch"
    r"|connection.*refused|timed?\s*out|permission\s*denied|no\s*such\s*file)",
    re.IGNORECASE,
)

# LISA log directory structures to search
_LOG_SUBDIRS = ["logs", "runtime", "runs", "results", "output"]
_LOG_GLOBS   = ["*.log", "*.txt", "console*.log", "serial*.log"]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TestLogContext:
    """Error context extracted from one test's log files."""
    test_name:         str
    log_files_found:   list[str]
    error_lines:       list[str]       # deduped lines near error signals
    context_snippet:   str             # final text for the LLM
    total_log_bytes:   int
    truncated:         bool = False


@dataclass
class RunLogCollection:
    """All log contexts from a single LISA run directory."""
    run_dir:                  str
    junit_xml_path:           str | None
    console_log_path:         str | None
    test_contexts:            list[TestLogContext]           = field(default_factory=list)
    unmatched_log_files:      list[str]                     = field(default_factory=list)
    errors_during_collection: list[str]                     = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def collect_run_logs(
    run_dir: str,
    max_tail_bytes:        int = MAX_TAIL_BYTES,
    error_context_lines:   int = ERROR_CONTEXT_LINES,
    max_chars_per_test:    int = MAX_CHARS_PER_TEST,
    failed_test_names:     list[str] | None = None,
) -> RunLogCollection:
    """
    Walk *run_dir* and collect error context for all (or specified) tests.

    Parameters
    ----------
    run_dir             : Path to a LISA run output directory.
    max_tail_bytes      : Bytes to read from the tail of each log file.
    error_context_lines : Context window around each error signal.
    max_chars_per_test  : Hard cap on context_snippet per test.
    failed_test_names   : Only collect logs for these tests (substring match).
                          None = collect for all tests found.
    """
    root = Path(run_dir)
    collection = RunLogCollection(
        run_dir=str(root.resolve()),
        junit_xml_path=None,
        console_log_path=None,
    )

    if not root.is_dir():
        collection.errors_during_collection.append(
            f"Run directory not found: {run_dir}"
        )
        return collection

    # Locate top-level artifacts
    junit_path, console_path = _find_run_artifacts(root)
    collection.junit_xml_path   = str(junit_path)   if junit_path   else None
    collection.console_log_path = str(console_path) if console_path else None

    # Find test-specific log directories
    test_dirs = _find_test_log_dirs(root)
    total_chars = 0

    for test_dir in sorted(test_dirs):
        test_name = test_dir.name

        # Filter to requested tests only
        if failed_test_names:
            if not any(fn.lower() in test_name.lower() for fn in failed_test_names):
                continue

        # Stop if total context budget exhausted
        if total_chars >= MAX_TOTAL_CHARS:
            break

        log_files = _find_log_files_for_test(test_dir)
        if not log_files:
            continue

        all_error_lines: list[str] = []
        all_bytes = 0

        for log_file in log_files:
            try:
                lines, nbytes = extract_error_context(
                    str(log_file),
                    max_tail_bytes=max_tail_bytes,
                    context_lines=error_context_lines,
                )
                all_error_lines.extend(lines)
                all_bytes += nbytes
            except Exception as exc:
                collection.errors_during_collection.append(
                    f"Error reading {log_file}: {exc}"
                )

        # Deduplicate while preserving order
        seen: set[str] = set()
        deduped: list[str] = []
        for line in all_error_lines:
            if line not in seen:
                seen.add(line)
                deduped.append(line)

        snippet = "\n".join(deduped)
        truncated = False
        if len(snippet) > max_chars_per_test:
            snippet = snippet[:max_chars_per_test] + "\n... [truncated]"
            truncated = True

        ctx = TestLogContext(
            test_name=test_name,
            log_files_found=[str(f) for f in log_files],
            error_lines=deduped,
            context_snippet=snippet,
            total_log_bytes=all_bytes,
            truncated=truncated,
        )
        collection.test_contexts.append(ctx)
        total_chars += len(snippet)

    # Record any .log files not associated with a test directory
    all_test_log_paths = {
        f
        for td in test_dirs
        for f in _find_log_files_for_test(td)
    }
    for log_file in root.rglob("*.log"):
        if log_file not in all_test_log_paths and log_file != console_path:
            collection.unmatched_log_files.append(str(log_file))

    return collection


def extract_error_context(
    log_path: str,
    max_tail_bytes: int = MAX_TAIL_BYTES,
    context_lines:  int = ERROR_CONTEXT_LINES,
) -> tuple[list[str], int]:
    """
    Read the tail of *log_path* and extract lines near error signals.

    Returns (error_context_lines, file_size_bytes).
    File size is the total file size, not the number of bytes read.
    """
    lines, file_size = _tail_read_lines(Path(log_path), max_tail_bytes)
    if not lines:
        return [], file_size

    # Find indices of lines matching error signals
    hit_indices: list[int] = [
        i for i, line in enumerate(lines) if _ERROR_RE.search(line)
    ]

    if not hit_indices:
        # No error signals found — return last few lines as fallback
        return lines[-min(context_lines, len(lines)):], file_size

    # Build context windows around each hit, merge overlapping windows
    selected: list[str] = []
    covered:  set[int]  = set()
    for hit in hit_indices:
        start = max(0, hit - context_lines)
        end   = min(len(lines), hit + context_lines + 1)
        for i in range(start, end):
            if i not in covered:
                covered.add(i)
                selected.append(lines[i])

    return selected, file_size


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _tail_read_lines(path: Path, max_bytes: int) -> tuple[list[str], int]:
    """Read the last *max_bytes* of *path*. Returns (lines, total_file_bytes)."""
    try:
        file_size = path.stat().st_size
    except OSError:
        return [], 0

    try:
        with path.open("rb") as fh:
            seek_pos = max(0, file_size - max_bytes)
            fh.seek(seek_pos)
            raw = fh.read(max_bytes)
        text = raw.decode("utf-8", errors="replace")
        # Drop the first (possibly partial) line when we didn't start at offset 0
        lines = text.splitlines()
        if seek_pos > 0 and lines:
            lines = lines[1:]   # discard partial first line
        return lines, file_size
    except OSError:
        return [], 0


def _find_log_files_for_test(test_dir: Path) -> list[Path]:
    """Return log files in *test_dir*, newest first."""
    files: list[Path] = []
    for glob in _LOG_GLOBS:
        files.extend(test_dir.rglob(glob))
    # Sort: newest modification time first, then alphabetical
    files.sort(key=lambda p: (-p.stat().st_mtime if p.exists() else 0, p.name))
    return files


def _find_test_log_dirs(root: Path) -> list[Path]:
    """
    Find directories that represent individual test runs inside *root*.

    LISA stores logs in:
      <root>/logs/<SuiteName>/<test_method>/
      <root>/runtime/<timestamp>/<test_name>/
    We return the leaf directories that contain at least one .log file.
    """
    candidates: list[Path] = []

    # Direct sub-dirs of standard log locations
    for subdir_name in _LOG_SUBDIRS:
        subdir = root / subdir_name
        if subdir.is_dir():
            for child in subdir.iterdir():
                if child.is_dir():
                    candidates.append(child)
                    # One level deeper for SuiteName/MethodName layout
                    for grandchild in child.iterdir():
                        if grandchild.is_dir():
                            candidates.append(grandchild)

    # Fallback: any directory at depth 1-2 that has .log files directly
    if not candidates:
        for depth1 in root.iterdir():
            if depth1.is_dir() and list(depth1.glob("*.log")):
                candidates.append(depth1)

    # Only return dirs that actually have log files
    return [d for d in candidates if any(d.rglob("*.log"))]


def _find_run_artifacts(root: Path) -> tuple[Path | None, Path | None]:
    """Locate JUnit XML and console log in *root*."""
    # JUnit XML
    junit: Path | None = None
    for candidate in [
        root / "lisa_results.xml",
        root / "results.xml",
    ]:
        if candidate.exists():
            junit = candidate
            break
    if junit is None:
        xml_files = list(root.glob("*.xml"))
        if xml_files:
            junit = max(xml_files, key=lambda p: p.stat().st_mtime)

    # Console log
    console: Path | None = None
    for name in ["console.log", "stdout.log", "lisa.log", "run.log"]:
        candidate = root / name
        if candidate.exists():
            console = candidate
            break
    if console is None:
        log_files = [f for f in root.glob("*.log") if f.is_file()]
        if log_files:
            console = max(log_files, key=lambda p: p.stat().st_mtime)

    return junit, console
