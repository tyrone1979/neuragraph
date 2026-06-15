# Agent Test Report

- Generated: 2026-06-15T00:04:52.358710+00:00
- Mock LLM: True (live = real deepseek / gpt-oss_120b only)
- Total: 67 | Passed: 64 | Failed: 3 | Skipped: 0

| Agent | Type | Status | ms | Message | Output preview |
| --- | --- | --- | ---: | --- | --- |
| `agent_refiner` | LLM | **PASS** | 2588 | ok | "{\"modifications\": []}" |
| `chemdisgene_answer_map` | PGM | **PASS** | 27 | ok | ["chem_disease:therapeutic"] |
| `chemdisgene_ner_parse` | PGM | **PASS** | 25 | ok | {"Chemical": ["Aspirin"], "Disease": ["heart disease"]} |
| `chemdisgene_pair_generate` | PGM | **PASS** | 27 | ok | [{"head": "Aspirin", "tail": "heart disease", "head_type": "Chemical", "tail_type": "Disease", "rel_template": "chem_disease:affects", "entity_type": "Chemical", "text": "Aspirin may reduce the risk of heart disease. Lithium carbonate to... |
| `chemdisgene_re_chem_disease_affects` | LLM | **PASS** | 32 | ok | "11" |
| `chemdisgene_re_chem_gene_activity` | LLM | **PASS** | 32 | ok | "11" |
| `chemdisgene_re_chem_gene_aff_bind` | LLM | **PASS** | 38 | ok | "11" |
| `chemdisgene_re_chem_gene_aff_expr` | LLM | **PASS** | 39 | ok | "11" |
| `chemdisgene_re_chem_gene_aff_local` | LLM | **PASS** | 42 | ok | "11" |
| `chemdisgene_re_chem_gene_dec_metab` | LLM | **PASS** | 33 | ok | "11" |
| `chemdisgene_re_chem_gene_expression` | LLM | **PASS** | 32 | ok | "11" |
| `chemdisgene_re_chem_gene_inc_activity` | LLM | **PASS** | 35 | ok | "11" |
| `chemdisgene_re_chem_gene_inc_metab` | LLM | **PASS** | 31 | ok | "11" |
| `chemdisgene_re_chem_gene_transport` | LLM | **PASS** | 34 | ok | "11" |
| `chemdisgene_re_gene_disease_marker` | LLM | **PASS** | 32 | ok | "11" |
| `chemdisgene_re_gene_disease_therapeutic` | LLM | **PASS** | 31 | ok | "11" |
| `chemdisgene_re_hypernyms` | LLM | **PASS** | 31 | ok | "11" |
| `chemdisgene_re_synonym` | LLM | **PASS** | 33 | ok | "11" |
| `chemdisgene_result_to_relation` | PGM | **PASS** | 27 | ok | ["Aspirin \| chem_disease:therapeutic \| heart disease"] |
| `cid_entities_dedupe_mesh` | PGM | **FAIL** | 27 | error field: Execution error: Import service.relation_normalize not allowed | [] |
| `cid_pair_generate` | PGM | **PASS** | 29 | ok | [{"head": "Aspirin", "tail": "heart disease", "head_id": "D001241", "tail_id": "D006331"}, {"head": "Aspirin", "tail": "toxicity", "head_id": "D001241", "tail_id": "D064420"}, {"head": "Lithium carbonate", "tail": "heart disease", "head_... |
| `dataset_chemdisgene_build` | PGM | **PASS** | 21 | ok | {"agent_id": "wf_chemdisgene_re_llm_linear", "output": "chemdisgene_agent_test.csv", "output_path": "tests/wf_chemdisgene_re_llm_linear/chemdisgene_agent_test.csv", "count": 1, "source": "data/raw/chemdisgene.txt"} |
| `dataset_cid_tuning_build` | PGM | **PASS** | 24 | ok | {"agent_id": "wf_cid_re_llm_linear", "tuning_output": "cid_agent_test_tuning.csv", "tuning_path": "tests/wf_cid_re_llm_linear/cid_agent_test_tuning.csv", "tuning_count": 2, "summary": {"picked": 2, "source": "comparison/data/CDR/dev.txt"}} |
| `e2e_entities_assign_group_ids` | PGM | **PASS** | 27 | ok | [{"text": "Aspirin", "id": "1", "label": "Chemical"}, {"text": "heart disease", "id": "1", "label": "Disease"}, {"text": "Lithium carbonate", "id": "2", "label": "Chemical"}, {"text": "toxicity", "id": "2", "label": "Disease"}] |
| `e2e_entities_dedup_by_id` | PGM | **PASS** | 24 | ok | [{"text": "Aspirin", "id": "D001241", "label": "Chemical"}, {"text": "heart disease", "id": "D006331", "label": "Disease"}, {"text": "Lithium carbonate", "id": "D016651", "label": "Chemical"}, {"text": "toxicity", "id": "D064420", "label... |
| `e2e_entities_passthrough` | PGM | **PASS** | 28 | ok | [{"text": "Aspirin", "id": "D001241", "label": "Chemical"}, {"text": "heart disease", "id": "D006331", "label": "Disease"}, {"text": "Lithium carbonate", "id": "D016651", "label": "Chemical"}, {"text": "toxicity", "id": "D064420", "label... |
| `e2e_entity_aliases_snapshot` | PGM | **PASS** | 32 | ok | [{"text": "Aspirin", "id": "D001241", "label": "Chemical"}, {"text": "heart disease", "id": "D006331", "label": "Disease"}, {"text": "Lithium carbonate", "id": "D016651", "label": "Chemical"}, {"text": "toxicity", "id": "D064420", "label... |
| `e2e_hypernym_filter` | LLM | **PASS** | 37 | ok | [{"text": "Aspirin", "id": "D001241", "label": "Chemical"}, {"text": "heart disease", "id": "D006331", "label": "Disease"}] |
| `e2e_synonym_filter` | LLM | **PASS** | 36 | ok | [{"text": "Aspirin", "id": "D001241", "label": "Chemical"}, {"text": "heart disease", "id": "D006331", "label": "Disease"}] |
| `eval_flair` | PGM | **PASS** | 41 | ok | {"total_entities": 2, "label_count": 2, "per_label_entity_count": {"Chemical": 1, "Disease": 1}} |
| `eval_llm` | PGM | **PASS** | 32 | ok | {"total_entities": 2, "label_count": 2, "per_label_entity_count": {"Chemical": 1, "Disease": 1}} |
| `eval_metrics` | PGM | **PASS** | 43 | ok | {"precision": 1.0, "recall": 0.6666666666666666, "f1": 0.8, "tp": 2, "fp": 0, "fn": 1} |
| `eval_metrics_relation` | PGM | **PASS** | 38 | ok | {"precision": 1.0, "recall": 0.5, "f1": 0.6666666666666666, "tp": 1, "fp": 0, "fn": 1} |
| `eval_metrics_segment` | PGM | **PASS** | 49 | ok | {"metrics": {"precision": 1.0, "recall": 1.0, "f1": 1.0, "correct_boundaries": 3, "predicted_boundaries": 3, "real_boundaries": 3}, "error_analysis": {"over_segmentation": [], "under_segmentation": [], "boundary_shift": []}, "summary": {... |
| `eval_pair_generate` | PGM | **PASS** | 37 | ok | [{"head": "Aspirin", "tail": "heart disease"}] |
| `kg_rdf_export` | PGM | **PASS** | 38 | ok | {"@context": {"label": "http://schema.org/name"}, "nodes": [{"@id": "Aspirin", "label": "Aspirin"}, {"@id": "heart_disease", "label": "heart disease"}], "edges": [{"@id": "e0", "subject": "Aspirin", "predicate": "treats", "object": "hear... |
| `kg_triple_extract_llm` | LLM | **FAIL** | 85 | triples list is empty | [] |
| `kg_triple_merge` | PGM | **PASS** | 31 | ok | [{"head": "D001241", "predicate": "treats", "tail": "D006331"}] |
| `kg_triple_persist` | PGM | **PASS** | 36 | ok | [{"head": "Aspirin", "predicate": "treats", "tail": "heart disease"}] |
| `llm_link_bulk_update` | PGM | **PASS** | 90 | ok | {"target_model": "deepseek", "source_model": null, "dry_run": true, "updated_count": 6, "skipped_count": 61, "updated": [{"agent_id": "kg_triple_extract_llm", "name": "Triple Extraction (LLM)", "old_model": "gpt-oss_120b", "new_model": "... |
| `merge_metrics` | PGM | **PASS** | 65 | ok | {"flair_metrics": {"micro": {"precision": 0.8, "recall": 0.7, "f1": 0.75}}, "llm_metrics": {"micro": {"precision": 0.9, "recall": 0.6, "f1": 0.72}}} |
| `ner_chemdisgene_llm` | LLM | **PASS** | 37 | ok | "Chemical\|Aspirin\nDisease\|heart disease\nGene\|PDE10A" |
| `ner_comparison_report` | LLM | **PASS** | 40 | ok | "## NER Comparison\n\nFlair and LLM metrics are comparable on the sample." |
| `ner_entities_to_re_format` | PGM | **PASS** | 34 | ok | [{"text": "Aspirin", "label": "Chemical", "id": ""}, {"text": "heart disease", "label": "Disease", "id": ""}] |
| `ner_flair_aggregate` | PGM | **PASS** | 35 | ok | {"Chemical": ["Aspirin"], "Disease": ["heart disease"]} |
| `ner_flair_doc` | PGM | **PASS** | 690 | ok | {"Chemical": ["Aspirin", "Lithium carbonate"], "Disease": ["heart disease"]} |
| `ner_flair_sent` | PGM | **PASS** | 234 | ok | {"Chemical": ["Aspirin"], "Disease": ["heart disease"]} |
| `ner_from_tree_llm` | LLM | **PASS** | 110 | ok | {"Chemical": ["Aspirin"], "Disease": ["heart disease"]} |
| `ner_llm` | LLM | **PASS** | 47 | ok | {"Chemical": ["Aspirin"], "Disease": ["heart disease"]} |
| `ontology_entity_link` | LLM | **PASS** | 101 | ok | {"Aspirin": {"canonical": "Aspirin", "id": "D001241"}} |
| `ontology_hypernym_filter` | LLM | **PASS** | 56 | ok | [{"text": "Aspirin", "id": "D001241", "label": "Chemical"}, {"text": "heart disease", "id": "D006331", "label": "Disease"}] |
| `ontology_synonym_resolve` | LLM | **FAIL** | 55 | synonyms missing pipe pairs (expected original\|is\|synonym) | "{\"Aspirin\": [\"acetylsalicylic acid\"]}" |
| `relation_extract_llm` | LLM | **PASS** | 338 | ok | ["Aspirin \| treats \| heart disease"] |
| `relation_extract_pubtator` | PGM | **PASS** | 32 | ok | ["Aspirin \| CID \| heart disease"] |
| `relation_from_tree_llm` | LLM | **PASS** | 75 | ok | ["Aspirin \| treats \| pain"] |
| `relation_result_to_id_pair` | PGM | **PASS** | 28 | ok | ["D001241 \| D006331"] |
| `relation_verify_llm` | LLM | **PASS** | 42 | ok | "$" |
| `relation_verify_to_pair` | PGM | **PASS** | 33 | ok | ["D001241", "D006331"] |
| `report_comparator` | LLM | **PASS** | 67 | ok | "## Comparison\n\nBaseline and candidate reports are similar." |
| `report_experiment` | LLM | **PASS** | 35 | ok | "## 1) Metrics\n\n\| Metric \| Value \|\n\| --- \| --- \|\n\| F1 \| 0.5 \|\n\n## 2) FN and FP Analysis\n\nSample FN noted.\n\n## 3) Agent Modification Suggestions\n\nTune relation_verify_llm prompt." |
| `report_experiment_tool` | LLM | **PASS** | 64 | ok | "## 1) Metrics\n\nF1=0.5\n\n## 2) FN and FP Analysis\n\nTool-assisted review complete.\n\n## 3) Agent Modification Suggestions\n\nNone." |
| `report_format_json` | PGM | **PASS** | 30 | ok | {"original": "Aspirin may reduce the risk of heart disease. Lithium carbonate toxicity was reported in a newborn infant.", "summary": "Aspirin may reduce heart disease risk.", "original_length": 106, "summary_length": 38} |
| `syntax_dep_parse` | LLM | **PASS** | 67 | ok | "1\tAspirin\taspirin\tNN\t_\t2\tnsubj\t_\t_\t_\t_\n2\ttreats\ttreat\tVBZ\t_\t0\troot\t_\t_\t_\t_\n3\tpain\tpain\tNN\t_\t2\tobj\t_\t_\t_\t_\n" |
| `text_coreference` | LLM | **PASS** | 81 | ok | "Aspirin may reduce the risk of heart disease." |
| `text_sentence_split` | LLM | **PASS** | 45 | ok | ["Aspirin may reduce the risk of heart disease.", "Lithium carbonate toxicity was reported."] |
| `text_summarize` | LLM | **PASS** | 50 | ok | "Aspirin may reduce heart disease risk; lithium toxicity was reported." |
| `text_word_segment` | LLM | **PASS** | 45 | ok | "\| Aspirin \| may \| reduce \| the \| risk \| of \| heart \| disease \|" |
