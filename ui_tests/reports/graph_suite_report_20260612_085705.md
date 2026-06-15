# Graph Test Suite Report

- Generated: 2026-06-12T00:57:05.708901+00:00
- Suite: `regression-graph` (Playwright `playwright_regression_graph.py`)
- Mock LLM: **no — G4 uses real /stream/test (LLM + plugins)**
- Workflows under test: **30** (all graphs under `meta/graphs`)
- On disk (`meta/graphs`): **30** JSON files
- Playwright cases: **3** | PASS **3** | FAIL **0**

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
| `sg_cid_re_verify` | tests/sg_cid_re_verify/*.csv |
| `sg_e2e_cid_re` | DEFAULT_GRAPH_INPUT |
| `sg_e2e_flair_ner` | DEFAULT_GRAPH_INPUT |
| `sg_e2e_pubtator_re` | DEFAULT_GRAPH_INPUT |
| `sg_ner_flair_sent` | LEGACY_GRAPH_INPUTS |
| `sg_preprocess_inner` | LEGACY_GRAPH_INPUTS |
| `sg_re_preprocess` | LEGACY_GRAPH_INPUTS |
| `sg_re_tree` | LEGACY_GRAPH_INPUTS |
| `sg_relation_verify` | LEGACY_GRAPH_INPUTS |
| `wf_cid_ner_llm_eval` | tests/wf_cid_ner_llm_eval/*.csv |
| `wf_cid_re_branch` | tests/wf_cid_re_branch/*.csv |
| `wf_cid_re_llm_linear` | tests/wf_cid_re_llm_linear/*.csv |
| `wf_cid_re_llm_linear_opt_20260529_143039_r2` | tests/wf_cid_re_llm_linear_opt_20260529_143039_r2/*.csv |
| `wf_cid_re_llm_linear_opt_20260604` | tests/wf_cid_re_llm_linear_opt_20260604/*.csv |
| `wf_doc_ner_flair_eval` | tests/wf_doc_ner_flair_eval/*.csv |
| `wf_doc_ner_flair_sent_eval` | tests/wf_doc_ner_flair_sent_eval/*.csv |
| `wf_doc_ner_llm_eval` | tests/wf_doc_ner_llm_eval/*.csv |
| `wf_doc_ner_loop_branch` | tests/wf_doc_ner_loop_branch/*.csv |
| `wf_doc_re_nested_branch` | tests/wf_doc_re_nested_branch/*.csv |
| `wf_e2e_flair_opt_re` | tests/wf_e2e_flair_opt_re/*.csv |
| `wf_e2e_pubtator_re` | DEFAULT_GRAPH_INPUT |
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
| `G2-wf_e2e_flair_opt_re` | **PASS** | screenshot |
| `G3-skip` | **PASS** | NG_GRAPH_SKIP_UI set |
| `G4-skip` | **PASS** | NG_GRAPH_SKIP_G4 set |

