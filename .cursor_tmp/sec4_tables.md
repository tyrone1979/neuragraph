**Table S14. LLM agents (22)**

| ID | Name | Description |
|---|---|---|
| agent_refiner | Agent Refiner (LLM) | Generate actionable agent modifications from experiment diagnostics. |
| kg_triple_extract_llm | Triple Extraction (LLM) | Biomedical knowledge-graph triple extraction |
| ner_comparison_report | NER Comparison Report | Generates a comparison report between Flair and LLM NER results |
| ner_from_tree_llm | NER from Dependency Tree (LLM) | Extract entities from CoNLL-U dependency tree |
| ner_llm | NER (LLM, configurable types) | Extract biomedical named entities from text |
| ontology_entity_link | Entity Linking / Normalization (LLM) | Canonicalize entity mentions for knowledge-graph linking |
| ontology_hypernym_filter | Hypernym Filter (LLM) | Identify same-type hypernyms by MeSH id; drop hypernym rows from entity list |
| ontology_hypernym_identify | Hypernym Identification (LLM) | Identify the biomedical hypernym (super-class) from a given pair of entities based on explicit MeSH tree numbers or same-as links in the provided entity list. |
| ontology_synonym_extract | Synonym Extraction (LLM) | Biomedical abstract synonym extraction |
| ontology_synonym_resolve | Synonym Resolution (LLM) | Biomedical abstract synonym extraction (aligned with synonym_extraction) |
| relation_dti_analyze | Drug–Target Interaction Analysis (LLM) | — |
| relation_extract_llm | Relation Extraction (LLM) | Strict biomedical CID relation verifier for chemical–disease pairs |
| relation_from_tree_llm | Relation Extraction from Tree (LLM) | Extract [head entity, verb, tail entity] triples from CoNLL-U dependency tree |
| relation_verify_llm | Relation Verification (LLM) | Strict biomedical relation verifier based on triple list |
| report_comparator | Report Comparator (LLM) | Compare baseline vs candidate experiment outcomes and report quality. |
| report_experiment | Experiment Report (LLM) | Generate a structured experiment diagnosis report from full workflow artifacts. |
| report_experiment_tool | Experiment Report (LLM + Tools) | Generate a structured experiment diagnosis report from full workflow artifacts. |
| syntax_dep_parse | Dependency Parse (CoNLL-U) | English sentence to CoNLL-U dependency tree |
| text_coreference | Coreference Resolution (LLM) | Biomedical abstract coreference resolution |
| text_sentence_split | Sentence Split (LLM) | English sentence splitting for biomedical abstract |
| text_summarize | Text Summarization (LLM) | Summarize text into 2-3 sentences |
| text_word_segment | Word Segmentation (LLM) | English word segmentation |

**Table S15. PGM agents (21)**

| ID | Name | Description |
|---|---|---|
| cid_pair_generate | CID Pair Generator (PGM) | — |
| dataset_cid_tuning_build | CID Tuning Dataset Builder (PGM) | — |
| eval_flair | Auto FLAIR NER Metrics | — |
| eval_llm | Auto LLM NER Metrics | — |
| eval_metrics | Evaluation Metrics (PGM) | — |
| eval_metrics_relation | Relation Set Metrics (PGM) | — |
| eval_metrics_segment | Segmentation Metrics (PGM) | — |
| eval_pair_generate | Evaluation Pair Generator (PGM) | — |
| kg_rdf_export | RDF-JSON Export (PGM) | — |
| kg_triple_merge | Triple Merge (PGM) | — |
| kg_triple_persist | Triple CSV Persistence (PGM) | — |
| llm_link_bulk_update | Bulk LLM Link Update (PGM) | — |
| merge_metrics | Merge Flair and LLM Metrics | — |
| ner_flair_aggregate | Flair NER Aggregator | — |
| ner_flair_doc | NER (Flair, document) | — |
| ner_flair_sent | NER (Flair, sentence) | — |
| ontology_mesh_lookup | MeSH Synonym/Hypernym Lookup (PGM) | — |
| relation_extract_pubtator | Relation Extraction (PubTator) | — |
| relation_result_to_id_pair | Relation Result -> ID Pair | — |
| relation_verify_to_pair | Relation Verify → Entity Pair | — |
| report_format_json | Result Formatter (PGM) | — |

**Table S16. Reusable subgraphs (7)**

| ID | Name | Description |
|---|---|---|
| sg_cid_re_verify | CID RE verify pair | Verify one Chemical–Disease pair; output id / id if induce ($). |
| sg_ner_flair_sent | Sentence Flair NER | Run ner_flair_sent on one sentence (loop body). |
| sg_ner_llm_tree | Tree-based LLM NER | syntax_dep_parse → ner_from_tree_llm per sentence. |
| sg_preprocess_inner | Inner preprocess loop body | Format / pass-through inner loop step. |
| sg_re_preprocess | RE preprocess + NER | Nested inner loop then ner_llm (outer loop body for doc RE). |
| sg_re_tree | Tree-based RE | syntax_dep_parse → relation_from_tree_llm per sentence. |
| sg_relation_verify | Relation verify pair | relation_verify_llm → relation_verify_to_pair for one head/tail pair. |

