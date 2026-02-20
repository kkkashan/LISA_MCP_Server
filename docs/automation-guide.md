# Automation and CI/CD Guide

Integrate LISA tests into GitHub Actions, Azure DevOps, or any CI/CD system using
the LISA MCP server's Python API or the `lisa` CLI directly.

---

## Table of Contents

1. [Architecture — CI/CD with LISA](#1-architecture--cicd-with-lisa)
2. [GitHub Actions](#2-github-actions)
3. [Azure DevOps Pipelines](#3-azure-devops-pipelines)
4. [Python script automation](#4-python-script-automation)
5. [Multi-distro grid testing in CI](#5-multi-distro-grid-testing-in-ci)
6. [Storing and archiving results](#6-storing-and-archiving-results)
7. [Failure handling and retry logic](#7-failure-handling-and-retry-logic)
8. [Security — managing credentials](#8-security--managing-credentials)

---

## 1. Architecture — CI/CD with LISA

```
CI Trigger (PR, schedule, image build)
     │
     ▼
Generate Runbook (lisa-mcp Python API or pre-committed YAML)
     │
     ▼
lisa -r runbook.yml -v subscription_id:$SECRET ...
     │                        │
     ▼                        ▼
Deploy Azure VMs       (or use existing ready platform)
     │
     ▼
Run test cases in parallel
     │
     ├── results.xml  (JUnit — for CI pass/fail gate)
     ├── results.html (human report)
     └── Console logs
     │
     ▼
Parse & evaluate results
     │
     ├── PASS (all P0 pass) → merge / publish image
     └── FAIL → block merge, notify team, preserve VMs for debug
```

---

## 2. GitHub Actions

### Full workflow — T0 gate on PR

```yaml
# .github/workflows/lisa_t0_gate.yml
name: LISA T0 Gate

on:
  pull_request:
    branches: [main]

permissions:
  id-token: write    # for Azure OIDC login
  contents: read

jobs:
  lisa-t0:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      # ── Setup ──────────────────────────────────────────────────────────
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install LISA and MCP server
        run: |
          pip install -e ./lisa                     # if lisa is a submodule
          # OR: pip install lisa                    # from PyPI when available
          pip install -e ./lisa-mcp-server

      # ── Azure login (OIDC — no stored secrets) ────────────────────────
      - name: Azure login
        uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

      # ── SSH key for VM access ─────────────────────────────────────────
      - name: Set up SSH key
        run: |
          echo "${{ secrets.LISA_SSH_PRIVATE_KEY }}" > /tmp/lisa_key
          chmod 600 /tmp/lisa_key

      # ── Generate runbook ──────────────────────────────────────────────
      - name: Generate T0 runbook
        run: |
          python3 -c "
          from lisa_mcp.tools.test_generator import generate_runbook_yaml
          yaml = generate_runbook_yaml(
              name='PR T0 Gate',
              platform_type='azure',
              tier='T0',
              image='ubuntu focal 20.04-lts latest',
              location='westus3',
              notifiers=['junit'],
          )
          open('ci_t0_runbook.yml', 'w').write(yaml)
          print('Runbook generated')
          "

      # ── Run tests ─────────────────────────────────────────────────────
      - name: Run LISA T0 tests
        run: |
          lisa -r ci_t0_runbook.yml \
               -v subscription_id=${{ secrets.AZURE_SUBSCRIPTION_ID }} \
               -v admin_private_key_file=/tmp/lisa_key
        env:
          AZURE_SUBSCRIPTION_ID: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

      # ── Evaluate results ──────────────────────────────────────────────
      - name: Evaluate test results
        run: |
          python3 -c "
          import sys
          from lisa_mcp.tools.result_parser import parse_junit_xml, summarize
          s = parse_junit_xml('./lisa_results.xml')
          print(summarize(s))
          # Fail the CI step if any test failed
          if s.failed > 0 or s.errors > 0:
              print(f'GATE FAILED: {s.failed} failures, {s.errors} errors')
              sys.exit(1)
          print('GATE PASSED')
          "

      # ── Archive results ───────────────────────────────────────────────
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: lisa-results-${{ github.run_id }}
          path: |
            lisa_results.xml
            lisa_report.html
            ./logs/

      # ── Publish JUnit results in GitHub UI ───────────────────────────
      - name: Publish test report
        if: always()
        uses: mikepenz/action-junit-report@v4
        with:
          report_paths: "lisa_results.xml"
          check_name: "LISA T0 Test Results"
```

### Nightly T1 run

```yaml
# .github/workflows/lisa_t1_nightly.yml
name: LISA T1 Nightly

on:
  schedule:
    - cron: "0 2 * * *"   # 2 AM UTC daily
  workflow_dispatch:        # allow manual trigger

jobs:
  lisa-t1:
    runs-on: ubuntu-latest
    timeout-minutes: 180   # 3 hours

    strategy:
      matrix:
        image:
          - "ubuntu focal 20.04-lts latest"
          - "ubuntu jammy 22.04-lts latest"
          - "redhat rhel 8_5 latest"
      fail-fast: false      # test all images even if one fails

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install
        run: pip install lisa lisa-mcp-server

      - name: Azure login
        uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

      - name: Generate T1 runbook
        run: |
          python3 -c "
          from lisa_mcp.tools.test_generator import generate_runbook_yaml
          yaml = generate_runbook_yaml(
              name='T1 Nightly - ${{ matrix.image }}',
              platform_type='azure',
              tier='T1',
              image='${{ matrix.image }}',
              notifiers=['html', 'junit'],
          )
          open('t1_runbook.yml', 'w').write(yaml)
          "

      - name: Run T1
        run: |
          echo "${{ secrets.LISA_SSH_PRIVATE_KEY }}" > /tmp/lisa_key
          chmod 600 /tmp/lisa_key
          lisa -r t1_runbook.yml \
               -v subscription_id=${{ secrets.AZURE_SUBSCRIPTION_ID }} \
               -v admin_private_key_file=/tmp/lisa_key

      - name: Upload results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: t1-results-${{ matrix.image }}-${{ github.run_id }}
          path: "*.xml *.html logs/"
```

---

## 3. Azure DevOps Pipelines

### T0 gate pipeline

```yaml
# azure-pipelines.yml
trigger:
  - main

pool:
  vmImage: ubuntu-latest

variables:
  SUBSCRIPTION_ID: $(AzureSubscriptionId)   # from ADO variable group

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: "3.12"

  - script: |
      pip install lisa lisa-mcp-server
    displayName: Install dependencies

  - task: AzureCLI@2
    displayName: Run LISA T0 tests
    inputs:
      azureSubscription: "MyAzureServiceConnection"
      scriptType: bash
      scriptLocation: inlineScript
      inlineScript: |
        # Write SSH key
        echo "$(LisaSshPrivateKey)" > /tmp/lisa_key
        chmod 600 /tmp/lisa_key

        # Generate runbook
        python3 -c "
        from lisa_mcp.tools.test_generator import generate_runbook_yaml
        yaml = generate_runbook_yaml(
            name='ADO T0 Gate',
            platform_type='azure',
            tier='T0',
            notifiers=['junit'],
        )
        open('t0_runbook.yml', 'w').write(yaml)
        "

        # Run
        lisa -r t0_runbook.yml \
             -v subscription_id=$(SUBSCRIPTION_ID) \
             -v admin_private_key_file=/tmp/lisa_key

  - task: PublishTestResults@2
    displayName: Publish test results
    condition: always()
    inputs:
      testResultsFormat: JUnit
      testResultsFiles: "lisa_results.xml"
      testRunTitle: "LISA T0 Results"

  - task: PublishPipelineArtifact@1
    condition: always()
    inputs:
      targetPath: "lisa_results.xml"
      artifact: "lisa-results"
```

---

## 4. Python script automation

For maximum control, use the MCP server's Python modules directly in scripts.

### Build and run a test from Python

```python
#!/usr/bin/env python3
"""
Automated LISA test runner script.
Usage: python3 run_tests.py --tier T1 --image "ubuntu focal 20.04-lts latest"
"""

import argparse
import sys
from pathlib import Path

from lisa_mcp.tools.test_generator import generate_runbook_yaml
from lisa_mcp.tools.runbook_builder import write_runbook, validate_runbook
from lisa_mcp.tools.test_runner import run_tests, check_lisa_installed
from lisa_mcp.tools.result_parser import parse_junit_xml, summarize


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", default="T1", choices=["T0", "T1", "T2", "T3", "T4"])
    parser.add_argument("--image", default="ubuntu focal 20.04-lts latest")
    parser.add_argument("--location", default="westus3")
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--ssh-key", required=True)
    parser.add_argument("--lisa-path", default=str(Path.home() / "lisa"))
    parser.add_argument("--output-dir", default="./test-results")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Check LISA is installed
    info = check_lisa_installed()
    if not info["installed"]:
        print("ERROR: LISA is not installed. Run: pip install -e ~/lisa", file=sys.stderr)
        sys.exit(1)
    print(f"LISA found: {info['path']}")

    # 2. Generate runbook
    print(f"Generating {args.tier} runbook for {args.image}...")
    yaml_str = generate_runbook_yaml(
        name=f"{args.tier} Run — {args.image}",
        platform_type="azure",
        tier=args.tier,
        image=args.image,
        location=args.location,
        notifiers=["html", "junit"],
    )
    runbook_path = str(output_dir / "runbook.yml")
    write_runbook(yaml_str, runbook_path)
    print(f"Runbook written: {runbook_path}")

    # 3. Validate runbook
    validation = validate_runbook(runbook_path)
    if not validation["valid"]:
        print("ERROR: Runbook validation failed:")
        for err in validation["errors"]:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)
    for warn in validation["warnings"]:
        print(f"WARNING: {warn}")

    # 4. Run tests
    print(f"Running {args.tier} tests (this may take a while)...")
    result = run_tests(
        lisa_path=args.lisa_path,
        runbook_path=runbook_path,
        variables={
            "subscription_id": args.subscription_id,
            "admin_private_key_file": args.ssh_key,
        },
        working_dir=str(output_dir),
    )

    print(f"Exit code: {result['returncode']}")
    if result.get("stderr"):
        print(f"Stderr: {result['stderr'][:500]}")

    # 5. Parse and print results
    junit_path = str(output_dir / "lisa_results.xml")
    try:
        summary = parse_junit_xml(junit_path)
        print("\nResults:")
        print(f"  {summarize(summary)}")

        if summary.failed > 0:
            print("\nFailed tests:")
            for r in summary.results:
                if r.status == "failed":
                    print(f"  FAIL: {r.name} — {r.message}")

        # Exit with error if failures
        sys.exit(1 if summary.failed > 0 else 0)

    except FileNotFoundError:
        print("No JUnit results file found — check LISA output above")
        sys.exit(1 if not result["success"] else 0)


if __name__ == "__main__":
    main()
```

Usage:
```bash
python3 run_tests.py \
    --tier T1 \
    --image "ubuntu focal 20.04-lts latest" \
    --subscription-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
    --ssh-key ~/.ssh/lisa_id_rsa \
    --output-dir ./ci-results
```

---

## 5. Multi-distro grid testing in CI

```python
#!/usr/bin/env python3
"""
Run T1 tests across multiple Linux distributions and collect all results.
"""

import concurrent.futures
import json
import sys
from pathlib import Path

from lisa_mcp.tools.test_generator import generate_runbook_yaml
from lisa_mcp.tools.runbook_builder import write_runbook
from lisa_mcp.tools.test_runner import run_tests
from lisa_mcp.tools.result_parser import parse_junit_xml, summarize


IMAGES = [
    ("ubuntu-2004", "ubuntu focal 20.04-lts latest"),
    ("ubuntu-2204", "ubuntu jammy 22.04-lts latest"),
    ("rhel-85",     "redhat rhel 8_5 8.5.2022012415"),
    ("debian-11",   "debian debian-11 11 latest"),
]

SUBSCRIPTION_ID = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
SSH_KEY_PATH    = "~/.ssh/lisa_id_rsa"
LISA_PATH       = str(Path.home() / "lisa")


def run_for_image(image_id: str, image_name: str) -> dict:
    """Run T1 tests for one image; return summary dict."""
    out_dir = Path(f"./grid-results/{image_id}")
    out_dir.mkdir(parents=True, exist_ok=True)

    yaml_str = generate_runbook_yaml(
        name=f"T1 Grid — {image_id}",
        platform_type="azure",
        tier="T1",
        image=image_name,
        notifiers=["junit"],
    )
    runbook_path = str(out_dir / "runbook.yml")
    write_runbook(yaml_str, runbook_path)

    result = run_tests(
        lisa_path=LISA_PATH,
        runbook_path=runbook_path,
        variables={
            "subscription_id": SUBSCRIPTION_ID,
            "admin_private_key_file": SSH_KEY_PATH,
        },
        working_dir=str(out_dir),
    )

    try:
        s = parse_junit_xml(str(out_dir / "lisa_results.xml"))
        return {"image": image_id, "summary": summarize(s), "failed": s.failed, "passed": s.passed}
    except FileNotFoundError:
        return {"image": image_id, "summary": "No results", "failed": -1, "passed": 0}


def main():
    print(f"Running T1 grid test across {len(IMAGES)} images...")

    # Run all images in parallel (up to 4 at a time)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(run_for_image, img_id, img_name): img_id
            for img_id, img_name in IMAGES
        }
        results = []
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            results.append(res)
            print(f"  [{res['image']}] {res['summary']}")

    total_failed = sum(r["failed"] for r in results if r["failed"] >= 0)
    print(f"\nGrid complete. Total failures: {total_failed}")
    sys.exit(1 if total_failed > 0 else 0)


if __name__ == "__main__":
    main()
```

---

## 6. Storing and archiving results

### Save results to Azure Blob Storage

```python
from azure.storage.blob import BlobServiceClient

def upload_results(results_path: str, container: str, blob_name: str, connection_string: str):
    client = BlobServiceClient.from_connection_string(connection_string)
    blob = client.get_blob_client(container=container, blob=blob_name)
    with open(results_path, "rb") as f:
        blob.upload_blob(f, overwrite=True)
    print(f"Uploaded {results_path} → {container}/{blob_name}")
```

### GitHub Actions artifact retention

```yaml
- uses: actions/upload-artifact@v4
  if: always()
  with:
    name: lisa-results-${{ github.sha }}-${{ matrix.image }}
    path: "*.xml *.html"
    retention-days: 30
```

---

## 7. Failure handling and retry logic

### Retry on infrastructure failure

```python
import time

def run_with_retry(lisa_path, runbook_path, variables, max_retries=3):
    for attempt in range(1, max_retries + 1):
        result = run_tests(lisa_path, runbook_path, variables)
        if result["success"]:
            return result
        # Distinguish infrastructure failure from test failure
        if "VM deployment failed" in result.get("stderr", ""):
            print(f"Infrastructure failure (attempt {attempt}/{max_retries}), retrying...")
            time.sleep(30 * attempt)  # back-off
        else:
            # Test failure (not infra) — don't retry
            return result
    return result
```

### Keep VMs on failure for debugging

Add to your runbook:
```yaml
# In your runbook YAML — preserve environments on failure
environment:
  keep_on_failure: true
```

Then list preserved VMs via Azure portal or CLI after a failed run.

---

## 8. Security — managing credentials

### Never hardcode credentials in runbooks

```yaml
# BAD — don't do this
variable:
  - name: subscription_id
    value: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx  # hardcoded!

# GOOD — use substitution
variable:
  - name: subscription_id
    value: $(subscription_id)   # pass via -v or secrets file
```

### Use Azure Managed Identity in CI

For GitHub Actions with OIDC (no stored secrets):
```yaml
- uses: azure/login@v2
  with:
    client-id: ${{ secrets.AZURE_CLIENT_ID }}
    tenant-id: ${{ secrets.AZURE_TENANT_ID }}
    subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
```

### Rotate SSH keys between runs

```bash
# Generate a temporary key for each CI run
ssh-keygen -t ed25519 -f /tmp/lisa_ci_key -N "" -q
export LISA_SSH_KEY=/tmp/lisa_ci_key
# key is ephemeral — cleaned up by the runner after the job
```

### Add secrets.yml to .gitignore

```bash
echo "secrets.yml" >> .gitignore
echo "*.pem" >> .gitignore
echo "*.key" >> .gitignore
```
