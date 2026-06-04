# Agent Test Report

- Generated: 2026-06-02T03:20:45.409064+00:00
- Mock LLM: False (live = real deepseek / gpt-oss_120b only)
- Total: 43 | Passed: 40 | Failed: 3 | Skipped: 0

| Agent | Type | Status | ms | Message | Output preview |
| --- | --- | --- | ---: | --- | --- |
| `agent_refiner` | LLM | **FAIL** | 8357 | plan_json is not valid JSON: Expecting value: line 1 column 1 (char 0) | "The input package contains only a single LLM agent (`relation_verify_llm`) with a baseline micro_f1 of 0.5 and no candidate states, no FN/FP samples, no report text, and no degradation evidence. There is no actionable FN/FP evidence, no... |
| `cid_pair_generate` | PGM | **PASS** | 34 | ok | [{"head": "Aspirin", "tail": "heart disease", "head_id": "D001241", "tail_id": "D006331"}, {"head": "Aspirin", "tail": "toxicity", "head_id": "D001241", "tail_id": "D064420"}, {"head": "Lithium carbonate", "tail": "heart disease", "head_... |
| `dataset_cid_tuning_build` | PGM | **PASS** | 44 | ok | {"runner_id": "wf_cid_re_llm_linear", "tuning_output": "cid_agent_test_tuning.csv", "tuning_path": "tests/wf_cid_re_llm_linear/cid_agent_test_tuning.csv", "tuning_count": 2, "summary": {"picked": 2, "source": "comparison/data/CDR/dev.txt"}} |
| `eval_flair` | PGM | **PASS** | 37 | ok | {"total_entities": 2, "label_count": 2, "per_label_entity_count": {"Chemical": 1, "Disease": 1}} |
| `eval_llm` | PGM | **PASS** | 50 | ok | {"total_entities": 2, "label_count": 2, "per_label_entity_count": {"Chemical": 1, "Disease": 1}} |
| `eval_metrics` | PGM | **PASS** | 41 | ok | {"precision": 1.0, "recall": 0.6666666666666666, "f1": 0.8, "tp": 2, "fp": 0, "fn": 1} |
| `eval_metrics_relation` | PGM | **PASS** | 50 | ok | {"precision": 1.0, "recall": 0.5, "f1": 0.6666666666666666, "tp": 1, "fp": 0, "fn": 1} |
| `eval_metrics_segment` | PGM | **PASS** | 56 | ok | {"metrics": {"precision": 1.0, "recall": 1.0, "f1": 1.0, "correct_boundaries": 3, "predicted_boundaries": 3, "real_boundaries": 3}, "error_analysis": {"over_segmentation": [], "under_segmentation": [], "boundary_shift": []}, "summary": {... |
| `eval_pair_generate` | PGM | **PASS** | 37 | ok | [{"head": "Aspirin", "tail": "heart disease"}] |
| `kg_rdf_export` | PGM | **PASS** | 45 | ok | {"@context": {"label": "http://schema.org/name"}, "nodes": [{"@id": "Aspirin", "label": "Aspirin"}, {"@id": "heart_disease", "label": "heart disease"}], "edges": [{"@id": "e0", "subject": "Aspirin", "predicate": "treats", "object": "hear... |
| `kg_triple_extract_llm` | LLM | **PASS** | 25105 | ok (live:gpt-oss_120b) | ["Aspirin \| reduces_risk_of \| heart disease"] |
| `kg_triple_merge` | PGM | **PASS** | 30 | ok | [{"head": "D001241", "predicate": "treats", "tail": "D006331"}] |
| `kg_triple_persist` | PGM | **PASS** | 31 | ok | [{"head": "Aspirin", "predicate": "treats", "tail": "heart disease"}] |
| `llm_link_bulk_update` | PGM | **PASS** | 71 | ok | {"target_model": "deepseek", "source_model": null, "dry_run": true, "updated_count": 8, "skipped_count": 35, "updated": [{"agent_id": "kg_triple_extract_llm", "name": "Triple Extraction (LLM)", "old_model": "gpt-oss_120b", "new_model": "... |
| `merge_metrics` | PGM | **PASS** | 36 | ok | {"flair_metrics": {"micro": {"precision": 0.8, "recall": 0.7, "f1": 0.75}}, "llm_metrics": {"micro": {"precision": 0.9, "recall": 0.6, "f1": 0.72}}} |
| `ner_comparison_report` | LLM | **PASS** | 11466 | ok (live:deepseek) | "Here is a comprehensive comparison report of the NER performance between Flair and the LLM on the provided text.\n\n---\n\n### NER Performance Comparison Report: Flair vs. LLM\n\n**Text Analyzed:**\n> *Aspirin may reduce the risk of hea... |
| `ner_flair_aggregate` | PGM | **PASS** | 29 | ok | {"Chemical": ["Aspirin"], "Disease": ["heart disease"]} |
| `ner_flair_doc` | PGM | **PASS** | 548 | ok | {"Chemical": ["Aspirin", "Lithium carbonate"], "Disease": ["heart disease"]} |
| `ner_flair_sent` | PGM | **PASS** | 209 | ok | {"Chemical": ["Aspirin"], "Disease": ["heart disease"]} |
| `ner_from_tree_llm` | LLM | **PASS** | 2919 | ok (live:gpt-oss_120b) | {"Chemical": ["Aspirin"], "Disease": []} |
| `ner_llm` | LLM | **PASS** | 804 | ok (live:deepseek) | {"Disease": ["heart disease"], "Chemical": ["Aspirin"]} |
| `ontology_entity_link` | LLM | **PASS** | 3407 | ok (live:gpt-oss_120b) | {"Aspirin": {"canonical": "aspirin", "type": "Chemical"}, "heart disease": {"canonical": "heart disease", "type": "Disease"}} |
| `ontology_hypernym_filter` | LLM | **PASS** | 1208 | ok (live:deepseek) | [{"text": "Aspirin", "id": "D001241", "label": "Chemical"}, {"text": "heart disease", "id": "D006331", "label": "Disease"}, {"text": "Lithium carbonate", "id": "D016651", "label": "Chemical"}, {"text": "toxicity", "id": "D064420", "label... |
| `ontology_hypernym_identify` | LLM | **PASS** | 4417 | ok (live:gpt-oss_120b) | [] |
| `ontology_mesh_lookup` | PGM | **PASS** | 42797 | ok | {"query": "aspirin", "matches": [{"mesh_id": "D001241", "label": "Aspirin", "resource": "http://id.nlm.nih.gov/mesh/D001241", "synonyms": ["2-(Acetyloxy)benzoic Acid", "Acetylsalicylic Acid", "Acid, Acetylsalicylic"], "hypernyms": [{"mes... |
| `ontology_synonym_extract` | LLM | **FAIL** | 4956 | empty or invalid output for 'synonyms' (str) | "" |
| `ontology_synonym_resolve` | LLM | **PASS** | 1013 | ok (live:deepseek) | "Aspirin\|is\|Aspirin" |
| `relation_dti_analyze` | LLM | **PASS** | 7532 | ok (live:deepseek) | {"mechanism": {"type": "competitive inhibition", "reasoning": "Aspirin (acetylsalicylic acid) is a non-selective NSAID that irreversibly acetylates a serine residue (Ser530 in COX-2) in the cyclooxygenase active site, blocking the access... |
| `relation_extract_llm` | LLM | **PASS** | 661 | ok (live:deepseek) | ["Aspirin \| CID \| heart disease"] |
| `relation_extract_pubtator` | PGM | **PASS** | 31 | ok | ["Aspirin \| CID \| heart disease"] |
| `relation_from_tree_llm` | LLM | **FAIL** | 5340 | empty or invalid output for 'triples' (list) | [] |
| `relation_result_to_id_pair` | PGM | **PASS** | 27 | ok | ["D001241 \| D006331"] |
| `relation_verify_llm` | LLM | **PASS** | 706 | ok (live:deepseek) | "~" |
| `relation_verify_to_pair` | PGM | **PASS** | 26 | ok | ["D001241", "D006331"] |
| `report_comparator` | LLM | **PASS** | 10615 | ok (live:deepseek) | "Here is the review based on the provided input:\n\n---\n\n## Experiment Review: `test-exp` (Runner: `wf_cid_re_llm_linear`)\n\n### 1) Metrics Delta\n\n\| Metric \| Baseline \| Candidate \| Delta \|\n\|--------\|----------\|-----------\|-------\|\... |
| `report_experiment` | LLM | **PASS** | 6935 | ok (live:deepseek) | "## 1) Metrics\n\n**Overall Metrics**\n\n\| Metric \| Value \|\n\|--------\|-------\|\n\| Micro F1 \| 0.50 \|\n\n**Agent Version Mapping**\n\n\| Agent ID \| Version Used \|\n\|----------\|--------------\|\n\| relation_verify_llm \| current \|\n\n*Note: No... |
| `report_experiment_tool` | LLM | **PASS** | 10527 | ok (live:deepseek) | "## 1) Metrics\n\n\| Metric \| Value \|\n\|--------\|-------\|\n\| Micro F1 \| 0.50 \|\n\n\| graph_id \| agent_id \| version_used \|\n\|----------\|----------\|--------------\|\n\| (not provided) \| relation_verify_llm \| current \|\n\n**Note:** The experime... |
| `report_format_json` | PGM | **PASS** | 33 | ok | {"original": "Aspirin may reduce the risk of heart disease. Lithium carbonate toxicity was reported in a newborn infant.", "summary": "Aspirin may reduce heart disease risk.", "original_length": 106, "summary_length": 38} |
| `syntax_dep_parse` | LLM | **PASS** | 14814 | ok (live:gpt-oss_120b) | "1\tAspirin\tAspirin\tPROPN\t_\tNumber=Sing\t3\tnsubj\t_\t_\n2\tmay\tmay\tAUX\t_\tMood=Ind\|Tense=Pres\|VerbForm=Fin\t3\taux\t_\t_\n3\treduce\treduce\tVERB\t_\tVerbForm=Inf\t0\troot\t_\t_\n4\tthe\tthe\tDET\t_\tDefinite=Def\|PronType=Art\t5\... |
| `text_coreference` | LLM | **PASS** | 4170 | ok (live:gpt-oss_120b) | "Aspirin may reduce the risk of heart disease. Lithium carbonate toxicity was reported in a newborn infant." |
| `text_sentence_split` | LLM | **PASS** | 1072 | ok (live:deepseek) | ["Aspirin may reduce the risk of heart disease.", "Lithium carbonate toxicity was reported in a newborn infant."] |
| `text_summarize` | LLM | **PASS** | 1115 | ok (live:deepseek) | "Aspirin may help lower the risk of heart disease, while lithium carbonate toxicity has been reported in a newborn infant." |
| `text_word_segment` | LLM | **PASS** | 974 | ok (live:deepseek) | "Aspirin \| may \| reduce \| heart \| disease \| risk \| ." |
