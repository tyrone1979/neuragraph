# Agent Test Report

- Generated: 2026-06-02T00:49:32.927025+00:00
- Mock LLM: True
- Total: 42 | Passed: 34 | Failed: 8 | Skipped: 0

| Agent | Type | Status | ms | Message | Output preview |
| --- | --- | --- | ---: | --- | --- |
| `agent_refiner` | LLM | **PASS** | 4744 | ok | "{\"modifications\": []}" |
| `cid_pair_generate` | PGM | **PASS** | 124 | ok | [{"head": "Aspirin", "tail": "heart disease", "head_id": "D001241", "tail_id": "D006331"}, {"head": "Aspirin", "tail": "toxicity", "head_id": "D001241", "tail_id": "D064420"}, {"head": "Lithium carbonate", "tail": "heart disease", "head_... |
| `dataset_cid_tuning_build` | PGM | **FAIL** | 133 | error field: Execution error: maximum recursion depth exceeded while calling a Python object | null |
| `eval_flair` | PGM | **PASS** | 56 | ok | {"total_entities": 2, "label_count": 2, "per_label_entity_count": {"Chemical": 1, "Disease": 1}} |
| `eval_llm` | PGM | **PASS** | 57 | ok | {"total_entities": 2, "label_count": 2, "per_label_entity_count": {"Chemical": 1, "Disease": 1}} |
| `eval_metrics` | PGM | **PASS** | 151 | ok | {"precision": 1.0, "recall": 0.6666666666666666, "f1": 0.8, "tp": 2, "fp": 0, "fn": 1} |
| `eval_metrics_relation` | PGM | **FAIL** | 61 | error field: Execution error: Found empty input array (e.g., `y_true` or `y_pred`) while a minimum of 1 sample is required. | null |
| `eval_metrics_segment` | PGM | **PASS** | 64 | ok | {"metrics": {"precision": 1.0, "recall": 1.0, "f1": 1.0, "correct_boundaries": 3, "predicted_boundaries": 3, "real_boundaries": 3}, "error_analysis": {"over_segmentation": [], "under_segmentation": [], "boundary_shift": []}, "summary": {... |
| `eval_pair_generate` | PGM | **FAIL** | 59 | empty or invalid output for 'pairs' (list) | [] |
| `kg_rdf_export` | PGM | **PASS** | 47 | ok | {"@context": {"label": "http://schema.org/name"}, "nodes": [{"@id": "Aspirin", "label": "Aspirin"}, {"@id": "heart_disease", "label": "heart disease"}], "edges": [{"@id": "e0", "subject": "Aspirin", "predicate": "treats", "object": "hear... |
| `kg_triple_extract_llm` | LLM | **PASS** | 369 | ok | [{"head": "Aspirin", "predicate": "treats", "tail": "heart disease"}] |
| `kg_triple_merge` | PGM | **FAIL** | 79 | error field: Execution error: Import json not allowed | [] |
| `kg_triple_persist` | PGM | **PASS** | 64 | ok | [{"head": "Aspirin", "predicate": "treats", "tail": "heart disease"}] |
| `merge_metrics` | PGM | **FAIL** | 81 | metrics dict lacks precision/recall/f1 fields | {"flair_metrics": {"micro": {"precision": 0.8, "recall": 0.7, "f1": 0.75}}, "llm_metrics": {"micro": {"precision": 0.9, "recall": 0.6, "f1": 0.72}}} |
| `ner_comparison_report` | LLM | **PASS** | 72 | ok | "## NER Comparison\n\nFlair and LLM metrics are comparable on the sample." |
| `ner_flair_aggregate` | PGM | **PASS** | 63 | ok | {"Chemical": ["Aspirin"], "Disease": ["heart disease"]} |
| `ner_flair_doc` | PGM | **FAIL** | 75 | error field: Execution error: Import re not allowed | null |
| `ner_flair_sent` | PGM | **PASS** | 566 | ok | {"Chemical": ["Aspirin"], "Disease": ["heart disease"]} |
| `ner_from_tree_llm` | LLM | **PASS** | 58 | ok | {"Chemical": ["Aspirin"], "Disease": ["heart disease"]} |
| `ner_llm` | LLM | **PASS** | 67 | ok | {"Chemical": ["Aspirin"], "Disease": ["heart disease"]} |
| `ontology_entity_link` | LLM | **PASS** | 93 | ok | {"Aspirin": {"canonical": "Aspirin", "id": "D001241"}} |
| `ontology_hypernym_filter` | LLM | **PASS** | 124 | ok | [{"text": "Aspirin", "id": "D001241", "label": "Chemical"}, {"text": "heart disease", "id": "D006331", "label": "Disease"}] |
| `ontology_hypernym_identify` | LLM | **PASS** | 376 | ok | [{"head": "Aspirin", "tail": "heart disease", "hypernym": "Drug"}] |
| `ontology_mesh_lookup` | PGM | **PASS** | 48093 | ok | {"query": "aspirin", "matches": [{"mesh_id": "D001241", "label": "Aspirin", "resource": "http://id.nlm.nih.gov/mesh/D001241", "synonyms": ["2-(Acetyloxy)benzoic Acid", "Acetylsalicylic Acid", "Acid, Acetylsalicylic"], "hypernyms": [{"mes... |
| `ontology_synonym_extract` | LLM | **PASS** | 706 | ok | "{\"Aspirin\": [\"acetylsalicylic acid\"]}" |
| `ontology_synonym_resolve` | LLM | **PASS** | 120 | ok | "{\"Aspirin\": [\"acetylsalicylic acid\"]}" |
| `relation_dti_analyze` | LLM | **PASS** | 94 | ok | {"interaction": "inhibits", "confidence": "medium"} |
| `relation_extract_llm` | LLM | **PASS** | 77 | ok | ["Aspirin \| treats \| heart disease"] |
| `relation_extract_pubtator` | PGM | **FAIL** | 91 | error field: Execution error: maximum recursion depth exceeded while calling a Python object | [] |
| `relation_from_tree_llm` | LLM | **PASS** | 395 | ok | [{"head": "Aspirin", "predicate": "treats", "tail": "heart disease"}] |
| `relation_result_to_id_pair` | PGM | **FAIL** | 73 | empty or invalid output for 'relations' (list) | [] |
| `relation_verify_llm` | LLM | **PASS** | 71 | ok | "$" |
| `relation_verify_to_pair` | PGM | **PASS** | 82 | ok | ["D001241", "D006331"] |
| `report_comparator` | LLM | **PASS** | 138 | ok | "## Comparison\n\nBaseline and candidate reports are similar." |
| `report_experiment` | LLM | **PASS** | 83 | ok | "## 1) Metrics\n\n\| Metric \| Value \|\n\| --- \| --- \|\n\| F1 \| 0.5 \|\n\n## 2) FN and FP Analysis\n\nSample FN noted.\n\n## 3) Agent Modification Suggestions\n\nTune relation_verify_llm prompt." |
| `report_experiment_tool` | LLM | **PASS** | 149 | ok | "## 1) Metrics\n\nF1=0.5\n\n## 2) FN and FP Analysis\n\nTool-assisted review complete.\n\n## 3) Agent Modification Suggestions\n\nNone." |
| `report_format_json` | PGM | **PASS** | 81 | ok | {"original": "Aspirin may reduce the risk of heart disease. Lithium carbonate toxicity was reported in a newborn infant.", "summary": "Aspirin may reduce heart disease risk.", "original_length": 106, "summary_length": 38} |
| `syntax_dep_parse` | LLM | **PASS** | 424 | ok | "1\tAspirin\taspirin\tNN\t_\t0\thead\t_\t_\t_\t_\n2\tmay\tmay\tMD\t_\t1\tadvmod\t_\t_\t_\t_\n" |
| `text_coreference` | LLM | **PASS** | 733 | ok | "Aspirin may reduce the risk of heart disease." |
| `text_sentence_split` | LLM | **PASS** | 142 | ok | ["Aspirin may reduce the risk of heart disease.", "Lithium carbonate toxicity was reported."] |
| `text_summarize` | LLM | **PASS** | 131 | ok | "Aspirin may reduce heart disease risk; lithium toxicity was reported." |
| `text_word_segment` | LLM | **PASS** | 817 | ok | "\| Aspirin \| may \| reduce \| the \| risk \| of \| heart \| disease \|" |
