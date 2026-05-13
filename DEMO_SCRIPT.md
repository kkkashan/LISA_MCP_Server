# LISA MCP Server — Live Demo Script for CVP Presentation

> Presenter-friendly walkthrough: **15 minutes** end-to-end.
> Side-by-side with `presentation.pptx`. Every prompt is copy-paste ready.

---

## 0 · Pre-Flight (do this **before** the meeting)

| ✓ | Item |
|---|---|
| ☐ | Repo cloned at `~/lisa-mcp-server` (or `/mnt/c/Users/kkashanjat/lisa-mcp-server`) |
| ☐ | `./demo.sh` ran cleanly once (artifacts in `/tmp/lisa-demo/`) |
| ☐ | LISA cloned at `~/lisa` (`git clone https://github.com/microsoft/lisa.git ~/lisa`) — needed for tools that scan a real LISA repo |
| ☐ | VS Code open in the `lisa-mcp-server` workspace |
| ☐ | GitHub Copilot Chat panel open in **Agent mode** (so it can invoke MCP tools) |
| ☐ | MCP server started: `Ctrl+Shift+P` → **MCP: Start Server** → **lisa** (or click ▶ in `.vscode/mcp.json`) |
| ☐ | Confirm green dot next to `lisa` in the MCP panel (18 tools enabled) |
| ☐ | Terminal pane open at the repo root for the safety-net CLI demo |
| ☐ | `presentation.pptx` open in PowerPoint on second screen |
| ☐ | Browser tab open to **github.com/kkkashan/LISA_MCP_Server** (closing slide reference) |
| ☐ | Wifi / VPN verified; Azure OpenAI key ready *if* showing optional LLM analysis |

> **Plan B (no network / MCP misbehaves):** Skip Acts 2–4 and run the CLI demo (`./demo.sh`) — same outcome, in 30 seconds.

---

## Demo arc (≈ 15 min)

| Act | Time | What happens | Slide |
|----|------|--------------|-------|
| **1. The hook** | 1 min | Pose the pain in one sentence | Slide 2 |
| **2. Discovery** | 2 min | AI lists tests in natural language | Slides 3–5 |
| **3. Generation** | 4 min | AI writes a runbook + a new test suite | Slide 5 |
| **4. Triage** | 4 min | AI explains a failure and recommends a fix | Slide 11 |
| **5. The point** | 2 min | Tie demo to impact + CTA | Slides 7, 8, 14 |
| **6. Q&A bridge** | 2 min | "Plug any AI into any capability" | Slide 15 |

---

## ACT 1 · The Hook (1 min) — Slide 2

> **Say:**
> "Today, validating a single Linux kernel update across all of Azure's supported distros takes a senior engineer **days** of grep, YAML hand-crafting, and log triage.
> What if any engineer could do it by **typing one sentence?** Watch."

(Click to Slide 3 — Solution.)

---

## ACT 2 · Discovery (2 min) — Slide 5

### Prompt 2.1 — Prove the AI knows what's in the LISA repo

Copy into Copilot Chat:

```
Using the lisa MCP server, list every functional test area in the LISA
repo at ~/lisa.
```

> **Say while it runs:**
> "Copilot just decided on its own to call `list_test_areas`. Notice — I didn't tell it the tool name, I told it the goal."

> **Talking point:** point at the returned areas (`network`, `storage`, `cpu`, …) — "500+ tests, hundreds of files, indexed in seconds via AST."

### Prompt 2.2 — Filtered, tier-aware discovery

```
Show me all priority-0 storage tests in ~/lisa that support Azure.
Give me 5 of them with a one-line description.
```

> **Talking point:** "That's the `discover_test_cases` tool with `area=storage`, `tier=T0`, `platform=azure` — all inferred from English."

---

## ACT 3 · Generation (4 min) — Slide 5

### Prompt 3.1 — Build a real Azure runbook

