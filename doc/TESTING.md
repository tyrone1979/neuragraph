# NeuraGraph Testing Guide

[README](../README.md) · [SUPPLEMENTARY](SUPPLEMENTARY.md) · [MANUAL](MANUAL.md) · [CODE_WIKI](CODE_WIKI.md) · [CHAT_COMMANDS](CHAT_COMMANDS.md)

This document describes **automated test suites**, **unit tests**, and where to find **checked-in test reports**.

---

## Quick start

From the project root, using the project venv:

```powershell
$env:PYTHONPATH = (Get-Location).Path
.\venv\Scripts\python.exe ui_tests\run_tests.py --suite regression-exp
.\venv\Scripts\python.exe ui_tests\run_tests.py --suite regression-graph
.\venv\Scripts\python.exe ui_tests\run_tests.py --suite regression-tool
.\venv\Scripts\python.exe ui_tests\run_tests.py --suite regression-agent
.\venv\Scripts\python.exe ui_tests\run_tests.py --suite unit
.\venv\Scripts\python.exe ui_tests\run_tests.py --suite agents
.\venv\Scripts\python.exe ui_tests\run_tests.py --suite all
```

Prerequisites for Playwright suites (`regression-*`): Chromium via Playwright, Flask on port **5001**, plugin sandbox on **5002** (started automatically by `run_tests.py` unless `--external-server`).

---

## Entry point: `ui_tests/run_tests.py`

| `--suite` | What it runs | Real LLM? |
| --- | --- | --- |
| `regression-exp` | Every `meta/graphs/*.json` — batch experiment, 2 articles, **with gold** and **without gold** | **Yes** — `/stream/run` |
| `regression-graph` | Every graph — G1–G4 (`playwright_regression_graph.py`) | **Yes** — G4 `/stream/test` |
| `regression-tool` | Every `meta/tools` entry — tool form UI + `/tools/api/run_tool` | Depends on tool |
| `regression-agent` | Every `meta/agents/*.json` — edit UI + mock-LLM batch invoke | **No** — mock LLM |
| `unit` | `ui_tests/unit/test_*.py` (unittest) | N/A |
| `agents` | All meta agents, `tests/<agent_id>/sample.csv` | **No** — mock LLM |
| `agents-live` | Same as agents | **Yes** — deepseek / gpt-oss_120b only |
| `all` | regression-exp + regression-graph + regression-tool + regression-agent + unit | Mixed |

Direct agent batch (writes reports under `ui_tests/reports/`):

```powershell
.\venv\Scripts\python.exe ui_tests\suites\agent_invoke_mock_llm_suite.py
.\venv\Scripts\python.exe ui_tests\suites\agent_invoke_mock_llm_suite.py --live-llm --agent agent_refiner
```

---

## Layout

```
ui_tests/
  run_tests.py              # CLI entry
  suites/                   # Playwright + agent batch
    playwright_regression_exp.py
    playwright_regression_graph.py
    playwright_regression_tool.py
    playwright_regression_agent.py
    agent_invoke_mock_llm_suite.py
  unit/                     # Offline unittest (no server)
    test_graph_workflow_json_utils.py
    test_workflow_family_selection.py
    test_plan_and_triple_parse.py
    ...
  utils/
    regression_helpers.py   # shared exp/graph/tool/agent regression helpers
  reports/                  # Committed snapshots (see README there)
  screenshots/              # Playwright captures + test_results.json (generated; not committed)
tests/                      # Per-agent / per-workflow CSV inputs (not scripts)
```

---

## Suite details

### Regression suites (`regression-exp` / `regression-graph` / `regression-tool` / `regression-agent`)

Full coverage with screenshots under `ui_tests/screenshots/` and aggregated results in `test_results.json`.

| Suite | Scope | Notes |
| --- | --- | --- |
| `regression-exp` | All graphs | 2-sample CSV per graph; runs once **with gold**, once **without gold** |
| `regression-graph` | All graphs | G1–G4 in `playwright_regression_graph.py` |
| `regression-tool` | All tools | Visits `/tools/{id}` and POSTs `/tools/api/run_tool` with schema/fixture inputs |
| `regression-agent` | All agents | Edit-page screenshots + in-process mock-LLM invoke (`agent_invoke_mock_llm_suite`) |

Filter to one item (debug):

```powershell
$env:NG_GRAPH_ONLY = "sg_cid_re_verify"
$env:NG_REGRESSION_EXP_ONLY = "sg_cid_re_verify"
$env:NG_REGRESSION_AGENT_ONLY = "relation_verify_llm"
.\venv\Scripts\python.exe ui_tests\run_tests.py --suite regression-exp
```

G4-only graph check (skip G1–G3 UI):

