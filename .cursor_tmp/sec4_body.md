### 4.1 Agents (43)

**Table S14. LLM agents (22)**

| No. | ID | Name | Description |
|---:|---|---|---|
| 1 | `agent_refiner` | Agent Refiner (LLM) | Generate actionable agent modifications from experiment diagnostics. |
| 2 | `kg_triple_extract_llm` | Triple Extraction (LLM) | Biomedical knowledge-graph triple extraction |
| 3 | `ner_comparison_report` | NER Comparison Report | Generates a comparison report between Flair and LLM NER results |
| 4 | `ner_from_tree_llm` | NER from Dependency Tree (LLM) | Extract entities from CoNLL-U dependency tree |
| 5 | `ner_llm` | NER (LLM, configurable types) | Extract biomedical named entities from text |
| 6 | `ontology_entity_link` | Entity Linking / Normalization (LLM) | Canonicalize entity mentions for knowledge-graph linking |
| 7 | `ontology_hypernym_filter` | Hypernym Filter (LLM) | Identify same-type hypernyms by MeSH id; drop hypernym rows from entity list |
| 8 | `ontology_hypernym_identify` | Hypernym Identification (LLM) | Identify the biomedical hypernym (super-class) from a given pair of entities based on explicit MeSH tree numbers or same-as links in the provided entity list. |
| 9 | `ontology_synonym_extract` | Synonym Extraction (LLM) | Biomedical abstract synonym extraction |
| 10 | `ontology_synonym_resolve` | Synonym Resolution (LLM) | Biomedical abstract synonym extraction (aligned with synonym_extraction) |
| 11 | `relation_dti_analyze` | Drug–Target Interaction Analysis (LLM) | Analyze drug–target interactions from drug chemistry and target protein inputs; return a structured dict (mechanism, affinity, binding mode, assessment, confidence). |
| 12 | `relation_extract_llm` | Relation Extraction (LLM) | Strict biomedical CID relation verifier for chemical–disease pairs |
| 13 | `relation_from_tree_llm` | Relation Extraction from Tree (LLM) | Extract [head entity, verb, tail entity] triples from CoNLL-U dependency tree |
| 14 | `relation_verify_llm` | Relation Verification (LLM) | Strict biomedical relation verifier based on triple list |
| 15 | `report_comparator` | Report Comparator (LLM) | Compare baseline vs candidate experiment outcomes and report quality. |
| 16 | `report_experiment` | Experiment Report (LLM) | Generate a structured experiment diagnosis report from full workflow artifacts. |
| 17 | `report_experiment_tool` | Experiment Report (LLM + Tools) | Generate a structured experiment diagnosis report from full workflow artifacts. |
| 18 | `syntax_dep_parse` | Dependency Parse (CoNLL-U) | English sentence to CoNLL-U dependency tree |
| 19 | `text_coreference` | Coreference Resolution (LLM) | Biomedical abstract coreference resolution |
| 20 | `text_sentence_split` | Sentence Split (LLM) | English sentence splitting for biomedical abstract |
| 21 | `text_summarize` | Text Summarization (LLM) | Summarize text into 2-3 sentences |
| 22 | `text_word_segment` | Word Segmentation (LLM) | English word segmentation |

**Table S15. PGM agents (21)**

