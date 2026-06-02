# NeuraGraph Testing Guide

[README](../README.md) · [MANUAL](MANUAL.md) · [CODE_WIKI](CODE_WIKI.md) · [CHAT_COMMANDS](CHAT_COMMANDS.md)

This document describes **automated test suites**, **unit tests**, and where to find **checked-in test reports**.

---

## Quick start

From the project root, using the project venv:

```powershell
$env:PYTHONPATH = (Get-Location).Path
.\venv\Scripts\python.exe ui_tests\run_tests.py --suite unit
.\venv\Scripts\python.exe ui_tests\run_tests.py --suite agents
.\venv\Scripts\python.exe ui_tests\run_tests.py --suite agents-live
.\venv\Scripts\python.exe ui_tests\run_tests.py --suite graphs
```

Prerequisites for Playwright suites (`regression`, `current`, `experiment`, `graphs`): Chromium via Playwright, Flask on port **5001**, plugin sandbox on **5002** (started automatically by `run_tests.py` unless `--external-server`).

---

## Entry point: `ui_tests/run_tests.py`

| `--suite` | What it runs | Real LLM? |
| --- | --- | --- |
| `unit` | `ui_tests/unit/test_*.py` (unittest) | N/A |
| `agents` | All meta agents, `tests/<agent_id>/sample.csv` | **No** — mock LLM |
| `agents-live` | Same as agents | **Yes** — deepseek / gpt-oss_120b only |
| `graphs` | `playwright_graph_full_suite.py` (G1–G4 per workflow family) | **Yes** — `/stream/test` |
| `regression` | Stable UI tests 1–14 | UI only |
| `current` | Newer / flaky UI tests | UI only |
| `experiment` | Experiment wizard UI | UI + real runs when triggered |
| `cid-experiment` | CID NER/RE experiment UI smoke | Real workflow when run |
| `all` | regression + current + experiment + graphs + unit | Mixed |

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
    playwright_graph_full_suite.py
    playwright_regression_suite.py
    agent_invoke_mock_llm_suite.py
    ...
  unit/                     # Offline unittest (no server)
    test_graph_workflow_json_utils.py
    test_workflow_family_selection.py
    test_plan_and_triple_parse.py
    ...
  utils/                    # Fixtures, graph JSON helpers, report writer
  reports/                  # Committed snapshots (see README there)
  screenshots/              # Playwright captures + test_results.json
tests/                      # Per-agent / per-workflow CSV inputs (not scripts)
```

---

## Suite details

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

### Graph suite (`--suite graphs`)

Phases per representative workflow (`graph_ids_for_testing()` — one id per family plus baseline where kept):

| Phase | Checks |
| --- | --- |
| G1 | Backup `meta/graphs` → clear directory |
| G2 | UI inject → save → JSON + canvas topology diff |
| G3 | Branch graphs with ≥3 conditions (UI smoke) |
| G4 | SSE `/stream/test` until `[DONE]`; fails on `Stream error` or `status: failed` in stream |

**Not mock:** G4 runs real runners, agents, LLM, and plugins. G2/G3 do not execute LLM logic — only editor round-trip.

Playwright aggregate: [ui_tests/screenshots/test_results.json](../ui_tests/screenshots/test_results.json) (CID experiment UI run). Graph markdown report: [graph_suite_report_latest.md](../ui_tests/reports/graph_suite_report_latest.md) when a full suite completes.

### Playwright regression / current / experiment

See `ui_tests/suites/playwright_*_suite.py`. Results append to `ui_tests/screenshots/test_results.json` via `playwright_helpers.write_results()`.

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

## Regenerating reports

```powershell
# Agents (mock) — updates agent_test_report_YYYYMMDD_* and *_latest* if suite writes latest
.\venv\Scripts\python.exe ui_tests\suites\agent_invoke_mock_llm_suite.py

# Agents (live)
.\venv\Scripts\python.exe ui_tests\suites\agent_invoke_mock_llm_suite.py --live-llm

# Graphs (long; restores meta/graphs from backup when finished)
.\venv\Scripts\python.exe -u ui_tests\run_tests.py --suite graphs
```

Copy or symlink the newest `agent_test_report_*.md` into `*_latest*` before commit if you want docs to point at a specific run.

---

## Related docs

- Agent/output parsing: `utils/conversion.py`, `parse_as` on agent meta
- Graph family pruning: `utils/graphutils.py`, `scripts/prune_redundant_graphs.py`
- Chat command tests: [CHAT_COMMANDS.md](CHAT_COMMANDS.md#testing)
