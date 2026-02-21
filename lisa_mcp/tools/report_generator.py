"""
Report generator — produce self-contained HTML and Markdown analysis reports.

The HTML report has:
  - Zero external dependencies (no CDN, no JavaScript frameworks)
  - Inline CSS only
  - Full HTML escaping on all user data
  - Failure cards sorted by severity (critical first)
  - Readable offline and in air-gapped CI environments
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path

from lisa_mcp.models import (
    AnalysisReport,
    FailureAnalysis,
    FailureSeverity,
    RunAnalysisSummary,
    _SEVERITY_ORDER,
)

# ---------------------------------------------------------------------------
# Inline CSS — embedded into every HTML report
# ---------------------------------------------------------------------------

_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
     background:#f0f2f5;color:#1a1a2e;line-height:1.65;padding:2rem}
.wrap{max-width:1140px;margin:0 auto}
/* Header */
.hdr{background:linear-gradient(135deg,#0078d4 0%,#005a9e 100%);
     color:#fff;padding:2rem 2.5rem;border-radius:12px;margin-bottom:2rem;
     box-shadow:0 4px 20px rgba(0,120,212,.3)}
.hdr h1{font-size:1.9rem;font-weight:700;margin-bottom:.4rem}
.hdr .meta{opacity:.75;font-size:.85rem}
/* Health badge */
.health{display:inline-block;padding:.3rem .9rem;border-radius:20px;
        font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;margin-top:.75rem}
.health-healthy{background:#107c10;color:#fff}
.health-degraded{background:#ff8c00;color:#fff}
.health-critical{background:#d13438;color:#fff}
.health-unknown{background:#797775;color:#fff}
/* Metrics grid */
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));
         gap:1rem;margin-bottom:2rem}
.mc{background:#fff;border-radius:10px;padding:1.2rem 1rem;text-align:center;
    box-shadow:0 2px 8px rgba(0,0,0,.07)}
.mc .val{font-size:2.4rem;font-weight:800;line-height:1}
.mc .lbl{font-size:.72rem;color:#666;text-transform:uppercase;letter-spacing:.06em;margin-top:.3rem}
.pass-val{color:#107c10}.fail-val{color:#d13438}.skip-val{color:#797775}
.total-val{color:#0078d4}.dur-val{color:#5c2d91}
/* Sections */
.section{background:#fff;border-radius:10px;padding:1.5rem 2rem;
         margin-bottom:1.5rem;box-shadow:0 2px 8px rgba(0,0,0,.07)}
.section h2{font-size:1.2rem;font-weight:700;margin-bottom:1rem;
            padding-bottom:.5rem;border-bottom:2px solid #e8ecf0}
/* Executive summary */
.exec-summary{font-size:1rem;line-height:1.8;color:#333;
              border-left:4px solid #0078d4;padding-left:1.2rem}
/* Failure cards */
.fail-card{border-radius:8px;margin-bottom:1.2rem;overflow:hidden;
           box-shadow:0 2px 6px rgba(0,0,0,.08)}
.fail-card-hdr{padding:.85rem 1.2rem;display:flex;justify-content:space-between;
               align-items:center;flex-wrap:wrap;gap:.5rem}
.fail-card-body{padding:1rem 1.5rem}
.fc-critical{border-left:5px solid #d13438}.fc-high{border-left:5px solid #ff8c00}
.fc-medium{border-left:5px solid #ffd700}.fc-low{border-left:5px solid #0078d4}
.fc-critical .fail-card-hdr{background:#fff0f0}
.fc-high .fail-card-hdr{background:#fff8f0}
.fc-medium .fail-card-hdr{background:#fffef0}
.fc-low .fail-card-hdr{background:#f0f6ff}
.test-name{font-family:monospace;font-size:.9rem;font-weight:600;color:#1a1a2e}
.badges{display:flex;gap:.4rem;flex-wrap:wrap}
/* Badges */
.badge{display:inline-block;padding:.18rem .55rem;border-radius:4px;
       font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em}
.b-critical{background:#d13438;color:#fff}.b-high{background:#ff8c00;color:#fff}
.b-medium{background:#ffd700;color:#333}.b-low{background:#0078d4;color:#fff}
.b-cat{background:#e0e0e0;color:#444}.b-conf{background:#f0f0f0;color:#666}
/* Detail items */
.detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:.75rem}
@media(max-width:600px){.detail-grid{grid-template-columns:1fr}}
.detail-item label{font-size:.75rem;font-weight:700;text-transform:uppercase;
                   color:#666;letter-spacing:.05em;display:block;margin-bottom:.25rem}
.detail-item p{font-size:.92rem;color:#333}
/* Log lines */
.log-block{background:#1e1e1e;color:#d4d4d4;font-family:'Cascadia Code',Consolas,
           'Courier New',monospace;font-size:.78rem;padding:1rem;border-radius:6px;
           overflow-x:auto;white-space:pre;margin-top:.85rem;
           max-height:220px;overflow-y:auto;line-height:1.5}
/* Lists */
.item-list{list-style:none}
.item-list li{padding:.55rem 1rem;margin-bottom:.4rem;border-radius:6px;
              border-left:3px solid #0078d4;background:#f8faff;font-size:.9rem}
.pattern-tag{display:inline-block;background:#e8f0fe;color:#1a73e8;
             padding:.2rem .7rem;border-radius:12px;font-size:.78rem;
             margin:.2rem;font-weight:500}
.priority-item{counter-increment:priorities}
.priority-item::before{content:counter(priorities)". ";font-weight:700;color:#0078d4}
ol.priority-list{list-style:none;counter-reset:priorities}
/* Progress bar */
.progress-bar{height:8px;border-radius:4px;background:#e0e0e0;margin-top:.5rem;overflow:hidden}
.progress-fill{height:100%;border-radius:4px;transition:width .3s}
.pf-pass{background:#107c10}.pf-fail{background:#d13438}
/* Footer */
footer{margin-top:3rem;font-size:.75rem;color:#aaa;text-align:center;padding:.5rem}
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_analysis_report(
    summary:          RunAnalysisSummary,
    failure_analyses: list[FailureAnalysis],
    total:            int,
    passed:           int,
    failed:           int,
    skipped:          int,
    errors:           int = 0,
    duration_seconds: float = 0.0,
    run_dir:          str | None = None,
    generated_at:     datetime | None = None,
) -> AnalysisReport:
    """Assemble a complete AnalysisReport from analysis components."""
    ts = (generated_at or datetime.now(tz=timezone.utc)).isoformat()
    return AnalysisReport(
        run_dir=run_dir,
        generated_at=ts,
        total=total,
        passed=passed,
        failed=failed,
        skipped=skipped,
        errors=errors,
        duration_seconds=duration_seconds,
        summary=summary,
        failure_analyses=sorted(failure_analyses, key=lambda f: f.severity_order),
    )


def generate_html_report(report: AnalysisReport) -> str:
    """Render a fully self-contained HTML report string."""
    e = _e   # short alias for html.escape

    pass_pct = (report.passed / report.total * 100) if report.total else 0
    fail_pct = (report.failed / report.total * 100) if report.total else 0
    health = report.summary.overall_health
    score_pct = int(report.summary.health_score * 100)
    dur_str = _fmt_duration(report.duration_seconds)

    # Failure cards HTML
    failure_cards = "\n".join(
        _failure_card_html(fa) for fa in report.failure_analyses
    )
    if not failure_cards:
        failure_cards = '<p style="color:#107c10;font-weight:600">✓ No failures detected.</p>'

    # Recommendations
    recs = "\n".join(
        f"<li>{e(r)}</li>" for r in report.summary.recommendations
    ) or "<li>No specific recommendations.</li>"

    # Patterns
    patterns = " ".join(
        f'<span class="pattern-tag">{e(p)}</span>'
        for p in report.summary.failure_patterns
    ) or "<em>No patterns detected.</em>"

    # Priorities
    priorities = "\n".join(
        f'<li class="priority-item">{e(p)}</li>'
        for p in report.summary.top_priorities
    ) or "<li>None identified.</li>"

    # Env issues
    env_issues = "\n".join(
        f"<li>{e(i)}</li>" for i in report.summary.environment_issues
    ) or "<li>No environment issues detected.</li>"

    run_dir_str = e(report.run_dir or "N/A")
    gen_at_str  = e(report.generated_at or "")

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LISA Test Analysis Report</title>
<style>{_CSS}</style>
</head>
<body>
<div class="wrap">

  <!-- Header -->
  <div class="hdr">
    <h1>LISA Test Analysis Report</h1>
    <div class="meta">
      Generated: {gen_at_str} &nbsp;|&nbsp;
      Run dir: <code>{run_dir_str}</code>
    </div>
    <span class="health health-{e(health)}">
      {e(health.upper())} &nbsp; {score_pct}% health score
    </span>
  </div>

  <!-- Metrics -->
  <div class="metrics">
    <div class="mc"><div class="val total-val">{report.total}</div><div class="lbl">Total Tests</div></div>
    <div class="mc"><div class="val pass-val">{report.passed}</div><div class="lbl">Passed</div></div>
    <div class="mc"><div class="val fail-val">{report.failed + report.errors}</div><div class="lbl">Failed</div></div>
    <div class="mc"><div class="val skip-val">{report.skipped}</div><div class="lbl">Skipped</div></div>
    <div class="mc"><div class="val dur-val">{e(dur_str)}</div><div class="lbl">Duration</div></div>
  </div>

  <!-- Pass rate bar -->
  <div class="section">
    <h2>Pass Rate</h2>
    <strong>{pass_pct:.1f}%</strong> ({report.passed}/{report.total} tests passed)
    <div class="progress-bar" style="margin-top:.75rem">
      <div class="progress-fill pf-pass" style="width:{pass_pct:.1f}%;display:inline-block;float:left"></div>
      <div class="progress-fill pf-fail" style="width:{fail_pct:.1f}%;display:inline-block"></div>
    </div>
  </div>

  <!-- Executive Summary -->
  <div class="section">
    <h2>Executive Summary</h2>
    <p class="exec-summary">{e(report.summary.executive_summary) or "No summary available."}</p>
  </div>

  <!-- Failure Analysis -->
  <div class="section">
    <h2>Failure Analysis ({report.failed + report.errors} failures)</h2>
    {failure_cards}
  </div>

  <!-- Top Priorities -->
  <div class="section">
    <h2>Top Priorities</h2>
    <ol class="priority-list">
      {priorities}
    </ol>
  </div>

  <!-- Recommendations -->
  <div class="section">
    <h2>Recommendations</h2>
    <ul class="item-list">
      {recs}
    </ul>
  </div>

  <!-- Failure Patterns -->
  <div class="section">
    <h2>Failure Patterns Detected</h2>
    <div>{patterns}</div>
  </div>

  <!-- Environment Issues -->
  <div class="section">
    <h2>Environment / Infrastructure Issues</h2>
    <ul class="item-list">
      {env_issues}
    </ul>
  </div>

  <footer>
    Generated by <strong>LISA MCP Server</strong> using Claude AI &nbsp;|&nbsp;
    <a href="https://github.com/kkkashan/LISA_MCP_Server" style="color:#0078d4">
      github.com/kkkashan/LISA_MCP_Server
    </a>
  </footer>

</div>
</body>
</html>"""
    return html_doc