```
Build a T1 Azure runbook for Ubuntu 22.04 LTS and save it to
/tmp/cvp-demo/azure_t1.yml. Then validate it and tell me if it's ready
to execute.
```

> **What to highlight on screen:**
> - The generated YAML is **production-shaped** (variables, platform block, criteria).
> - The validator returns `valid: True` with platform and criteria summary.
> - "This used to be 30 minutes of YAML and three Stack Overflow tabs."

### Prompt 3.2 — Author a *brand-new* test suite from English

```
Generate a LISA test suite called "NvmeThroughput" in the "storage"
area, category "performance". It should run fio sequential read for
60 seconds and fail if throughput is below 1024 MB/s. Priority 1,
Azure only, owner cvp-demo@microsoft.com. Save it to
/tmp/cvp-demo/nvme_throughput.py.
```

> **Show in editor:**
> - Open the generated file. Scroll through the `@TestSuiteMetadata` /
>   `@TestCaseMetadata` decorators and the typed `Environment` / `Node`
>   parameters — "this is LISA-idiomatic Python, not a sketch."

> **Talking point:** "An engineer just authored a real, runnable test in **15 seconds** — without knowing the LISA SDK."

### Prompt 3.3 — Wire it into the runbook

```
Add the NvmeThroughput.verify_nvme_throughput test as an include
criterion to /tmp/cvp-demo/azure_t1.yml, then re-validate.
```

> **Point at:** the updated `criteria` block in the YAML. "The agent is now editing **its own previous artifact** — that's composition."

---

## ACT 4 · Triage (4 min) — Slide 11

### Prompt 4.1 — Parse a failed run

(Use the pre-staged failing run artifact — keep this XML ready in the repo:)

```
Parse the JUnit results at /tmp/lisa-demo/fake_results.xml and give me
a pass/fail breakdown.
```

> **Talking point:** "30 seconds ago that was an opaque XML file. Now we have totals, durations, and which test failed."

### Prompt 4.2 — Root-cause the failure with the LLM

**[Optional — requires Azure OpenAI key]**

```
Analyze the failure of NetworkSuite.verify_mtu in
/tmp/lisa-demo/fake_results.xml. The failure message is
"Expected MTU 1500, got 1450". Use my Azure OpenAI key
<PASTE-KEY-HERE>. Give me severity, root cause category,
and a one-line recommended fix.
```

> **What to highlight in the response:**
> - **Category** (network config / kernel / hypervisor)
> - **Severity** (critical / high / medium / low)
> - **Recommended fix** — specific path / setting / command

> **Talking point:** "Two hours of log archaeology — compressed to 30 seconds. And the AI is **not** guessing in a vacuum: it has the structured test metadata, the JUnit context, and the log slice all at once."

### Prompt 4.3 — Stakeholder-ready report

```
Generate a full HTML and Markdown analysis report from
/tmp/lisa-demo/fake_results.xml using my Azure OpenAI key, and save
it to /tmp/cvp-demo/report/. Then open the HTML.
```

> **Show:** the resulting HTML report side-by-side. **Close with:**
> "This is the artifact you forward to a stakeholder. The engineer never wrote it; the AI did."

---

## ACT 5 · The Point (2 min) — Slides 7, 8, 14

> **Say (pointing at Slide 7 — Impact Inside Microsoft):**
> "What you just saw maps to three concrete numbers:
> - Discovery: 10 min → 10 sec (**100×**)
> - Runbook authoring: 30 min → one sentence
> - Failure triage: 2 hrs → 30 sec
>
> Multiply that by every Linux validation engineer at Microsoft and you have a measurable productivity dividend."

(Click to Slide 8 — Outside Microsoft.)

> **Say:** "LISA is already open source. With this server, **partners** — Canonical, Red Hat, SUSE — can self-serve Azure compatibility certification. We turn a cost center into an ecosystem."

(Click to Slide 14 — Call to Action.)