| No. | ID | Name | Description |
|---:|---|---|---|
| 1 | `cid_pair_generate` | CID Pair Generator (PGM) | Builds chemical–disease head/tail text pairs with MeSH IDs from filtered Chemical and Disease entities. |
| 2 | `dataset_cid_tuning_build` | CID Tuning Dataset Builder (PGM) | Builds CID relation tuning and test splits from a PubTator source file via the CidDatasetBuilder plugin. |
| 3 | `eval_flair` | Auto FLAIR NER Metrics | Counts unique FLAIR NER entities per label and returns total and per-label entity counts. |
| 4 | `eval_llm` | Auto LLM NER Metrics | Counts unique LLM NER entities per label and returns total and per-label entity counts. |
| 5 | `eval_metrics` | Evaluation Metrics (PGM) | Computes NER precision, recall, and F1 by comparing predicted and expected entity sets via MetricsCalculation. |
| 6 | `eval_metrics_relation` | Relation Set Metrics (PGM) | Evaluates chemical–induced-disease relation sets by normalizing and comparing predicted relations to ground truth. |
| 7 | `eval_metrics_segment` | Segmentation Metrics (PGM) | Scores pipe-delimited word segmentation by boundary precision, recall, F1, and segmentation error analysis. |
| 8 | `eval_pair_generate` | Evaluation Pair Generator (PGM) | Generates all chemical–disease evaluation pairs from expected Chemical and Disease entity lists. |
| 9 | `kg_rdf_export` | RDF-JSON Export (PGM) | Exports knowledge-graph triples to RDF-JSON with node labels and subject–predicate–object edges. |
| 10 | `kg_triple_merge` | Triple Merge (PGM) | Merges pipe-delimited relations with entity-link canonicalization and deduplicates head–predicate–tail triples. |
| 11 | `kg_triple_persist` | Triple CSV Persistence (PGM) | Persists merged knowledge-graph triples to CSV under result with head, verb, and tail columns. |
| 12 | `llm_link_bulk_update` | Bulk LLM Link Update (PGM) | Bulk-updates LLM connector links on selected agents from a source model to a target, optionally dry-run. |
| 13 | `merge_metrics` | Merge Flair and LLM Metrics | Combines FLAIR and LLM NER metric dictionaries into a single merged_metrics report object. |
| 14 | `ner_flair_aggregate` | Flair NER Aggregator | Aggregates per-sentence FLAIR NER outputs into document-level label-to-unique-entity-text dictionaries. |
| 15 | `ner_flair_doc` | NER (Flair, document) | Runs HunFlair2 NER on a document split into sentences and returns deduplicated entities per label. |
| 16 | `ner_flair_sent` | NER (Flair, sentence) | Tags one sentence with HunFlair2 NER and returns predicted entity texts grouped by label. |
| 17 | `ontology_mesh_lookup` | MeSH Synonym/Hypernym Lookup (PGM) | Looks up MeSH descriptors for a query and returns mesh IDs, synonyms, and hypernyms per match. |
| 18 | `relation_extract_pubtator` | Relation Extraction (PubTator) | Extracts chemical–disease relations from text or PMID using PubTator3 and local entity annotations. |
| 19 | `relation_result_to_id_pair` | Relation Result -> ID Pair | Emits head_id/tail_id CID relation lines when verification is positive, with negation and weak-association guards. |
| 20 | `relation_verify_to_pair` | Relation Verify → Entity Pair | Maps a positive relation verification to canonical head and tail entity IDs from entity_link. |
| 21 | `report_format_json` | Result Formatter (PGM) | Formats original text and summary into JSON with character lengths for reporting pipelines. |

### 4.2 Reusable subgraphs (7)

**Table S16. Reusable subgraphs (7)**

| No. | ID | Name | Description |
|---:|---|---|---|
| 1 | `sg_cid_re_verify` | CID RE verify pair | Verify one Chemical–Disease pair; output MeSH id pair when verdict is induces. |
| 2 | `sg_ner_flair_sent` | Sentence Flair NER | Run ner_flair_sent on one sentence (loop body). |
| 3 | `sg_ner_llm_tree` | Tree-based LLM NER | syntax_dep_parse → ner_from_tree_llm per sentence. |
| 4 | `sg_preprocess_inner` | Inner preprocess loop body | Format / pass-through inner loop step. |
| 5 | `sg_re_preprocess` | RE preprocess + NER | Nested inner loop then ner_llm (outer loop body for doc RE). |
| 6 | `sg_re_tree` | Tree-based RE | syntax_dep_parse → relation_from_tree_llm per sentence. |
| 7 | `sg_relation_verify` | Relation verify pair | relation_verify_llm → relation_verify_to_pair for one head/tail pair. |

### 4.3 Reference workflows (17)

**Table S17. Reference workflows (17)**