def generate_markdown_report(report: AnalysisReport) -> str:
    """Render a Markdown string from an AnalysisReport."""
    pass_pct  = (report.passed / report.total * 100) if report.total else 0
    health    = report.summary.overall_health.upper()
    score_pct = int(report.summary.health_score * 100)
    dur_str   = _fmt_duration(report.duration_seconds)

    lines: list[str] = [
        "# LISA Test Analysis Report",
        "",
        f"**Generated:** {report.generated_at}  ",
        f"**Run directory:** `{report.run_dir or 'N/A'}`  ",
        f"**Overall health:** **{health}** ({score_pct}% score)",
        "",
        "---",
        "",
        "## Run Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total | {report.total} |",
        f"| Passed | {report.passed} ({pass_pct:.1f}%) |",
        f"| Failed | {report.failed + report.errors} |",
        f"| Skipped | {report.skipped} |",
        f"| Duration | {dur_str} |",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        report.summary.executive_summary or "_No summary available._",
        "",
        "---",
        "",
        f"## Failure Analysis ({report.failed + report.errors} failures)",
        "",
    ]

    if not report.failure_analyses:
        lines.append("✅ No failures detected.")
    else:
        for i, fa in enumerate(report.failure_analyses, 1):
            conf_pct = int(fa.confidence * 100)
            lines += [
                f"### {i}. `{fa.test_name}`",
                "",
                f"| Field | Value |",
                f"|-------|-------|",
                f"| **Severity** | `{fa.severity.value.upper()}` |",
                f"| **Category** | `{fa.root_cause_category.value}` |",
                f"| **Confidence** | {conf_pct}% |",
                "",
                f"**Root Cause:**  ",
                fa.root_cause_description or "_Not determined._",
                "",
                f"**Recommended Fix:**  ",
                fa.recommended_fix or "_No recommendation._",
                "",
            ]
            if fa.relevant_log_lines:
                lines += [
                    "**Relevant Log Lines:**",
                    "```",
                ]
                lines.extend(fa.relevant_log_lines[:10])
                lines.append("```")
            lines.append("")

    lines += [
        "---",
        "",
        "## Top Priorities",
        "",
    ]
    for i, p in enumerate(report.summary.top_priorities, 1):
        lines.append(f"{i}. {p}")
    if not report.summary.top_priorities:
        lines.append("_None identified._")

    lines += [
        "",
        "---",
        "",
        "## Recommendations",
        "",
    ]
    for r in report.summary.recommendations:
        lines.append(f"- {r}")
    if not report.summary.recommendations:
        lines.append("_No specific recommendations._")

    lines += [
        "",
        "---",
        "",
        "## Failure Patterns",
        "",
    ]
    if report.summary.failure_patterns:
        for p in report.summary.failure_patterns:
            lines.append(f"- `{p}`")
    else:
        lines.append("_No patterns detected._")

    if report.summary.environment_issues:
        lines += [
            "",
            "---",
            "",
            "## Environment / Infrastructure Issues",
            "",
        ]
        for issue in report.summary.environment_issues:
            lines.append(f"- {issue}")

    lines += [
        "",
        "---",
        "",
        "_Generated by [LISA MCP Server](https://github.com/kkkashan/LISA_MCP_Server) using Claude AI_",
    ]
    return "\n".join(lines)


