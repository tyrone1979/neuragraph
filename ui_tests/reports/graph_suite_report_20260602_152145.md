# Graph Test Suite Report

- Generated: 2026-06-02T07:21:45.964676+00:00
- Suite: `graphs` (Playwright `playwright_graph_full_suite.py`)
- Mock LLM: **no — G4 uses real /stream/test (LLM + plugins)**
- Workflows under test: **26** (one per family via `graph_ids_for_testing`)
- On disk (`meta/graphs`): **26** JSON files
- Playwright cases: **27** | PASS **27** | FAIL **0**

## Coverage audit (mock vs real)

| Phase | What it tests | Mock? | Gap risk |
| --- | --- | --- | --- |
| G1 | Backup + clear `meta/graphs` | — | Low |
| G2 | UI inject → save → JSON/canvas diff | No LLM | **Medium** — editor round-trip only |
| G3 | Branch nodes (≥3 conditions) UI | No LLM | Low (structure) |
| G4 | SSE `/stream/test` end-to-end | **Real** runners/agents/LLM | **High** — was only `[DONE]`; now fails on `Stream error` / `status: failed` in SSE |

Unlike `agent_invoke_mock_llm_suite.py`, this suite has **no mock-LLM mode**. The main false-confidence risk is **weak G4 assertions** (stream finished) not **mocked models**.

## Workflow inputs (G4)

| Graph ID | Input source |
| --- | --- |
| `ner_flair_sent_loop` | DEFAULT_GRAPH_INPUT |
| `sg_cid_re_verify` | tests/sg_cid_re_verify/*.csv |
| `sg_ner_flair_sent` | LEGACY_GRAPH_INPUTS |
| `sg_ner_llm_tree` | LEGACY_GRAPH_INPUTS |
| `sg_preprocess_inner` | LEGACY_GRAPH_INPUTS |
| `sg_re_preprocess` | LEGACY_GRAPH_INPUTS |
| `sg_re_tree` | LEGACY_GRAPH_INPUTS |
| `sg_relation_verify` | LEGACY_GRAPH_INPUTS |
| `wf_cid_ner_flair_eval` | tests/wf_cid_ner_flair_eval/*.csv |
| `wf_cid_ner_llm_eval` | tests/wf_cid_ner_llm_eval/*.csv |
| `wf_cid_re_branch` | tests/wf_cid_re_branch/*.csv |
| `wf_cid_re_llm_linear` | tests/wf_cid_re_llm_linear/*.csv |
| `wf_cid_re_llm_linear_opt_20260529_143039_r2` | tests/wf_cid_re_llm_linear_opt_20260529_143039_r2/*.csv |
| `wf_doc_ner_flair_eval` | tests/wf_doc_ner_flair_eval/*.csv |
| `wf_doc_ner_llm_eval` | tests/wf_doc_ner_llm_eval/*.csv |
| `wf_doc_ner_loop_branch` | tests/wf_doc_ner_loop_branch/*.csv |
| `wf_doc_re_nested_branch` | tests/wf_doc_re_nested_branch/*.csv |
| `wf_flair_vs_llm_ner` | tests/wf_flair_vs_llm_ner/*.csv |
| `wf_general_report_linear` | tests/wf_general_report_linear/*.csv |
| `wf_kg_flair_full` | tests/wf_kg_flair_full/*.csv |
| `wf_kg_llm_full` | tests/wf_kg_llm_full/*.csv |
| `wf_kg_syntax_loop` | tests/wf_kg_syntax_loop/*.csv |
| `wf_re_pubtator_dev10` | tests/wf_re_pubtator_dev10/*.csv |
| `wf_re_pubtator_eval` | tests/wf_re_pubtator_eval/*.csv |
| `wf_re_verify_llm_loop` | tests/wf_re_verify_llm_loop/*.csv |
| `wf_word_seg_llm_eval` | tests/wf_word_seg_llm_eval/*.csv |

## Per-case results

| Case | Status | Detail |
| --- | --- | --- |
| `cid_ner-dataset-listed` | **PASS** | True |
| `cid_ner-dataset-2-samples` | **PASS** | True |
| `cid_ner-runner-id` | **PASS** |  |
| `cid_ner-dataset-select` | **PASS** |  |
| `cid_ner-preview-gold` | **PASS** |  |
| `cid_ner-exp-id` | **PASS** | True |
| `cid_ner-results-file` | **PASS** | True |
| `cid_ner-results-page` | **PASS** |  |
| `cid_ner-results-persisted` | **PASS** | True |
| `cid_ner-has-metrics` | **PASS** | True |
| `cid_ner-has-entities` | **PASS** | True |
| `cid_ner-report-html` | **PASS** | True |
| `cid_re-dataset-listed` | **PASS** | True |
| `cid_re-dataset-2-samples` | **PASS** | True |
| `cid_re-runner-id` | **PASS** |  |
| `cid_re-dataset-select` | **PASS** |  |
| `cid_re-preview-gold` | **PASS** |  |
| `cid_re-exp-id` | **PASS** | True |
| `cid_re-results-file` | **PASS** | True |
| `cid_re-results-page` | **PASS** |  |
| `cid_re-results-persisted` | **PASS** | True |
| `cid_re-has-metrics` | **PASS** | True |
| `cid_re-has-entities` | **PASS** | True |
| `cid_re-report-html` | **PASS** | True |
| `cid-list-page` | **PASS** | True |
| `cid-list-ner` | **PASS** | True |
| `cid-list-re` | **PASS** | True |