| No. | ID | Name | Description |
|---:|---|---|---|
| 1 | `wf_cid_ner_llm_eval` | CID NER Eval (LLM) | Chemical/Disease NER with LLM and generic metrics. |
| 2 | `wf_cid_re_branch` | CID RE (multi-branch gate) | NER then 4-way branch gate before relation extraction. |
| 3 | `wf_cid_re_llm_linear` | CID RE Pipeline (linear) | Gold entities → hypernym filter → pair list → foreach RE verify → id pairs. |
| 4 | `wf_doc_ner_flair_eval` | Doc NER Eval (Flair) | Document Flair NER with metrics (replaces bio_ner_graph). |
| 5 | `wf_doc_ner_flair_sent_eval` | Doc NER Eval (Flair, sentence) | Sentence split → loop HunFlair2 per sentence → entity metrics (Table S2 / Fig. S2). |
| 6 | `wf_doc_ner_llm_eval` | Doc NER Eval (LLM) | Split document then LLM NER with metrics. |
| 7 | `wf_doc_ner_loop_branch` | Doc NER loop + branch | Sentence split → loop Flair NER → 4-way branch → optional LLM → metrics. |
| 8 | `wf_doc_re_nested_branch` | Doc RE (nested loop + branch) | Outer loop with nested preprocess + NER, 4-way branch, then RE. |
| 9 | `wf_flair_vs_llm_ner` | Flair vs LLM NER Comparison | Sentence split, Flair loop NER, LLM NER, per-path metrics, and ner_comparison_report on the same document. |
| 10 | `wf_general_report_linear` | Summarize + format | Summarize text and pack into JSON result. |
| 11 | `wf_kg_flair_full` | KG Build (Flair NER) | Flair doc NER → entity link → triple extract → merge → RDF. |
| 12 | `wf_kg_llm_full` | KG Build (LLM NER) | LLM NER → entity link → RE → triple merge → RDF export. |
| 13 | `wf_kg_syntax_loop` | KG from syntax (sentence loop) | Coreference → split → loop tree-RE subgraph → CSV persist. |
| 14 | `wf_re_pubtator_dev10` | PubTator RE Dev (10) | BC5CDR dev.txt (10 articles): gold entities → PubTator3 relation extraction → relation pair metrics vs gold_relations. |
| 15 | `wf_re_pubtator_eval` | PubTator RE Eval | Gold entities → PubTator relation extraction → relation pair metrics. |
| 16 | `wf_re_verify_llm_loop` | RE Verify (pair loop) | Generate evaluation pairs → loop verify subgraph → metrics. |
| 17 | `wf_word_seg_llm_eval` | Word Segmentation Eval | LLM word segmentation with boundary metrics. |

### 4.4 Callable tools (12)

**Table S18. Callable tools (12)**

| No. | ID | Name | Description |
|---:|---|---|---|
| 1 | `agent_change_impact_trace` | Agent Change Impact Trace | Estimate per-agent metric contribution from version_map and two experiment states. |
| 2 | `agent_version_guard` | Agent Version Guard | Policy-based guard for keep/alert/rollback decisions using metric deltas. |
| 3 | `dataset_cid_tuning_build` | CID Tuning Dataset Builder | Build a stratified CID tuning CSV (and optional test-remain set) from PubTator gold dev.txt. |
| 4 | `dataset_sampler_stratified` | Dataset Sampler Stratified | Stratified sample by text length, entity density, and relation density for quick A/B validation. |
| 5 | `error_case_exporter` | Error Case Exporter | Export worst-k error cases from states into markdown and jsonl payloads for review/regression. |
| 6 | `fn_fp_bucket_analyzer` | FN FP Bucket Analyzer | Bucket FN/FP into boundary/type/relation/missed-recall style categories with examples. |
| 7 | `merge_heads_tails_to_entities` | Merge Heads & Tails to Entities | Merge two lists of head/tail entities into a unified 'text,type,mesh' string format, one entity per line. |
| 8 | `metrics_delta_compare` | Metrics Delta Compare | Compare baseline and candidate states, return precision/recall/f1 deltas and significantly degraded samples. |
| 9 | `prompt_patch_apply_safe` | Prompt Patch Apply Safe | Apply structured prompt patch (append/replace) with validation and safety checks. |
| 10 | `report_quality_scorer` | Report Quality Scorer | Score report quality on evidence, executability, and traceability. |
| 11 | `tool_ner_flair` | NER by Flair | Input a sentence string, and label string like "Chemical,Disease", the tool will do NER task and return a dict like  {"Chemical":["a","b"], "Disease":["c","d"] } |
| 12 | `tool_pubtator_relation_extract` | PubTator Relation Extract | Call NCBI PubTator3 API (https://www.ncbi.nlm.nih.gov/research/pubtator3-api) to extract chemical–disease relations from a PubMed PMID or text. Returns relations as head / CID / tail lines. |

### 4.5 Native dataset parsers

**Table S19. Native dataset parsers (3)**

| No. | ID | Name | Description |
|---:|---|---|---|
| 1 | `parser_cdr` | CDR (PubTator) | Load BioCreative V CDR PubTator .txt articles with gold entities and CID relations (CIDParser). |
| 2 | `parser_chemdisgene` | ChemDisGene | Load ChemDisGene article .txt files with companion .tsv annotation trees (ChemDisGeneParser). |
| 3 | `parser_plain_text` | Plain text (raw upload) | Load user-uploaded plain-text .txt from data/raw for batch runs without bundled gold files. |

Built-in loaders are selected automatically from dataset folder layout (`data/data_load.py`: PubTator .txt, ChemDisGene .tsv trees, or `data/raw` uploads).