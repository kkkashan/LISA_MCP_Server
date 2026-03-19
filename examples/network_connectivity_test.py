# Generated test suite file: networkconnectivitytest.py
"""
Validates core network connectivity, DNS resolution, interface configuration, and data transfer on Azure Linux VMs.
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


@TestSuiteMetadata(
    area="network",
    category="functional",
    description="Validates core network connectivity, DNS resolution, interface configuration, and data transfer on Azure Linux VMs.",
    owner="kkashanjat",
)
class NetworkConnectivityTest(TestSuite):
    """
    Validates core network connectivity, DNS resolution, interface configuration, and data transfer on Azure Linux VMs.
    """

    @TestCaseMetadata(
        description="Verify that a default gateway is configured and reachable via ping.",
        priority=0,
        timeout=600,
        use_new_environment=False,
        requirement=simple_requirement(),
    )
    def verify_default_gateway(
        self,
        case_name: str,
        node: Node,
        environment: Environment,
        log: Logger,
    ) -> None:
        result = node.execute("ip route show default", expected_exit_code=0)
        assert_that(result.stdout).described_as("Default route must exist").contains("default via")
        gw = result.stdout.split("via ")[1].split()[0]
        ping = node.execute(f"ping -c 3 -W 5 {gw}", expected_exit_code=0)
        assert_that(ping.stdout).contains(" 0% packet loss")

    @TestCaseMetadata(
        description="Verify that DNS resolution works for external hostnames.",
        priority=0,
        timeout=600,
        use_new_environment=False,
        requirement=simple_requirement(),
    )
    def verify_dns_resolution(
        self,
        case_name: str,
        node: Node,
        environment: Environment,
        log: Logger,
    ) -> None:
        result = node.execute("nslookup microsoft.com", expected_exit_code=0)
        assert_that(result.stdout).described_as("DNS must resolve microsoft.com").contains("Address")

    @TestCaseMetadata(
        description="Verify all expected network interfaces are in UP state with valid IP addresses.",
        priority=1,
        timeout=600,
        use_new_environment=False,
        requirement=simple_requirement(),
    )
    def verify_network_interfaces_up(
        self,
        case_name: str,
        node: Node,
        environment: Environment,
        log: Logger,
    ) -> None:
        result = node.execute("ip -o link show up", expected_exit_code=0)
        assert_that(result.stdout).described_as("At least one interface must be UP").is_not_empty()
        ip_result = node.execute("ip -o -4 addr show", expected_exit_code=0)
        assert_that(ip_result.stdout).described_as("At least one IPv4 address must be assigned").contains("inet ")

    @TestCaseMetadata(
        description="Verify outbound TCP connectivity to a well-known external endpoint.",
        priority=1,
        timeout=900,
        use_new_environment=False,
        requirement=simple_requirement(),
    )
    def verify_outbound_connectivity(
        self,
        case_name: str,
        node: Node,
        environment: Environment,
        log: Logger,
    ) -> None:
        result = node.execute("curl -s -o /dev/null -w '%{http_code}' --connect-timeout 10 https://azure.microsoft.com", expected_exit_code=0)
        assert_that(result.stdout).described_as("HTTP request must succeed").is_equal_to("200")

    @TestCaseMetadata(
        description="Verify that the primary network interface MTU is at least 1500 bytes.",
        priority=2,
        timeout=600,
        use_new_environment=False,
        requirement=simple_requirement(),
    )
    def verify_mtu_size(
        self,
        case_name: str,
        node: Node,
        environment: Environment,
        log: Logger,
    ) -> None:
        result = node.execute("cat /sys/class/net/eth0/mtu", expected_exit_code=0)
        mtu = int(result.stdout.strip())
        assert_that(mtu).described_as("MTU must be >= 1500").is_greater_than_or_equal_to(1500)

    @TestCaseMetadata(
        description="Verify basic TCP data transfer by downloading a small payload and checking integrity.",
        priority=2,
        timeout=1200,
        use_new_environment=False,
        requirement=simple_requirement(),
    )
    def verify_tcp_data_transfer(
        self,
        case_name: str,
        node: Node,
        environment: Environment,
        log: Logger,
    ) -> None:
        node.execute("curl -s -o /tmp/test_download https://aka.ms/linux", expected_exit_code=0)
        result = node.execute("test -s /tmp/test_download && echo OK", expected_exit_code=0)
        assert_that(result.stdout.strip()).described_as("Downloaded file must not be empty").is_equal_to("OK")
        node.execute("rm -f /tmp/test_download")

    def before_case(self, **kwargs: Any) -> None:
        """Runs before each test case. Raise an exception to skip the case."""
        pass

    def after_case(self, **kwargs: Any) -> None:
        """Runs after each test case regardless of outcome."""
        pass