def save_report(
    report:     AnalysisReport,
    output_dir: str,
    base_name:  str = "lisa_analysis",
) -> dict[str, str]:
    """Write HTML and Markdown reports to *output_dir*. Returns file paths."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    html_path = out / f"{base_name}.html"
    md_path   = out / f"{base_name}.md"

    html_path.write_text(generate_html_report(report), encoding="utf-8")
    md_path.write_text(generate_markdown_report(report), encoding="utf-8")

    return {"html": str(html_path.resolve()), "markdown": str(md_path.resolve())}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _failure_card_html(fa: FailureAnalysis) -> str:
    e = _e
    sev  = fa.severity.value
    conf = int(fa.confidence * 100)

    log_block = ""
    if fa.relevant_log_lines:
        raw = "\n".join(fa.relevant_log_lines[:10])
        log_block = f'<div class="log-block">{e(raw)}</div>'

    return f"""<div class="fail-card fc-{e(sev)}">
  <div class="fail-card-hdr">
    <span class="test-name">{e(fa.test_name)}</span>
    <div class="badges">
      <span class="badge b-{e(sev)}">{e(sev.upper())}</span>
      <span class="badge b-cat">{e(fa.root_cause_category.value)}</span>
      <span class="badge b-conf">confidence {conf}%</span>
    </div>
  </div>
  <div class="fail-card-body">
    <div class="detail-grid">
      <div class="detail-item">
        <label>Root Cause</label>
        <p>{e(fa.root_cause_description) or "<em>Not determined.</em>"}</p>
      </div>
      <div class="detail-item">
        <label>Recommended Fix</label>
        <p>{e(fa.recommended_fix) or "<em>No recommendation.</em>"}</p>
      </div>
    </div>
    {log_block}
  </div>
</div>"""


def _fmt_duration(seconds: float) -> str:
    if seconds <= 0:
        return "N/A"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def _e(text: str) -> str:
    """HTML-escape helper."""
    return html.escape(str(text))
