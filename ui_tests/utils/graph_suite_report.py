"""Write markdown audit/run report for the graph Playwright suite."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ui_tests.utils.graph_workflow_json_utils import (
    ROOT,
    discover_graph_ids,
    graph_run_params,
    list_graph_ids,
)
from ui_tests.utils import playwright_helpers as ph


def _input_source(graph_id: str) -> str:
    test_dir = ROOT / "tests" / graph_id
    if test_dir.is_dir() and any(test_dir.glob("*.csv")):
        return f"tests/{graph_id}/*.csv"
    from ui_tests.utils.graph_workflow_json_utils import LEGACY_GRAPH_INPUTS

    if graph_id in LEGACY_GRAPH_INPUTS:
        return "LEGACY_GRAPH_INPUTS"
    return "DEFAULT_GRAPH_INPUT"


def write_graph_suite_report(
    screenshots_dir: str | Path,
    *,
    suite_label: str = "regression-graph",
    mock_llm: bool = False,
) -> Path:
    screenshots_dir = Path(screenshots_dir)
    results_path = screenshots_dir / "test_results.json"
    payload: dict[str, Any] = {}
    if results_path.is_file():
        payload = json.loads(results_path.read_text(encoding="utf-8"))

    graph_ids = sorted(discover_graph_ids(from_backup=False))
    rows = payload.get("results") or ph.results
    passed = sum(1 for r in rows if r.get("status") == "PASS")
    failed = sum(1 for r in rows if r.get("status") == "FAIL")
    total = len(rows)

    lines = [
        "# Graph Test Suite Report",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Suite: `{suite_label}` (Playwright `playwright_regression_graph.py`)",
        f"- Mock LLM: **{'yes' if mock_llm else 'no — G4 uses real /stream/test (LLM + plugins)'}**",
        f"- Workflows under test: **{len(graph_ids)}** (all graphs under `meta/graphs`)",
        f"- On disk (`meta/graphs`): **{len(list_graph_ids(from_backup=False))}** JSON files",
        f"- Playwright cases: **{total}** | PASS **{passed}** | FAIL **{failed}**",
        "",
        "## Coverage audit (mock vs real)",
        "",
        "| Phase | What it tests | Mock? | Gap risk |",
        "| --- | --- | --- | --- |",
        "| G1 | Backup + clear `meta/graphs` | — | Low |",
        "| G2 | UI inject → save → JSON/canvas diff | No LLM | **Medium** — editor round-trip only |",
        "| G3 | Branch nodes (≥3 conditions) UI | No LLM | Low (structure) |",
        "| G4 | SSE `/stream/test` end-to-end | **Real** runners/agents/LLM | **High** — was only `[DONE]`; now fails on `Stream error` / `status: failed` in SSE |",
        "",
        "Unlike `agent_invoke_mock_llm_suite.py`, this suite has **no mock-LLM mode**. "
        "The main false-confidence risk is **weak G4 assertions** (stream finished) not **mocked models**.",
        "",
        "## Workflow inputs (G4)",
        "",
        "| Graph ID | Input source |",
        "| --- | --- |",
    ]
    for gid in graph_ids:
        lines.append(f"| `{gid}` | {_input_source(gid)} |")

    lines.extend(["", "## Per-case results", "", "| Case | Status | Detail |", "| --- | --- | --- |"])
    for r in rows:
        status = r.get("status", "?")
        mark = "**PASS**" if status == "PASS" else f"**{status}**"
        detail = str(r.get("detail", "")).replace("|", "\\|")[:180]
        lines.append(f"| `{r.get('test', '')}` | {mark} | {detail} |")

    if payload.get("errors"):
        lines.extend(["", "## Page errors", ""])
        for err in payload["errors"][:10]:
            lines.append(f"- {err}")

    lines.append("")
    report_dir = ROOT / "ui_tests" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = report_dir / f"graph_suite_report_{stamp}.md"
    latest = report_dir / "graph_suite_report_latest.md"
    text = "\n".join(lines) + "\n"
    out.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    json_out = report_dir / f"graph_suite_report_{stamp}.json"
    json_payload = (
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mock_llm": mock_llm,
            "graph_ids": graph_ids,
            "input_sources": {gid: _input_source(gid) for gid in graph_ids},
            "passed": passed,
            "failed": failed,
            "total": total,
            "results": rows,
            "page_errors": payload.get("errors") or ph.page_errors[:10],
        }
    )
    json_text = json.dumps(json_payload, ensure_ascii=False, indent=2)
    json_out.write_text(json_text, encoding="utf-8")
    (report_dir / "graph_suite_report_latest.json").write_text(json_text, encoding="utf-8")
    return out