**Table S17. Reference workflows (17)**

| ID | Name | Description |
|---|---|---|
| wf_cid_ner_llm_eval | CID NER Eval (LLM) | Chemical/Disease NER with LLM and generic metrics. |
| wf_cid_re_branch | CID RE (multi-branch gate) | NER then 4-way branch gate before relation extraction. |
| wf_cid_re_llm_linear | CID RE Pipeline (linear) | Gold entities → hypernym filter → pair list → foreach RE verify → id pairs. |
| wf_doc_ner_flair_eval | Doc NER Eval (Flair) | Document Flair NER with metrics (replaces bio_ner_graph). |
| wf_doc_ner_flair_sent_eval | Doc NER Eval (Flair, sentence) | Sentence split → loop HunFlair2 per sentence → entity metrics (Table S2 / Fig. S2). |
| wf_doc_ner_llm_eval | Doc NER Eval (LLM) | Split document then LLM NER with metrics. |
| wf_doc_ner_loop_branch | Doc NER loop + branch | Sentence split → loop Flair NER → 4-way branch → optional LLM → metrics. |
| wf_doc_re_nested_branch | Doc RE (nested loop + branch) | Outer loop with nested preprocess + NER, 4-way branch, then RE. |
| wf_flair_vs_llm_ner | Flair vs LLM NER Comparison | Workflow for Flair vs LLM NER Comparison |
| wf_general_report_linear | Summarize + format | Summarize text and pack into JSON result. |
| wf_kg_flair_full | KG Build (Flair NER) | Flair doc NER → entity link → triple extract → merge → RDF. |
| wf_kg_llm_full | KG Build (LLM NER) | LLM NER → entity link → RE → triple merge → RDF export. |
| wf_kg_syntax_loop | KG from syntax (sentence loop) | Coreference → split → loop tree-RE subgraph → CSV persist. |
| wf_re_pubtator_dev10 | PubTator RE Dev (10) | BC5CDR dev.txt (10 articles): gold entities → PubTator3 relation extraction → relation pair metrics vs gold_relations. |
| wf_re_pubtator_eval | PubTator RE Eval | Gold entities → PubTator relation extraction → relation pair metrics. |
| wf_re_verify_llm_loop | RE Verify (pair loop) | Generate evaluation pairs → loop verify subgraph → metrics. |
| wf_word_seg_llm_eval | Word Segmentation Eval | LLM word segmentation with boundary metrics. |

**Table S18. Callable tools (12)**

| ID | Name | Description |
|---|---|---|
| agent_change_impact_trace | Agent Change Impact Trace | Estimate per-agent metric contribution from version_map and two experiment states. |
| agent_version_guard | Agent Version Guard | Policy-based guard for keep/alert/rollback decisions using metric deltas. |
| dataset_cid_tuning_build | CID Tuning Dataset Builder | Build a stratified CID tuning CSV (and optional test-remain set) from PubTator gold dev.txt. |
| dataset_sampler_stratified | Dataset Sampler Stratified | Stratified sample by text length, entity density, and relation density for quick A/B validation. |
| error_case_exporter | Error Case Exporter | Export worst-k error cases from states into markdown and jsonl payloads for review/regression. |
| fn_fp_bucket_analyzer | FN FP Bucket Analyzer | Bucket FN/FP into boundary/type/relation/missed-recall style categories with examples. |
| merge_heads_tails_to_entities | Merge Heads & Tails to Entities | Merge two lists of head/tail entities into a unified 'text,type,mesh' string format, one entity per line. |
| metrics_delta_compare | Metrics Delta Compare | Compare baseline and candidate states, return precision/recall/f1 deltas and significantly degraded samples. |
| prompt_patch_apply_safe | Prompt Patch Apply Safe | Apply structured prompt patch (append/replace) with validation and safety checks. |
| report_quality_scorer | Report Quality Scorer | Score report quality on evidence, executability, and traceability. |
| tool_ner_flair | NER by Flair | Input a sentence string, and label string like "Chemical,Disease", the tool will do NER task and return a dict like  {"Chemical":["a","b"], "Disease":["c","d"] } |
| tool_pubtator_relation_extract | PubTator Relation Extract | Call NCBI PubTator3 API (https://www.ncbi.nlm.nih.gov/research/pubtator3-api) to extract chemical–disease relations from a PubMed PMID or text. Returns relations as head / CID / tail lines. |