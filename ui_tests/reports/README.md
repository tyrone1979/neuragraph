# UI test reports (committed snapshots)

Reports in this folder are **checked into git** so CI and reviewers can see last known results without re-running long suites.

## Index

| File | Suite | Mode | Summary |
| --- | --- | --- | --- |
| [agent_test_report_latest.md](agent_test_report_latest.md) | All agents | Mock LLM | **43/43 PASS** (alias of mock_latest) |
| [agent_test_report_latest.json](agent_test_report_latest.json) | All agents | Mock LLM | Machine-readable same run |
| [agent_test_report_mock_latest.md](agent_test_report_mock_latest.md) | All agents | Mock LLM | **43/43 PASS** |
| [agent_test_report_mock_latest.json](agent_test_report_mock_latest.json) | All agents | Mock LLM | JSON |
| [agent_test_report_live_latest.md](agent_test_report_live_latest.md) | 3 agents | Live LLM | **3/3 PASS** (refiner, synonym, tree RE) |
| [agent_test_report_live_latest.json](agent_test_report_live_latest.json) | 3 agents | Live LLM | JSON |
| [graph_suite_report_latest.md](graph_suite_report_latest.md) | Graph G1–G4 | Real `/stream/test` | Status / audit (see file) |

## Other artifacts

- Playwright CID experiment UI: [../screenshots/test_results.json](../screenshots/test_results.json)
- Playwright captures: [../screenshots/](../screenshots/) (`g2_editor_*.png`, etc.)
- Full documentation: [../../doc/TESTING.md](../../doc/TESTING.md)

## Local-only files

Runs also write timestamped files such as `agent_test_report_YYYYMMDD_HHMMSS.md`. Those are optional to commit; update `*_latest*` before push when you want docs to reflect a new baseline.
