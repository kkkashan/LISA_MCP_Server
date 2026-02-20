# Writing New LISA Tests — Step-by-Step Guide

This guide walks through writing new LISA test cases from scratch, using the MCP
server to generate boilerplate and the LISA framework to execute them.

---

## Table of Contents

1. [LISA test anatomy](#1-lisa-test-anatomy)
2. [Setting up your test file](#2-setting-up-your-test-file)
3. [Defining a test suite](#3-defining-a-test-suite)
4. [Defining test cases](#4-defining-test-cases)
5. [Using Node — running commands](#5-using-node--running-commands)
6. [Using Tools — installing and running software](#6-using-tools--installing-and-running-software)
7. [Using Features — platform capabilities](#7-using-features--platform-capabilities)
8. [Writing assertions](#8-writing-assertions)
9. [Requirements — controlling when a test runs](#9-requirements--controlling-when-a-test-runs)
10. [Before and after hooks](#10-before-and-after-hooks)
11. [Multi-node tests](#11-multi-node-tests)
12. [Generating with the MCP server](#12-generating-with-the-mcp-server)
13. [Adding to a runbook](#13-adding-to-a-runbook)
14. [Complete example](#14-complete-example)

---

## 1. LISA test anatomy

A LISA test is a Python method inside a Python class:

```
test suite (class)
├── @TestSuiteMetadata  — defines area, category, description, owner
├── test case (method)
│   ├── @TestCaseMetadata  — defines priority, timeout, requirement
│   └── method body        — runs commands via node.execute(), asserts results
├── test case (method)
│   └── ...
├── before_case()  — setup, runs before every test
└── after_case()   — teardown, runs after every test
```

---

## 2. Setting up your test file

### File location

Custom test suites can go anywhere in the LISA repo. The convention is:

```
lisa/microsoft/testsuites/<your_area_folder>/<your_suite_name>.py
```

For example:
```
lisa/microsoft/testsuites/network/kvp_test.py
lisa/microsoft/testsuites/storage/nvme_performance.py
```

### Required imports

```python
from __future__ import annotations

from logging import Logger
from typing import Any

from lisa import (
    Environment,
    Node,
    TestCaseMetadata,
    TestSuite,
    TestSuiteMetadata,
    assert_that,
    simple_requirement,
)
from lisa.environment import EnvironmentStatus
```

Additional imports as needed:
```python
# Platform types (for requirement filters)
from lisa.util.constants import AZURE, HYPERV, BAREMETAL

# OS types (for unsupported_os)
from lisa.operating_system import BSD, Windows, Debian, Fedora, Ubuntu

# Features
from lisa.features import SerialConsole, Nvme, StartStop, Resize

# Tools
from lisa.tools import Echo, Uname, Lscpu, Dmesg
```

---

## 3. Defining a test suite

```python
@TestSuiteMetadata(
    area="network",            # functional domain — use existing areas or create new ones
    category="functional",     # functional | performance | stress | community
    description="Verifies Linux network interface health and basic connectivity.",
    owner="your-team-name",    # who owns this suite
)
class MyNetworkTests(TestSuite):
    """Optional class docstring."""
    pass
```

### `area` values (existing in LISA)

```
cpu        core       hyperv     kdump      memory
network    nvme       perf_network  perf_storage  provisioning
resizing   security   storage    sriov      startstop
stress     vhd        xdp
```

You can also create new areas.

### `category` values

| Value | Use for |
|-------|---------|
| `functional` | Correctness checks, smoke tests, feature verification |
| `performance` | Throughput, latency, IOPS benchmarks |
| `stress` | Long-running, resource-intensive, stability tests |
| `community` | Tests contributed by the community, non-critical |

---

## 4. Defining test cases

```python
@TestCaseMetadata(
    description="Verifies at least one non-loopback interface is UP.",
    priority=0,                          # 0=critical, 1=high, 2=medium, 3=low, 4-5=info
    timeout=300,                         # seconds; test is killed if exceeded
    use_new_environment=False,           # True = dedicate a fresh VM to this test
    requirement=simple_requirement(
        environment_status=EnvironmentStatus.Deployed,
    ),
)
def verify_interface_up(
    self,
    case_name: str,         # injected: full test name e.g. "MyNetworkTests.verify_interface_up"
    node: Node,             # injected: the Linux VM under test
    environment: Environment,  # injected: all nodes + platform
    log: Logger,            # injected: Python logger for this test
) -> None:
    result = node.execute("ip link show | grep -c 'state UP'")
    count = int(result.stdout.strip())
    assert_that(count).described_as("UP interface count").is_greater_than(0)
```

### Priority guidance

| Priority | Meaning | When used |
|----------|---------|-----------|
| 0 | Critical — blocking | Core boot, SSH access, network reachability |
| 1 | High | Feature-level correctness (NVMe present, CPU count correct) |
| 2 | Medium | Integration tests, configuration checks |
| 3 | Low | Edge cases, less common configurations |
| 4 | Informational | Benchmarks, data collection |
| 5 | Optional | Community tests, experimental |

### `timeout` guidance

```python
timeout=120      # Simple commands (ping, uname, ip)
timeout=600      # File I/O, package installation
timeout=3600     # Default — complex operations
timeout=7200     # Performance benchmarks, stress tests
```

### `use_new_environment`

```python
use_new_environment=False   # Default: share VM with other tests in the suite (faster)
use_new_environment=True    # Spin up a fresh VM just for this test (isolated, slower)
```

Use `True` when:
- The test modifies system configuration that would affect other tests
- The test requires a clean state (e.g. tests first boot behavior)
- The test is destructive (reboots, disk reformatting)

---

## 5. Using Node — running commands

`node` is your primary interface to the Linux VM.

### Basic command execution

```python
# Simple command
result = node.execute("uname -r")
print(result.stdout)   # "5.15.0-1040-azure"
print(result.returncode)  # 0

# Expect specific exit code (raises assertion if different)
result = node.execute("ls /etc/ssh", expected_exit_code=0)

# Run as root
result = node.execute("cat /etc/shadow", sudo=True)

# With timeout override
result = node.execute("sleep 5", timeout=10)

# Capture stderr too
result = node.execute("command_that_may_fail 2>&1")
```

### Handling command results

```python
result = node.execute("df -h /")

# Available attributes:
result.stdout        # string: standard output
result.stderr        # string: standard error
result.exit_code     # int: process exit code (also returncode)
result.returncode    # same as exit_code
```

### Working with output

```python
# Get CPU count
result = node.execute("nproc")
cpu_count = int(result.stdout.strip())

# Get disk free space in bytes
result = node.execute("df --block-size=1 / | awk 'NR==2 {print $4}'")
free_bytes = int(result.stdout.strip())

# Check if a process is running
result = node.execute("pgrep sshd")
is_running = result.exit_code == 0

# Multi-line output
result = node.execute("ls /dev/nvme*")
nvme_devices = [line.strip() for line in result.stdout.splitlines() if line.strip()]
```

### File operations on the node

```python
# Upload a local file to the node
node.shell.copy_to_remote(local_path=Path("/tmp/script.sh"), remote_path=PurePosixPath("/tmp/script.sh"))

# Read a file from the node
content = node.execute("cat /etc/os-release").stdout

# Write a file on the node
node.execute("echo 'hello' > /tmp/testfile")
```

---

## 6. Using Tools — installing and running software

LISA has a `tools` registry. Accessing `node.tools[ToolClass]` auto-installs the
tool if it's not present.

```python
from lisa.tools import Lscpu, Dmesg, Iperf3, Fio

# Get tool (installs automatically if missing)
lscpu = node.tools[Lscpu]

# Use tool's structured methods
cpu_info = lscpu.get_cpu_info()
print(cpu_info.model_name)
print(cpu_info.core_count)

# Use Dmesg to check kernel messages
dmesg = node.tools[Dmesg]
messages = dmesg.get_logs()
kernel_errors = [m for m in messages if "error" in m.lower()]
```

### Built-in tools reference

| Tool class | What it wraps | Key methods |
|------------|---------------|-------------|
| `Lscpu` | `lscpu` | `.get_cpu_info()` |
| `Dmesg` | `dmesg` | `.get_logs()` |
| `Uname` | `uname` | `.get_linux_information()` |
| `Iperf3` | `iperf3` | `.run_as_server()`, `.run_as_client()` |
| `Fio` | `fio` | `.launch()`, `.get_result()` |
| `Echo` | `echo` | `.run(text)` |
| `Ntttcp` | `ntttcp` | `.run_as_sender()`, `.run_as_receiver()` |

### Writing a custom tool

```python
from lisa.executable import Tool

class MyTool(Tool):
    @property
    def command(self) -> str:
        return "mytool"

    def _check_exists(self) -> bool:
        result = self._node.execute("which mytool")
        return result.exit_code == 0

    def _install(self) -> bool:
        self._node.execute("apt-get install -y mytool", sudo=True)
        return True

    def run_check(self) -> str:
        return self._node.execute("mytool --check").stdout
```

---

## 7. Using Features — platform capabilities

Features represent capabilities provided by the platform (Azure, HyperV, etc.).
Declare them in `requirement=` and then access via `node.features[FeatureClass]`.

```python
from lisa.features import SerialConsole, StartStop, Resize, Nvme

@TestCaseMetadata(
    description="Verifies VM can be stopped and restarted",
    priority=1,
    requirement=simple_requirement(
        supported_features=[StartStop],   # declare needed features
    ),
)
def verify_start_stop(self, case_name, node, environment, log):
    start_stop = node.features[StartStop]

    # Stop the VM
    start_stop.stop()
    log.info("VM stopped")

    # Start it again
    start_stop.start()
    log.info("VM restarted")

    # Verify it's back
    result = node.execute("uptime")
    assert_that(result.exit_code).is_equal_to(0)
```

### Available features (common)

| Feature | Description |
|---------|-------------|
| `SerialConsole` | Access VM serial console |
| `StartStop` | Stop and restart the VM |
| `Resize` | Resize VM to a different SKU |
| `Nvme` | NVMe disk support |
| `Sriov` | SR-IOV accelerated networking |
| `Gpu` | GPU/CUDA support |
| `Hibernation` | VM hibernation |

---

## 8. Writing assertions

LISA uses a fluent assertion library.

```python
from lisa import assert_that

# Equality
assert_that(result.exit_code).is_equal_to(0)
assert_that(cpu_count).is_equal_to(4)

# Comparisons
assert_that(free_bytes).is_greater_than(1024 * 1024 * 100)  # > 100 MB
assert_that(response_time_ms).is_less_than(100)

# None checks
assert_that(value).is_not_none()
assert_that(value).is_none()

# String operations
assert_that(result.stdout).contains("SUCCESS")
assert_that(result.stdout).does_not_contain("ERROR")
assert_that(result.stdout).starts_with("Linux")

# Boolean
assert_that(process_running).is_true()
assert_that(has_errors).is_false()

# With descriptions (shown in failure messages)
assert_that(cpu_count)\
    .described_as(f"vCPU count on node {node.name}")\
    .is_equal_to(expected_count)

# Lists and collections
assert_that(nvme_devices).is_not_empty()
assert_that(nvme_devices).contains("/dev/nvme0")
assert_that(len(nvme_devices)).is_greater_than_or_equal_to(1)
```

### Raising skip instead of fail

Sometimes a test should be skipped rather than failed when a condition isn't met:

```python
from lisa.util import SkippedException

def verify_nvme_performance(self, case_name, node, environment, log):
    # Check if NVMe devices exist before testing
    result = node.execute("ls /dev/nvme* 2>/dev/null")
    if result.exit_code != 0:
        raise SkippedException("No NVMe devices found — skipping performance test")

    # ... rest of test ...
```

---

## 9. Requirements — controlling when a test runs

Requirements tell LISA which environments are compatible with a test.
Incompatible tests are **skipped** (not failed).

```python
requirement=simple_requirement(
    # Hardware minimums
    min_core_count=4,           # Need at least 4 vCPUs
    min_memory_mb=8192,         # Need at least 8 GB RAM
    min_disk_space_gb=100,      # Need at least 100 GB disk

    # Environment state
    environment_status=EnvironmentStatus.Deployed,  # VM must be running

    # Platform restriction
    supported_platform_type=[AZURE],            # Only Azure
    # supported_platform_type=[AZURE, HYPERV],  # Azure or HyperV

    # OS exclusions
    unsupported_os=[Windows, BSD],              # Skip on Windows/BSD

    # Required capabilities
    supported_features=[SerialConsole, Nvme],   # Must support these
)
```

### Common requirement patterns

```python
# T0 smoke test — any deployed VM
requirement=simple_requirement(
    environment_status=EnvironmentStatus.Deployed
)

# Azure-only, high-core-count
requirement=simple_requirement(
    supported_platform_type=[AZURE],
    min_core_count=16,
    min_memory_mb=32768,
)

# HyperV-specific feature
requirement=simple_requirement(
    supported_platform_type=[HYPERV],
    supported_features=[Hvvp],  # HyperV-specific feature
)

# No special requirements (any environment)
requirement=simple_requirement()
```

---

## 10. Before and after hooks

```python
class MyTestSuite(TestSuite):

    def before_case(self, **kwargs: Any) -> None:
        """
        Runs before EACH test case in this suite.
        If this method raises an exception, the test case is SKIPPED (not failed).
        Use this for setup that every test requires.
        """
        # Example: ensure a package is installed before every test
        node = kwargs.get("node")
        if node:
            node.execute("apt-get install -y curl", sudo=True)

    def after_case(self, **kwargs: Any) -> None:
        """
        Runs after EACH test case, regardless of whether it passed or failed.
        Use this for cleanup.
        """
        node = kwargs.get("node")
        if node:
            node.execute("rm -f /tmp/test_*")
```

---

## 11. Multi-node tests

Some tests need multiple VMs (e.g. sender/receiver for network throughput).

```python
@TestCaseMetadata(
    description="Verifies network throughput between two VMs in the same VNET",
    priority=2,
    requirement=simple_requirement(
        min_count=2,    # Require at least 2 nodes in the environment
    ),
)
def verify_inter_vm_throughput(self, case_name, node, environment, log):
    # node is the first node; get the second one:
    sender = environment.nodes[0]
    receiver = environment.nodes[1]

    receiver_ip = receiver.internal_address

    # Start iperf3 server on receiver
    receiver.execute("iperf3 -s -D")  # -D = daemon mode

    # Run iperf3 client on sender
    result = sender.execute(
        f"iperf3 -c {receiver_ip} -t 30 --json",
        timeout=60,
        expected_exit_code=0
    )

    import json
    data = json.loads(result.stdout)
    throughput_gbps = data["end"]["sum_received"]["bits_per_second"] / 1e9
    log.info(f"Throughput: {throughput_gbps:.2f} Gbps")

    assert_that(throughput_gbps)\
        .described_as("inter-VM network throughput (Gbps)")\
        .is_greater_than(5.0)
```

---

## 12. Generating with the MCP server

Instead of writing boilerplate manually, ask Claude to generate it:

### Example prompt

```
Generate a LISA test suite called "KernelVerification" in the "core" area,
category functional, owned by "kernel-team".

Include these test cases:
1. verify_kernel_version — priority 0 — checks kernel >= 5.15 on Azure
2. verify_no_kernel_errors — priority 1 — checks dmesg for errors at boot
3. verify_kdump_enabled — priority 2 — checks kdump service is active

Use node.execute() and assert_that() in the bodies.
Save to ~/lisa/microsoft/testsuites/core/kernel_verification.py
```

Claude calls `generate_test_suite_code(...)` and writes the file immediately.

---

## 13. Adding to a runbook

After writing your test, include it in a runbook:

```yaml
# In your runbook YAML:
testcase:
  - criteria:
      name: verify_kernel_version    # include by method name
  - criteria:
      area: core                     # include all "core" area tests
```

Or ask Claude:

```
Add "KernelVerification.verify_kernel_version" to my runbook at ~/my_runbook.yml
```

---

## 14. Complete example

A complete, production-ready test suite:

```python
# lisa/microsoft/testsuites/core/kernel_verification.py
"""
KernelVerification — verifies kernel version, dmesg health, and kdump.
"""

from __future__ import annotations

import re
from logging import Logger
from typing import Any

from lisa import (
    Environment,
    Node,
    TestCaseMetadata,
    TestSuite,
    TestSuiteMetadata,
    assert_that,
    simple_requirement,
)
from lisa.environment import EnvironmentStatus
from lisa.util import SkippedException


MIN_KERNEL_MAJOR = 5
MIN_KERNEL_MINOR = 15


@TestSuiteMetadata(
    area="core",
    category="functional",
    description="Verifies kernel version, dmesg health, and kdump service.",
    owner="kernel-team",
)
class KernelVerification(TestSuite):

    @TestCaseMetadata(
        description=(
            f"Verifies kernel version is >= {MIN_KERNEL_MAJOR}.{MIN_KERNEL_MINOR} on Azure."
        ),
        priority=0,
        timeout=120,
        requirement=simple_requirement(
            environment_status=EnvironmentStatus.Deployed,
        ),
    )
    def verify_kernel_version(
        self,
        case_name: str,
        node: Node,
        environment: Environment,
        log: Logger,
    ) -> None:
        result = node.execute("uname -r", expected_exit_code=0)
        version_str = result.stdout.strip()
        log.info(f"Kernel version: {version_str}")

        # Parse major.minor from e.g. "5.15.0-1040-azure"
        match = re.match(r"(\d+)\.(\d+)", version_str)
        assert_that(match).described_as("kernel version format").is_not_none()

        major = int(match.group(1))
        minor = int(match.group(2))

        assert_that(major * 1000 + minor)\
            .described_as(f"kernel {version_str} >= {MIN_KERNEL_MAJOR}.{MIN_KERNEL_MINOR}")\
            .is_greater_than_or_equal_to(MIN_KERNEL_MAJOR * 1000 + MIN_KERNEL_MINOR)

    @TestCaseMetadata(
        description="Verifies no critical errors appear in dmesg at boot.",
        priority=1,
        timeout=300,
        requirement=simple_requirement(),
    )
    def verify_no_kernel_errors(
        self,
        case_name: str,
        node: Node,
        environment: Environment,
        log: Logger,
    ) -> None:
        result = node.execute("dmesg --level=crit,alert,emerg", expected_exit_code=0)
        critical_messages = [
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip()
        ]

        if critical_messages:
            log.warning(f"Critical dmesg messages found:\n" + "\n".join(critical_messages))

        assert_that(critical_messages)\
            .described_as("critical/alert dmesg messages at boot")\
            .is_empty()

    @TestCaseMetadata(
        description="Verifies kdump service is enabled and configured.",
        priority=2,
        timeout=120,
        requirement=simple_requirement(),
    )
    def verify_kdump_enabled(
        self,
        case_name: str,
        node: Node,
        environment: Environment,
        log: Logger,
    ) -> None:
        # Check if kdump is available at all
        result = node.execute("systemctl status kdump 2>/dev/null || echo NOT_FOUND")
        if "NOT_FOUND" in result.stdout or "could not be found" in result.stdout:
            raise SkippedException("kdump service not available on this image")

        result = node.execute("systemctl is-enabled kdump", expected_exit_code=0)
        assert_that(result.stdout.strip())\
            .described_as("kdump service enabled state")\
            .is_in("enabled", "static")

    def before_case(self, **kwargs: Any) -> None:
        pass

    def after_case(self, **kwargs: Any) -> None:
        pass
```
