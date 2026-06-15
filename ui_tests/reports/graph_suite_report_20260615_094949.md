# Graph Test Suite Report

- Generated: 2026-06-15T01:49:49.262552+00:00
- Suite: `regression-graph` (Playwright `playwright_regression_graph.py`)
- Mock LLM: **no — G4 uses real /stream/test (LLM + plugins)**
- Workflows under test: **33** (all graphs under `meta/graphs`)
- On disk (`meta/graphs`): **33** JSON files
- Playwright cases: **85** | PASS **83** | FAIL **2**

## Coverage audit (mock vs real)

| Phase | What it tests | Mock? | Gap risk |
| --- | --- | --- | --- |
| G1 | Simple lifecycle + 3-level nested loops / inner branch | **Real** PGM run | Low |
| G2 | Editor screenshots per graph | No LLM | Low — layout smoke |
| G3 | Branch nodes (≥3 conditions) UI | No LLM | Low (structure) |
| G4 | SSE `/stream/test` end-to-end | **Real** runners/agents/LLM | **High** — was only `[DONE]`; now fails on `Stream error` / `status: failed` in SSE |

Unlike `agent_invoke_mock_llm_suite.py`, this suite has **no mock-LLM mode**. The main false-confidence risk is **weak G4 assertions** (stream finished) not **mocked models**.

## Workflow inputs (G4)

