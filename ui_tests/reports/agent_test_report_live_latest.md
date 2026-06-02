# Agent Test Report (live LLM — regression fixes)

- Generated: 2026-06-02 (venv verification before push)
- Mock LLM: **False** (deepseek / gpt-oss_120b only)
- Total: **3** | Passed: **3** | Failed: **0**

These agents previously failed under live LLM; fixed in commit `5555880` (`parse_as` scope, refiner prompt braces, tree/synonym sample CSV).

| Agent | Type | Status | Model | Message |
| --- | --- | --- | --- | --- |
| `agent_refiner` | LLM | **PASS** | deepseek | ok |
| `ontology_synonym_extract` | LLM | **PASS** | gpt-oss_120b | ok |
| `relation_from_tree_llm` | LLM | **PASS** | gpt-oss_120b | ok |

Full mock regression for all 43 agents: [agent_test_report_mock_latest.md](agent_test_report_mock_latest.md).
