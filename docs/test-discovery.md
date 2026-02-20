# Test Discovery — How It Works

This document explains the internals of the `discover_test_cases` and `search_tests`
tools: how they scan a LISA repository, what they extract, and how filtering works.

---

## Overview

Test discovery uses **Python AST (Abstract Syntax Tree) parsing** to scan `.py` files.
This means:

- **No LISA installation required** — just a cloned repository
- **No Python imports executed** — no risk of import errors or side effects
- **Fast** — scans hundreds of files in seconds
- **Safe** — read-only, never modifies any file

---

## What the scanner looks for

The scanner walks all `.py` files in the given `lisa_path` directory tree, looking for
two specific Python decorators:

### `@TestSuiteMetadata`

Applied to a **class** that extends `TestSuite`. Marks it as a test suite.

```python
@TestSuiteMetadata(
    area="network",
    category="functional",
    description="Verifies Linux network interface health",
    owner="Microsoft",
)
class NetworkConnectivity(TestSuite):
    ...
```

The scanner extracts: `area`, `category`, `description`, `owner`.

### `@TestCaseMetadata`

Applied to a **method** inside a `TestSuite` class. Marks it as an individual test case.

```python
@TestCaseMetadata(
    description="Verifies ICMP connectivity to default gateway",
    priority=0,
    timeout=300,
    use_new_environment=False,
    requirement=simple_requirement(
        min_core_count=2,
        supported_platform_type=[AZURE],
        unsupported_os=[Windows, BSD],
    ),
)
def verify_ping(self, case_name, node, environment, log):
    ...
```

The scanner extracts: `description`, `priority`, `timeout`, `use_new_environment`,
and the contents of the `requirement=simple_requirement(...)` call.

---

## AST parsing — step by step

For each `.py` file the scanner:

1. **Reads the file** as text (no import)
2. **Parses it** with `ast.parse()` to get a syntax tree
3. **Walks the tree** looking for `ast.ClassDef` nodes
4. For each class, checks if it has an `@TestSuiteMetadata(...)` decorator
5. If yes, extracts the keyword arguments from the decorator call
6. Then walks the class body looking for `ast.FunctionDef` nodes
7. For each method, checks for `@TestCaseMetadata(...)` and extracts its args
8. The `requirement=simple_requirement(...)` argument is parsed recursively:
   - The `ast.Call` node for `simple_requirement(...)` is detected
   - Each keyword argument (`min_core_count=4`, `supported_platform_type=[AZURE]`, etc.)
     is evaluated from its AST node into a Python value

### Handling complex AST nodes

The `_eval_ast_node` function handles:

| AST node type | Example | Returns |
|---------------|---------|---------|
| `ast.Constant` | `"network"`, `0`, `True` | The literal value |
| `ast.List` | `[AZURE, HYPERV]` | A Python list |
| `ast.Name` | `AZURE`, `True` | The identifier string `"AZURE"` |
| `ast.Attribute` | `EnvironmentStatus.Deployed` | `"EnvironmentStatus.Deployed"` |
| `ast.Call` | `simple_requirement(...)` | Dict with `__call__` key |

---

## Directory exclusions

The scanner automatically skips these directories to avoid noise and performance issues:

```python
EXCLUDED_DIRS = {".venv", "venv", "__pycache__", "build", "dist", ".git"}
```

Any file whose path contains one of these directory names is skipped.

---

## Filtering logic

After scanning, results are filtered in this order:

### 1. Area filter

```python
if area and suite.area.lower() != area.lower():
    skip suite
```

Areas are case-insensitive. `area="Network"` and `area="network"` both work.

### 2. Tier / priority filter

Tier maps to a list of priorities:
```python
T0 → [0]
T1 → [0, 1]
T2 → [0, 1, 2]
T3 → [0, 1, 2, 3]
T4 → [0, 1, 2, 3, 4, 5]
```

A test case is included if its `priority` is in the filter list.

If both `tier` and `priority` are given, `tier` takes precedence.

### 3. Platform filter

```python
# A test passes the platform filter if:
# (a) it has no supported_platform_type restriction, OR
# (b) the requested platform is in its supported_platform_type list
```

Platform names are case-insensitive.

### 4. Name pattern filter

```python
if name_pattern.lower() in tc.name.lower():   # name substring match
    include
elif name_pattern.lower() in tc.description.lower():  # description match
    include
elif fnmatch.fnmatch(tc.name.lower(), name_pattern.lower()):  # glob pattern
    include
```

Example patterns:
- `"ping"` — matches any test with "ping" in name or description
- `"verify_*"` — glob: matches any test whose name starts with "verify_"
- `"*nvme*"` — glob: matches any test with "nvme" anywhere in name

---

## Performance

On a full LISA repository checkout (~400 Python files), discovery takes approximately:

| Operation | Time |
|-----------|------|
| Full scan (no filters) | ~3–5 seconds |
| Scan with area filter | ~1–2 seconds |
| Scan with tier T0 | ~0.5 seconds |

The bottleneck is file I/O, not AST parsing. SSDs and WSL2 with Linux-native paths
(e.g. `~/lisa`) are significantly faster than Windows paths (`/mnt/c/...`).

---

## Discovered data model

Each test case is represented as a `TestCaseInfo` Pydantic model:

```python
class TestCaseInfo(BaseModel):
    name: str                      # "SuiteName.method_name"
    method_name: str               # "method_name"
    suite_name: str                # "SuiteName"
    file_path: str                 # absolute path to source file
    area: str                      # from @TestSuiteMetadata
    category: str                  # from @TestSuiteMetadata
    description: str               # from @TestCaseMetadata
    priority: int                  # 0–5
    timeout: int                   # seconds
    use_new_environment: bool
    requirement: Requirement        # parsed from simple_requirement(...)
    tags: list[str]
    owner: str
```

```python
class Requirement(BaseModel):
    min_core_count: int | None
    min_memory_mb: int | None
    min_disk_space_gb: int | None
    supported_features: list[str]
    unsupported_os: list[str]
    supported_platform_type: list[str]
    environment_status: str | None
```

---

## Known limitations

1. **Dynamic decorators** — if a decorator is applied via a variable (`@my_decorator`)
   rather than the literal name `@TestSuiteMetadata(...)`, it won't be detected.

2. **Inherited test cases** — if a test method is defined in a base class and inherited,
   it must have its own `@TestCaseMetadata` in each subclass to be discovered.

3. **`simple_requirement` only** — only the `simple_requirement(...)` factory function
   is parsed. Custom `Requirement` objects constructed other ways won't have their
   fields extracted (they'll have default empty fields).

4. **Syntax errors** — files with Python syntax errors are silently skipped.

5. **String concatenation** — decorator values built from `"part1" + "part2"` won't
   be evaluated (only literals are supported).

---

## Extending the scanner

To add support for additional LISA decorator names:

```python
# In tools/test_discovery.py, update _find_decorator:
def _find_decorator(node, name):
    for dec in node.decorator_list:
        if isinstance(dec, ast.Call):
            func = dec.func
            # Add support for fully qualified names:
            if isinstance(func, ast.Name) and func.id == name:
                return dec
            if isinstance(func, ast.Attribute) and func.attr == name:
                return dec
    return None
```

To add support for a new requirement factory function:

```python
# In _parse_requirement, handle the new function name:
def _parse_requirement(req_raw):
    if not isinstance(req_raw, dict):
        return Requirement()
    call_name = req_raw.get("__call__", "")
    if call_name in ("simple_requirement", "my_custom_requirement"):
        # parse kwargs...
```