| Graph ID | Input source |
| --- | --- |
| `sg_chemdisgene_re_verify` | tests/sg_chemdisgene_re_verify/*.csv |
| `sg_cid_re_verify` | tests/sg_cid_re_verify/*.csv |
| `sg_e2e_cid_re` | tests/sg_e2e_cid_re/*.csv |
| `sg_e2e_flair_ner` | tests/sg_e2e_flair_ner/*.csv |
| `sg_e2e_pubtator_re` | tests/sg_e2e_pubtator_re/*.csv |
| `sg_ner_flair_sent` | tests/sg_ner_flair_sent/*.csv |
| `sg_preprocess_inner` | tests/sg_preprocess_inner/*.csv |
| `sg_re_preprocess` | tests/sg_re_preprocess/*.csv |
| `sg_re_tree` | tests/sg_re_tree/*.csv |
| `sg_relation_verify` | tests/sg_relation_verify/*.csv |
| `wf_chemdisgene_ner_llm_eval` | tests/wf_chemdisgene_ner_llm_eval/*.csv |
| `wf_chemdisgene_re_llm_linear` | tests/wf_chemdisgene_re_llm_linear/*.csv |
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
| `wf_e2e_pubtator_re` | tests/wf_e2e_pubtator_re/*.csv |
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
| `G1-build` | **PASS** | nodes=START,report_format_json,END |
| `G1-save` | **PASS** | rg_lc_20260615_093825 |
| `G1-run-rg_lc_20260615_093825` | **PASS** | completed |
| `G1-copy` | **PASS** | rg_lc_20260615_093825_copy |
| `G1-run-rg_lc_20260615_093825_copy` | **PASS** | completed |
| `G1-delete-rg_lc_20260615_093825_copy` | **PASS** | removed |
| `G1-delete-rg_lc_20260615_093825` | **PASS** | removed |
| `G1-cleanup` | **PASS** | both workflows removed from list |
| `G1b-save-rg_sg_l3_20260615_093852` | **PASS** | subgraph saved |
| `G1b-save-rg_sg_l2_20260615_093852` | **PASS** | subgraph saved |
| `G1b-save-rg_sg_l1_20260615_093852` | **PASS** | subgraph saved |
| `G1b-build` | **PASS** | 3-level loops + branch on canvas |
| `G1b-save-main` | **PASS** | rg_wf_nested_20260615_093852 |
| `G1b-run` | **PASS** | completed |
| `G1b-run-verify` | **FAIL** | branch labels missing in summaries: ['Has text', 'Has text', 'Has text', 'Has text', 'Has text', 'Has text'] |
| `G2-sg_chemdisgene_re_verify` | **PASS** | screenshot |
| `G2-sg_cid_re_verify` | **PASS** | screenshot |
| `G2-sg_e2e_cid_re` | **PASS** | screenshot |
| `G2-sg_e2e_flair_ner` | **PASS** | screenshot |
| `G2-sg_e2e_pubtator_re` | **PASS** | screenshot |
| `G2-sg_ner_flair_sent` | **PASS** | screenshot |
| `G2-sg_preprocess_inner` | **PASS** | screenshot |
| `G2-sg_re_preprocess` | **PASS** | screenshot |
| `G2-sg_re_tree` | **PASS** | screenshot |
| `G2-sg_relation_verify` | **PASS** | screenshot |
| `G2-wf_chemdisgene_ner_llm_eval` | **PASS** | screenshot |
| `G2-wf_chemdisgene_re_llm_linear` | **PASS** | screenshot |
| `G2-wf_cid_ner_llm_eval` | **PASS** | screenshot |
| `G2-wf_cid_re_branch` | **PASS** | screenshot |
| `G2-wf_cid_re_llm_linear` | **PASS** | screenshot |
| `G2-wf_cid_re_llm_linear_opt_20260529_143039_r2` | **FAIL** | graph not loaded |
| `G2-wf_cid_re_llm_linear_opt_20260604` | **PASS** | screenshot |
| `G2-wf_doc_ner_flair_eval` | **PASS** | screenshot |
| `G2-wf_doc_ner_flair_sent_eval` | **PASS** | screenshot |
| `G2-wf_doc_ner_llm_eval` | **PASS** | screenshot |
| `G2-wf_doc_ner_loop_branch` | **PASS** | screenshot |
| `G2-wf_doc_re_nested_branch` | **PASS** | screenshot |
| `G2-wf_e2e_flair_opt_re` | **PASS** | screenshot |
| `G2-wf_e2e_pubtator_re` | **PASS** | screenshot |
| `G2-wf_flair_vs_llm_ner` | **PASS** | screenshot |
| `G2-wf_general_report_linear` | **PASS** | screenshot |
| `G2-wf_kg_flair_full` | **PASS** | screenshot |
| `G2-wf_kg_llm_full` | **PASS** | screenshot |
| `G2-wf_kg_syntax_loop` | **PASS** | screenshot |
| `G2-wf_re_pubtator_dev10` | **PASS** | screenshot |
| `G2-wf_re_pubtator_eval` | **PASS** | screenshot |
| `G2-wf_re_verify_llm_loop` | **PASS** | screenshot |
| `G2-wf_word_seg_llm_eval` | **PASS** | screenshot |
| `G3-sg_chemdisgene_re_verify` | **PASS** | re_tpl_branch conditions=14 |
| `G3-wf_cid_re_branch` | **PASS** | cid_re_gate conditions=4 |
| `G3-wf_doc_ner_loop_branch` | **PASS** | ner_route conditions=4 |
| `G3-wf_doc_re_nested_branch` | **PASS** | re_gate conditions=4 |
| `G4-sg_chemdisgene_re_verify-gold` | **PASS** | completed |
| `G4-sg_cid_re_verify-gold` | **PASS** | completed |
| `G4-sg_e2e_cid_re-gold` | **PASS** | completed |
| `G4-sg_e2e_flair_ner-gold` | **PASS** | completed |
| `G4-sg_e2e_pubtator_re-gold` | **PASS** | completed |
| `G4-sg_ner_flair_sent-gold` | **PASS** | completed |
| `G4-sg_preprocess_inner-gold` | **PASS** | completed |
| `G4-sg_re_preprocess-gold` | **PASS** | completed |
| `G4-sg_re_tree-gold` | **PASS** | completed |
| `G4-sg_relation_verify-gold` | **PASS** | completed |
| `G4-wf_chemdisgene_ner_llm_eval-gold` | **PASS** | completed |
| `G4-wf_chemdisgene_re_llm_linear-gold` | **PASS** | completed |
| `G4-wf_cid_ner_llm_eval-gold` | **PASS** | completed |
| `G4-wf_cid_re_branch-gold` | **PASS** | completed |
| `G4-wf_cid_re_llm_linear-gold` | **PASS** | completed |
| `G4-wf_cid_re_llm_linear_opt_20260529_143039_r2-gold` | **PASS** | completed |
| `G4-wf_cid_re_llm_linear_opt_20260604-gold` | **PASS** | completed |
| `G4-wf_doc_ner_flair_eval-gold` | **PASS** | completed |
| `G4-wf_doc_ner_flair_sent_eval-gold` | **PASS** | completed |
| `G4-wf_doc_ner_llm_eval-gold` | **PASS** | completed |
| `G4-wf_doc_ner_loop_branch-gold` | **PASS** | completed |
| `G4-wf_doc_re_nested_branch-gold` | **PASS** | completed |
| `G4-wf_e2e_flair_opt_re-gold` | **PASS** | completed |
| `G4-wf_e2e_pubtator_re-gold` | **PASS** | completed |
| `G4-wf_flair_vs_llm_ner-gold` | **PASS** | completed |
| `G4-wf_general_report_linear-gold` | **PASS** | completed |
| `G4-wf_kg_flair_full-gold` | **PASS** | completed |
| `G4-wf_kg_llm_full-gold` | **PASS** | completed |
| `G4-wf_kg_syntax_loop-gold` | **PASS** | completed |
| `G4-wf_re_pubtator_dev10-gold` | **PASS** | completed |
| `G4-wf_re_pubtator_eval-gold` | **PASS** | completed |
| `G4-wf_re_verify_llm_loop-gold` | **PASS** | completed |
| `G4-wf_word_seg_llm_eval-gold` | **PASS** | completed |