```powershell
$env:NG_GRAPH_SKIP_UI = "1"
.\venv\Scripts\python.exe ui_tests\run_tests.py --suite regression-graph
```

### Graph suite phases (`regression-graph`)

| Phase | Checks |
| --- | --- |
| G1 | **Simple:** create PGM workflow → run → copy → run copy → delete. **Nested:** L1→L2→L3 loops; **branch + 2 arms inside L3 body** → run → verify `route`/`result` |
| G2 | Open each graph editor and screenshot |
| G3 | Branch graphs with ≥3 conditions (UI smoke) |
| G4 | Each graph × gold / no_gold: Test modal `/stream/test` until complete |

**Not mock:** G1 (PGM run) and G4 run real workflow execution. G2/G3 do not execute LLM logic.

Skip G1 only:

```powershell
$env:NG_GRAPH_SKIP_G1 = "1"
.\venv\Scripts\python.exe ui_tests\run_tests.py --suite regression-graph
```

Graph markdown report: [graph_suite_report_latest.md](../ui_tests/reports/graph_suite_report_latest.md) when a full suite completes.

### Unit tests (`--suite unit`)

Fast, no browser. Covers parsers, graph backup/diff, workflow family selection, PubTator client, chat commands, report constraints, etc.

```powershell
.\venv\Scripts\python.exe -m unittest discover -s ui_tests/unit -p "test_*.py"
```

### Agent suite (`agents` / `agents-live`)

- Invokes every `meta/agents/*.json` with one row from `tests/<agent_id>/sample.csv`.
- **Mock mode** (`agents`): deterministic LLM stubs — good for CI and regressions; can miss prompt/parser bugs.
- **Live mode** (`agents-live`): real API calls; use after changing prompts, `parse_as`, or output parsers.

Reports: [agent mock full (43/43)](../ui_tests/reports/agent_test_report_mock_latest.md) · [live fixes (3 LLM agents)](../ui_tests/reports/agent_test_report_live_latest.md)

---

## Checked-in test reports

| Report | Description |
| --- | --- |
| [ui_tests/reports/README.md](../ui_tests/reports/README.md) | Index of all committed artifacts |
| [agent_test_report_mock_latest.md](../ui_tests/reports/agent_test_report_mock_latest.md) | Full agent batch, mock LLM, 43/43 pass |
| [agent_test_report_live_latest.md](../ui_tests/reports/agent_test_report_live_latest.md) | Live LLM verification (formerly failing agents) |
| [graph_suite_report_latest.md](../ui_tests/reports/graph_suite_report_latest.md) | Graph suite audit + per-case table (after full run) |

Timestamped runs from local executions may also exist as `agent_test_report_YYYYMMDD_*.md`; only `*_latest*` files are updated for documentation links.

---

## Graph suite troubleshooting

If **G4 shows `timed out` for every graph** (including fast `sg_*` subgraphs):

1. **Server wedged** — G2 runs many `saveGraph()` calls; a stuck dialog or slow Flask can leave port 5001 unresponsive. Restart the app, then re-run. The suite **restores `meta/graphs` from backup before G4** so stream tests use canonical JSON, not broken UI saves.
2. **G2c false FAIL** — Editor adds empty `agentVersions` / `flowNodes` while backups omit them; `normalize_graph` now treats those as equivalent.
3. **Quick G4-only check** (skip G1–G3 UI):

   ```powershell
   $env:NG_GRAPH_SKIP_UI = "1"
   .\venv\Scripts\python.exe -u ui_tests\run_tests.py --suite regression-graph
   ```

4. **Single graph**:

   ```powershell
   $env:NG_GRAPH_ONLY = "sg_cid_re_verify"
   $env:NG_GRAPH_SKIP_UI = "1"
   .\venv\Scripts\python.exe -u ui_tests\run_tests.py --suite regression-graph
   ```

Ensure port **5001** responds (`curl http://127.0.0.1:5001/`) and plugin sandbox **5002** is up before G4.

---

## Regenerating reports

```powershell
# Agents (mock)
.\venv\Scripts\python.exe ui_tests\suites\agent_invoke_mock_llm_suite.py

# Agents (live)
.\venv\Scripts\python.exe ui_tests\suites\agent_invoke_mock_llm_suite.py --live-llm

# Graphs (long; restores meta/graphs from backup when finished)
.\venv\Scripts\python.exe -u ui_tests\run_tests.py --suite regression-graph
```

Copy or symlink the newest `agent_test_report_*.md` into `*_latest*` before commit if you want docs to point at a specific run.

---

## Related docs

- Agent/output parsing: `utils/conversion.py`, `parse_as` on agent meta
- Graph family pruning: `utils/graphutils.py`, `scripts/prune_redundant_graphs.py`
- Chat command tests: [CHAT_COMMANDS.md](CHAT_COMMANDS.md#testing)
