#!/usr/bin/env python3
"""Regenerate doc/META_INVENTORY.md from meta/agents and meta/graphs."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "doc" / "META_INVENTORY.md"


def _esc(text: str) -> str:
    return str(text or "").replace("|", "/").replace("\n", " ").strip()


def _load_agents() -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    for path in sorted((ROOT / "meta" / "agents").glob("*.json")):
        meta = json.loads(path.read_text(encoding="utf-8"))
        rows.append(
            (
                path.stem,
                _esc(meta.get("name")),
                str(meta.get("type") or "?"),
                _esc(meta.get("description")),
            )
        )
    return rows


def _load_graphs() -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    for path in sorted((ROOT / "meta" / "graphs").glob("*.json")):
        stem = path.stem
        if not (stem.startswith("wf_") or stem.startswith("sg_")):
            continue
        meta = json.loads(path.read_text(encoding="utf-8"))
        kind = "subgraph" if stem.startswith("sg_") else "workflow"
        rows.append(
            (
                stem,
                _esc(meta.get("name")),
                kind,
                _esc(meta.get("description")),
            )
        )
    return rows


def _table(title: str, rows: list[tuple[str, str, str, str]]) -> list[str]:
    lines = [f"### {title}", "", "| No. | ID | Type | Name | Description |", "| ---: | --- | --- | --- | --- |"]
    for idx, (aid, name, typ, desc) in enumerate(rows, start=1):
        lines.append(f"| {idx} | `{aid}` | {typ} | {name} | {desc} |")
    lines.append("")
    return lines


def main() -> None:
    agents = _load_agents()
    graphs = _load_graphs()
    type_counts = Counter(t for _, _, t, _ in agents)
    sg_count = sum(1 for _, _, k, _ in graphs if k == "subgraph")
    wf_count = sum(1 for _, _, k, _ in graphs if k == "workflow")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    llm_rows = [r for r in agents if r[2] == "LLM"]
    pgm_rows = [r for r in agents if r[2] != "LLM"]
    sg_rows = [r for r in graphs if r[2] == "subgraph"]
    wf_rows = [r for r in graphs if r[2] == "workflow"]

    lines = [
        "# Meta inventory (agents & graphs)",
        "",
        f"Generated: {stamp} via `scripts/gen_meta_inventory.py`.",
        "",
        f"- **Agents:** {len(agents)} ({type_counts.get('LLM', 0)} LLM, {type_counts.get('PGM', 0)} PGM)",
        f"- **Graphs:** {len(graphs)} ({sg_count} subgraphs, {wf_count} workflows)",
        f"- **Agent test data:** `tests/<agent_id>/sample.csv` (1 row each; see `ui_tests/utils/agent_sample_row_fixtures.py`)",
        "",
        "## Agents",
        "",
        *_table(f"LLM agents ({len(llm_rows)})", llm_rows),
        *_table(f"PGM agents ({len(pgm_rows)})", pgm_rows),
        "## Graphs",
        "",
        *_table(f"Subgraphs ({len(sg_rows)})", sg_rows),
        *_table(f"Workflows ({len(wf_rows)})", wf_rows),
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} ({len(agents)} agents, {len(graphs)} graphs)")


if __name__ == "__main__":
    main()
