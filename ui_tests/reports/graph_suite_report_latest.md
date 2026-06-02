# Graph Test Suite Report

- Generated: 2026-06-02 (documentation baseline; full Playwright G1–G4 run pending)
- Suite: `playwright_graph_full_suite.py` via `ui_tests/run_tests.py --suite graphs`
- Mock LLM: **no** — G4 uses real `/stream/test` (LLM + plugins)

## Coverage audit (mock vs real)

| Phase | What it tests | Mock? | Gap risk |
| --- | --- | --- | --- |
| G1 | Backup + clear `meta/graphs` | — | Low |
| G2 | UI inject → save → JSON/canvas diff | No LLM | Medium — editor only |
| G3 | Branch nodes (≥3 conditions) | No LLM | Low |
| G4 | SSE workflow run | **Real** | High if only checking `[DONE]` — suite also fails on `Stream error` / `status: failed` in SSE |

Unlike the agent suite, there is **no mock-LLM mode** for graphs. False confidence comes from weak stream assertions or missing `tests/<graph_id>/*.csv` (falls back to `LEGACY_GRAPH_INPUTS`).

## Last full run status

A complete G1–G4 run for all `graph_ids_for_testing()` (~24 workflows) was **interrupted** (Playwright dialog race; fixed with `_safe_accept_dialog` in `playwright_graph_full_suite.py`).

Re-run and replace this file:

```powershell
$env:PYTHONPATH = (Get-Location).Path
.\venv\Scripts\python.exe -u ui_tests\run_tests.py --suite graphs
```

The suite writes an updated `graph_suite_report_latest.md` and `.json` on completion.

## Workflow inputs

See [doc/TESTING.md](../../doc/TESTING.md#graph-suite---suite-graphs) for input sources (`tests/<id>/*.csv` vs legacy map).
