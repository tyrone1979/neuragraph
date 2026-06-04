# Agent Test Report

- Generated: 2026-06-02T01:37:28.140574+00:00
- Mock LLM: True
- Total: 43 | Passed: 43 | Failed: 0 | Skipped: 0

| Agent | Type | Status | ms | Message | Output preview |
| --- | --- | --- | ---: | --- | --- |
| `agent_refiner` | LLM | **PASS** | 5376 | ok | "{\"modifications\": []}" |
| `cid_pair_generate` | PGM | **PASS** | 257 | ok | [{"head": "Aspirin", "tail": "heart disease", "head_id": "D001241", "tail_id": "D006331"}, {"head": "Aspirin", "tail": "toxicity", "head_id": "D001241", "tail_id": "D064420"}, {"head": "Lithium carbonate", "tail": "heart disease", "head_... |
| `dataset_cid_tuning_build` | PGM | **PASS** | 108 | ok | {"runner_id": "wf_cid_re_llm_linear", "tuning_output": "cid_agent_test_tuning.csv", "tuning_path": "tests/wf_cid_re_llm_linear/cid_agent_test_tuning.csv", "tuning_count": 2, "summary": {"picked": 2, "source": "comparison/data/CDR/dev.txt"}} |
| `eval_flair` | PGM | **PASS** | 63 | ok | {"total_entities": 2, "label_count": 2, "per_label_entity_count": {"Chemical": 1, "Disease": 1}} |
| `eval_llm` | PGM | **PASS** | 51 | ok | {"total_entities": 2, "label_count": 2, "per_label_entity_count": {"Chemical": 1, "Disease": 1}} |
| `eval_metrics` | PGM | **PASS** | 76 | ok | {"precision": 1.0, "recall": 0.6666666666666666, "f1": 0.8, "tp": 2, "fp": 0, "fn": 1} |
| `eval_metrics_relation` | PGM | **PASS** | 69 | ok | {"precision": 1.0, "recall": 0.5, "f1": 0.6666666666666666, "tp": 1, "fp": 0, "fn": 1} |
| `eval_metrics_segment` | PGM | **PASS** | 63 | ok | {"metrics": {"precision": 1.0, "recall": 1.0, "f1": 1.0, "correct_boundaries": 3, "predicted_boundaries": 3, "real_boundaries": 3}, "error_analysis": {"over_segmentation": [], "under_segmentation": [], "boundary_shift": []}, "summary": {... |
| `eval_pair_generate` | PGM | **PASS** | 112 | ok | [{"head": "Aspirin", "tail": "heart disease"}] |
| `kg_rdf_export` | PGM | **PASS** | 93 | ok | {"@context": {"label": "http://schema.org/name"}, "nodes": [{"@id": "Aspirin", "label": "Aspirin"}, {"@id": "heart_disease", "label": "heart disease"}], "edges": [{"@id": "e0", "subject": "Aspirin", "predicate": "treats", "object": "hear... |
| `kg_triple_extract_llm` | LLM | **PASS** | 383 | ok | [{"head": "Aspirin", "predicate": "treats", "tail": "heart disease"}] |
| `kg_triple_merge` | PGM | **PASS** | 76 | ok | [{"head": "D001241", "predicate": "treats", "tail": "D006331"}] |
| `kg_triple_persist` | PGM | **PASS** | 82 | ok | [{"head": "Aspirin", "predicate": "treats", "tail": "heart disease"}] |
| `llm_link_bulk_update` | PGM | **PASS** | 190 | ok | {"target_model": "deepseek", "source_model": null, "dry_run": true, "updated_count": 13, "skipped_count": 30, "updated": [{"agent_id": "kg_triple_extract_llm", "name": "Triple Extraction (LLM)", "old_model": "kimi-2.6", "new_model": "dee... |
| `merge_metrics` | PGM | **PASS** | 86 | ok | {"flair_metrics": {"micro": {"precision": 0.8, "recall": 0.7, "f1": 0.75}}, "llm_metrics": {"micro": {"precision": 0.9, "recall": 0.6, "f1": 0.72}}} |
| `ner_comparison_report` | LLM | **PASS** | 73 | ok | "## NER Comparison\n\nFlair and LLM metrics are comparable on the sample." |
| `ner_flair_aggregate` | PGM | **PASS** | 61 | ok | {"Chemical": ["Aspirin"], "Disease": ["heart disease"]} |
| `ner_flair_doc` | PGM | **PASS** | 1292 | ok | {"Chemical": ["Aspirin", "Lithium carbonate"], "Disease": ["heart disease"]} |
| `ner_flair_sent` | PGM | **PASS** | 829 | ok | {"Chemical": ["Aspirin"], "Disease": ["heart disease"]} |
| `ner_from_tree_llm` | LLM | **PASS** | 98 | ok | {"Chemical": ["Aspirin"], "Disease": ["heart disease"]} |
| `ner_llm` | LLM | **PASS** | 121 | ok | {"Chemical": ["Aspirin"], "Disease": ["heart disease"]} |
| `ontology_entity_link` | LLM | **PASS** | 75 | ok | {"Aspirin": {"canonical": "Aspirin", "id": "D001241"}} |
| `ontology_hypernym_filter` | LLM | **PASS** | 123 | ok | [{"text": "Aspirin", "id": "D001241", "label": "Chemical"}, {"text": "heart disease", "id": "D006331", "label": "Disease"}] |
| `ontology_hypernym_identify` | LLM | **PASS** | 508 | ok | [{"head": "Aspirin", "tail": "heart disease", "hypernym": "Drug"}] |
| `ontology_mesh_lookup` | PGM | **PASS** | 46076 | ok | {"query": "aspirin", "matches": [{"mesh_id": "D001241", "label": "Aspirin", "resource": "http://id.nlm.nih.gov/mesh/D001241", "synonyms": ["2-(Acetyloxy)benzoic Acid", "Acetylsalicylic Acid", "Acid, Acetylsalicylic"], "hypernyms": [{"mes... |
| `ontology_synonym_extract` | LLM | **PASS** | 389 | ok | "{\"Aspirin\": [\"acetylsalicylic acid\"]}" |
| `ontology_synonym_resolve` | LLM | **PASS** | 80 | ok | "{\"Aspirin\": [\"acetylsalicylic acid\"]}" |
| `relation_dti_analyze` | LLM | **PASS** | 68 | ok | {"interaction": "inhibits", "confidence": "medium"} |
| `relation_extract_llm` | LLM | **PASS** | 67 | ok | ["Aspirin \| treats \| heart disease"] |
| `relation_extract_pubtator` | PGM | **PASS** | 58 | ok | ["Aspirin \| CID \| heart disease"] |
| `relation_from_tree_llm` | LLM | **PASS** | 545 | ok | [{"head": "Aspirin", "predicate": "treats", "tail": "heart disease"}] |
| `relation_result_to_id_pair` | PGM | **PASS** | 57 | ok | ["D001241 \| D006331"] |
| `relation_verify_llm` | LLM | **PASS** | 66 | ok | "$" |
| `relation_verify_to_pair` | PGM | **PASS** | 52 | ok | ["D001241", "D006331"] |
| `report_comparator` | LLM | **PASS** | 116 | ok | "## Comparison\n\nBaseline and candidate reports are similar." |
| `report_experiment` | LLM | **PASS** | 93 | ok | "## 1) Metrics\n\n\| Metric \| Value \|\n\| --- \| --- \|\n\| F1 \| 0.5 \|\n\n## 2) FN and FP Analysis\n\nSample FN noted.\n\n## 3) Agent Modification Suggestions\n\nTune relation_verify_llm prompt." |
| `report_experiment_tool` | LLM | **PASS** | 190 | ok | "## 1) Metrics\n\nF1=0.5\n\n## 2) FN and FP Analysis\n\nTool-assisted review complete.\n\n## 3) Agent Modification Suggestions\n\nNone." |
| `report_format_json` | PGM | **PASS** | 55 | ok | {"original": "Aspirin may reduce the risk of heart disease. Lithium carbonate toxicity was reported in a newborn infant.", "summary": "Aspirin may reduce heart disease risk.", "original_length": 106, "summary_length": 38} |
| `syntax_dep_parse` | LLM | **PASS** | 342 | ok | "1\tAspirin\taspirin\tNN\t_\t0\thead\t_\t_\t_\t_\n2\tmay\tmay\tMD\t_\t1\tadvmod\t_\t_\t_\t_\n" |
| `text_coreference` | LLM | **PASS** | 459 | ok | "Aspirin may reduce the risk of heart disease." |
| `text_sentence_split` | LLM | **PASS** | 68 | ok | ["Aspirin may reduce the risk of heart disease.", "Lithium carbonate toxicity was reported."] |
| `text_summarize` | LLM | **PASS** | 172 | ok | "Aspirin may reduce heart disease risk; lithium toxicity was reported." |
| `text_word_segment` | LLM | **PASS** | 463 | ok | "\| Aspirin \| may \| reduce \| the \| risk \| of \| heart \| disease \|" |