> **Ask for the close:**
> "I'd like to pilot this with one Linux validation team this sprint, with a target of **80% reduction in triage time**. Two engineering hours and an Azure OpenAI deployment is all I need to start."

---

## ACT 6 · Q&A Bridge (2 min) — Slide 15

Likely questions and pre-canned answers:

| Question | Answer |
|---|---|
| **"Why MCP and not a REST API?"** | "MCP is the emerging standard — one server works with Copilot, Claude, VS Code, and whatever AI ships next. No N×M rewrite." |
| **"What if Azure OpenAI is down?"** | "Discovery, generation, and execution don't need an LLM. Only the failure-analysis tools do, and they support OpenAI, Ollama, LM Studio, or Foundry as drop-in replacements." |
| **"Can it run in CI?"** | "Yes — `run_and_analyze` is a single tool call. You can wrap it in a GitHub Action or ADO pipeline today." |
| **"What about security / secrets?"** | "MCP runs locally next to the IDE. The API key for analysis is passed per-call and never persisted by the server." |
| **"Could this work for Windows / .NET / Azure SDKs?"** | "Yes — the architecture is generic. This server is the reference implementation; the same pattern applies to any test framework." |
| **"How much code is this?"** | "~3,000 lines of Python, MIT-licensed, on GitHub. Not a science project — a shipping tool." |

---

## Fail-Safe — 30-Second CLI Demo

If Copilot Chat misbehaves or VS Code's MCP integration hangs, switch to terminal:

```bash
cd ~/lisa-mcp-server
./demo.sh
```

Then narrate over the output:
> "Even without an AI client, the server runs as a regular Python package. You see 18 tools register, a runbook built and validated, a brand-new test suite generated, and JUnit results parsed — same capability, same artifacts."

Show the produced files:

```bash
ls /tmp/lisa-demo/
cat /tmp/lisa-demo/azure_t1_demo.yml
```

---

## After the Demo — Leave-Behind Bundle

Email / Teams these to attendees:

| File | Purpose |
|---|---|
| `presentation.pptx` | Editable deck |
| `presentation.pdf` | Read-only / projector |
| `demo.sh` | Reproduce the demo on any laptop |
| `/tmp/lisa-demo/azure_t1_demo.yml` | Sample generated runbook |
| `/tmp/lisa-demo/demo_nvme_throughput.py` | Sample generated test suite |
| Link: `github.com/kkkashan/LISA_MCP_Server` | Source + docs |

---

## Quick Reference — Prompts in One Block (copy/paste during demo)

```
Using the lisa MCP server, list every functional test area in the LISA repo at ~/lisa.

Show me all priority-0 storage tests in ~/lisa that support Azure. Give me 5 of them with a one-line description.

Build a T1 Azure runbook for Ubuntu 22.04 LTS and save it to /tmp/cvp-demo/azure_t1.yml. Then validate it and tell me if it's ready to execute.

Generate a LISA test suite called "NvmeThroughput" in the "storage" area, category "performance". It should run fio sequential read for 60 seconds and fail if throughput is below 1024 MB/s. Priority 1, Azure only, owner cvp-demo@microsoft.com. Save it to /tmp/cvp-demo/nvme_throughput.py.

Add the NvmeThroughput.verify_nvme_throughput test as an include criterion to /tmp/cvp-demo/azure_t1.yml, then re-validate.

Parse the JUnit results at /tmp/lisa-demo/fake_results.xml and give me a pass/fail breakdown.

Analyze the failure of NetworkSuite.verify_mtu in /tmp/lisa-demo/fake_results.xml. The failure message is "Expected MTU 1500, got 1450". Use my Azure OpenAI key <PASTE-KEY-HERE>. Give me severity, root cause category, and a one-line recommended fix.

Generate a full HTML and Markdown analysis report from /tmp/lisa-demo/fake_results.xml using my Azure OpenAI key, and save it to /tmp/cvp-demo/report/. Then open the HTML.
```
