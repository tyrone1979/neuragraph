# Meta inventory (agents & graphs)

Generated: 2026-06-15 00:08 UTC via `scripts/gen_meta_inventory.py`.

- **Agents:** 67 (36 LLM, 31 PGM)
- **Graphs:** 33 (10 subgraphs, 23 workflows)
- **Agent test data:** `tests/<agent_id>/sample.csv` (1 row each; see `ui_tests/utils/agent_sample_row_fixtures.py`)

## Agents

### LLM agents (36)

| No. | ID | Type | Name | Description |
| ---: | --- | --- | --- | --- |
| 1 | `agent_refiner` | LLM | Agent Refiner (LLM) |  |
| 2 | `chemdisgene_re_chem_disease_affects` | LLM | ChemDisGene RE chem_disease:affects |  |
| 3 | `chemdisgene_re_chem_gene_activity` | LLM | ChemDisGene RE chem_gene:activity |  |
| 4 | `chemdisgene_re_chem_gene_aff_bind` | LLM | ChemDisGene RE chem_gene:affects^binding |  |
| 5 | `chemdisgene_re_chem_gene_aff_expr` | LLM | ChemDisGene RE chem_gene:affects^expression |  |
| 6 | `chemdisgene_re_chem_gene_aff_local` | LLM | ChemDisGene RE chem_gene:affects^localization |  |
| 7 | `chemdisgene_re_chem_gene_dec_metab` | LLM | ChemDisGene RE chem_gene:decreases^metabolic_processing |  |
| 8 | `chemdisgene_re_chem_gene_expression` | LLM | ChemDisGene RE chem_gene:expression |  |
| 9 | `chemdisgene_re_chem_gene_inc_activity` | LLM | ChemDisGene RE chem_gene:increases^activity |  |
| 10 | `chemdisgene_re_chem_gene_inc_metab` | LLM | ChemDisGene RE chem_gene:increases^metabolic_processing |  |
| 11 | `chemdisgene_re_chem_gene_transport` | LLM | ChemDisGene RE chem_gene:transport |  |
| 12 | `chemdisgene_re_gene_disease_marker` | LLM | ChemDisGene RE gene_disease:marker/mechanism |  |
| 13 | `chemdisgene_re_gene_disease_therapeutic` | LLM | ChemDisGene RE gene_disease:therapeutic |  |
| 14 | `chemdisgene_re_hypernyms` | LLM | ChemDisGene RE hypernyms |  |
| 15 | `chemdisgene_re_synonym` | LLM | ChemDisGene RE synonym |  |
| 16 | `e2e_hypernym_filter` | LLM | E2E Hypernym Filter (LLM) |  |
| 17 | `e2e_synonym_filter` | LLM | E2E Synonym Filter (LLM) |  |
| 18 | `kg_triple_extract_llm` | LLM | Triple Extraction (LLM) |  |
| 19 | `ner_chemdisgene_llm` | LLM | NER (ChemDisGene) |  |
| 20 | `ner_comparison_report` | LLM | NER Comparison Report |  |
| 21 | `ner_from_tree_llm` | LLM | NER from Dependency Tree (LLM) |  |
| 22 | `ner_llm` | LLM | NER (LLM, configurable types) |  |
| 23 | `ontology_entity_link` | LLM | Entity Linking / Normalization (LLM) |  |
| 24 | `ontology_hypernym_filter` | LLM | Hypernym Filter (LLM) |  |
| 25 | `ontology_synonym_resolve` | LLM | Synonym Resolution (LLM) |  |
| 26 | `relation_extract_llm` | LLM | Relation Extraction (LLM) |  |
| 27 | `relation_from_tree_llm` | LLM | Relation Extraction from Tree (LLM) |  |
| 28 | `relation_verify_llm` | LLM | Relation Verification (LLM) |  |
| 29 | `report_comparator` | LLM | Report Comparator (LLM) |  |
| 30 | `report_experiment` | LLM | Experiment Report (LLM) |  |
| 31 | `report_experiment_tool` | LLM | Experiment Report (LLM + Tools) |  |
| 32 | `syntax_dep_parse` | LLM | Dependency Parse (CoNLL-U) |  |
| 33 | `text_coreference` | LLM | Coreference Resolution (LLM) |  |
| 34 | `text_sentence_split` | LLM | Sentence Split (LLM) |  |
| 35 | `text_summarize` | LLM | Text Summarization (LLM) |  |
| 36 | `text_word_segment` | LLM | Word Segmentation (LLM) |  |

### PGM agents (31)

| No. | ID | Type | Name | Description |
| ---: | --- | --- | --- | --- |
| 1 | `chemdisgene_answer_map` | PGM | ChemDisGene Answer Map (PGM) | Map ChemDisGene RE answer codes to canonical relation type labels. |
| 2 | `chemdisgene_ner_parse` | PGM | ChemDisGene NER Parse (PGM) | Parse ChemDisGene type/entity NER lines into entity-type dict for metrics. |
| 3 | `chemdisgene_pair_generate` | PGM | ChemDisGene Pair Generator (PGM) | Build ChemDisGene RE candidate pairs with relation template keys. |
| 4 | `chemdisgene_result_to_relation` | PGM | ChemDisGene Result to Relation (PGM) | Format mapped ChemDisGene relation types as head / rel_type / tail lines. |
| 5 | `cid_entities_dedupe_mesh` | PGM | CID Entities Dedupe (MeSH id) | Collapse oracle entities that share a MeSH id (synonyms) to one row per id before hypernym filter and pair generation. |
| 6 | `cid_pair_generate` | PGM | CID Pair Generator (PGM) | Builds chemical–disease head/tail text pairs with MeSH IDs from filtered Chemical and Disease entities. |
| 7 | `dataset_chemdisgene_build` | PGM | ChemDisGene Dataset Builder (PGM) | Build structured CSV from raw gold file; save under tests/<agent_id>/. |
| 8 | `dataset_cid_tuning_build` | PGM | CID Tuning Dataset Builder (PGM) | Build stratified tuning CSV from a raw gold file; output under tests/<agent_id>/. |
| 9 | `e2e_entities_assign_group_ids` | PGM | E2E Assign Synonym Group IDs (PGM) | Assign shared numeric ids (1, 2, ...) per label to synonym groups; all surface forms in a group share the same id. |
| 10 | `e2e_entities_dedup_by_id` | PGM | E2E Entities Dedup By ID | Deduplicate entities by shared id; keep shortest surface form per id group. |
| 11 | `e2e_entities_passthrough` | PGM | E2E Entities Passthrough | Dedupe Flair NER entities and use surface text as id when MeSH id is missing (E2E RE path). |
| 12 | `e2e_entity_aliases_snapshot` | PGM | E2E Entity Aliases Snapshot (PGM) | Preserve all synonym surface forms + shared numeric ids for metrics lookup (before dedup). |
| 13 | `eval_flair` | PGM | Auto FLAIR NER Metrics | Counts unique FLAIR NER entities per label and returns total and per-label entity counts. |
| 14 | `eval_llm` | PGM | Auto LLM NER Metrics | Counts unique LLM NER entities per label and returns total and per-label entity counts. |
| 15 | `eval_metrics` | PGM | Evaluation Metrics (PGM) | Computes NER precision, recall, and F1 by comparing predicted and expected entity sets via MetricsCalculation. |
| 16 | `eval_metrics_relation` | PGM | Relation Set Metrics (PGM) | Evaluates chemical–induced-disease relation sets by normalizing and comparing predicted relations to ground truth. |
| 17 | `eval_metrics_segment` | PGM | Segmentation Metrics (PGM) | Scores pipe-delimited word segmentation by boundary precision, recall, F1, and segmentation error analysis. |
| 18 | `eval_pair_generate` | PGM | Evaluation Pair Generator (PGM) | Generates all chemical–disease evaluation pairs from expected Chemical and Disease entity lists. |
| 19 | `kg_rdf_export` | PGM | RDF-JSON Export (PGM) | Exports knowledge-graph triples to RDF-JSON with node labels and subject–predicate–object edges. |
| 20 | `kg_triple_merge` | PGM | Triple Merge (PGM) | Merges pipe-delimited relations with entity-link canonicalization and deduplicates head–predicate–tail triples. |
| 21 | `kg_triple_persist` | PGM | Triple CSV Persistence (PGM) | Persists merged knowledge-graph triples to CSV under result with head, verb, and tail columns. |
| 22 | `llm_link_bulk_update` | PGM | Bulk LLM Link Update (PGM) | Bulk-updates LLM connector links on selected agents from a source model to a target, optionally dry-run. |
| 23 | `merge_metrics` | PGM | Merge Flair and LLM Metrics | Combines FLAIR and LLM NER metric dictionaries into a single merged_metrics report object. |
| 24 | `ner_entities_to_re_format` | PGM | NER Entities to RE Format | Converts Flair NER label dict {Chemical:[...], Disease:[...]} to the entity list format [{text, label, id}] expected by the CID RE pipeline. |
| 25 | `ner_flair_aggregate` | PGM | Flair NER Aggregator | Aggregates per-sentence FLAIR NER outputs into document-level label-to-unique-entity-text dictionaries. |
| 26 | `ner_flair_doc` | PGM | NER (Flair, document) | Runs HunFlair2 NER on a document split into sentences and returns deduplicated entities per label. |
| 27 | `ner_flair_sent` | PGM | NER (Flair, sentence) | Tags one sentence with HunFlair2 NER and returns predicted entity texts grouped by label. |
| 28 | `relation_extract_pubtator` | PGM | Relation Extraction (PubTator) | Extracts chemical–disease relations from text or PMID using PubTator3 and local entity annotations. |
| 29 | `relation_result_to_id_pair` | PGM | Relation Result -> ID Pair | Emits head_id/tail_id CID relation lines when verification is positive, with negation and weak-association guards. |
| 30 | `relation_verify_to_pair` | PGM | Relation Verify → Entity Pair | Maps a positive relation verification to canonical head and tail entity IDs from entity_link. |
| 31 | `report_format_json` | PGM | Result Formatter (PGM) | Formats original text and summary into JSON with character lengths for reporting pipelines. |

## Graphs

### Subgraphs (10)

| No. | ID | Type | Name | Description |
| ---: | --- | --- | --- | --- |
| 1 | `sg_chemdisgene_re_verify` | subgraph | ChemDisGene RE verify pair | Branch on rel_template to ChemDisGene RE verify agents; map answer to relation line. |
| 2 | `sg_cid_re_verify` | subgraph | CID RE verify pair | Verify one Chemical–Disease pair; output MeSH id pair when verdict is induces. |
| 3 | `sg_e2e_cid_re` | subgraph | E2E CID RE (subgraph) | Subgraph: passthrough → synonym → assign ids → alias snapshot → dedup → hypernym → pair gen → verify loop. |
| 4 | `sg_e2e_flair_ner` | subgraph | E2E Flair NER (subgraph) | Subgraph: sentence split → loop HunFlair2 per sentence → RE format entities. Input: text + labels. Output: entities as [{text, label, id}]. |
| 5 | `sg_e2e_pubtator_re` | subgraph | E2E PubTator3 RE (subgraph) | Subgraph: PubTator3 API → CID relations. Input: text + pmid. Output: relations as head_id / CID / tail_id lines. |
| 6 | `sg_ner_flair_sent` | subgraph | Sentence Flair NER | Run ner_flair_sent on one sentence (loop body). |
| 7 | `sg_preprocess_inner` | subgraph | Inner preprocess loop body | Format / pass-through inner loop step. |
| 8 | `sg_re_preprocess` | subgraph | RE preprocess + NER | Nested inner loop then ner_llm (outer loop body for doc RE). |
| 9 | `sg_re_tree` | subgraph | Tree-based RE | syntax_dep_parse → relation_from_tree_llm per sentence. |
| 10 | `sg_relation_verify` | subgraph | Relation verify pair | relation_verify_llm → relation_verify_to_pair for one head/tail pair. |

### Workflows (23)

| No. | ID | Type | Name | Description |
| ---: | --- | --- | --- | --- |
| 1 | `wf_chemdisgene_ner_llm_eval` | workflow | ChemDisGene NER Eval (LLM) | ChemDisGene NER with type/entity prompt and entity dict metrics. |
| 2 | `wf_chemdisgene_re_llm_linear` | workflow | ChemDisGene RE Pipeline (linear) | Gold entities → pair generation → foreach RE verify (template branch) → relation metrics. |
| 3 | `wf_cid_ner_llm_eval` | workflow | CID NER Eval (LLM) | Chemical/Disease NER with LLM and generic metrics. |
| 4 | `wf_cid_re_branch` | workflow | CID RE (multi-branch gate) | NER then 4-way branch gate before relation extraction. |
| 5 | `wf_cid_re_llm_linear` | workflow | CID RE Pipeline (linear) | Gold entities → e2e dedup by id → e2e hypernym filter (with text context) → pair list → foreach RE verify → id pairs. Upgraded from wf_e2e_flair_opt_re agents. |
| 6 | `wf_cid_re_llm_linear_opt_20260529_143039_r2` | workflow | CID RE Pipeline (linear) [optimized] | Gold entities → e2e dedup by id → e2e hypernym filter (with text context) → pair list → foreach RE verify → id pairs. Upgraded from wf_e2e_flair_opt_re agents. |
| 7 | `wf_cid_re_llm_linear_opt_20260604` | workflow | CID RE Pipeline (linear) [optimized v2] | Gold entities → hypernym filter → pair list → foreach RE verify → id pairs. Optimized on 50-stratified dev articles. relation_verify_llm prompt: reject endogenous substances, accept AE reporting language. |
| 8 | `wf_doc_ner_flair_eval` | workflow | Doc NER Eval (Flair) | Document Flair NER with metrics (replaces bio_ner_graph). |
| 9 | `wf_doc_ner_flair_sent_eval` | workflow | Doc NER Eval (Flair, sentence) | Sentence split → loop HunFlair2 per sentence → entity metrics (Table S2 / Fig. S2). |
| 10 | `wf_doc_ner_llm_eval` | workflow | Doc NER Eval (LLM) | Split document then LLM NER with metrics. |
| 11 | `wf_doc_ner_loop_branch` | workflow | Doc NER loop + branch | Sentence split → loop Flair NER → 4-way branch → optional LLM → metrics. |
| 12 | `wf_doc_re_nested_branch` | workflow | Doc RE (nested loop + branch) | Outer loop with nested preprocess + NER, 4-way branch, then RE. |
| 13 | `wf_e2e_flair_opt_re` | workflow | E2E Flair NER + Optimized RE | Flair sentence-split NER → optimized CID RE (v0008 prompt) → relation metrics. For Table S18. |
| 14 | `wf_e2e_pubtator_re` | workflow | E2E PubTator3 RE | Compose sg_e2e_pubtator_re (PubTator3 API → relations) → relation metrics vs gold_relations. For Table S18 comparison. |
| 15 | `wf_flair_vs_llm_ner` | workflow | Flair vs LLM NER Comparison | Sentence split, Flair loop NER, LLM NER, per-path metrics, and ner_comparison_report on the same document. |
| 16 | `wf_general_report_linear` | workflow | Summarize + format | Summarize text and pack into JSON result. |
| 17 | `wf_kg_flair_full` | workflow | KG Build (Flair NER) | Flair doc NER → entity link → triple extract → merge → RDF. |
| 18 | `wf_kg_llm_full` | workflow | KG Build (LLM NER) | LLM NER → entity link → RE → triple merge → RDF export. |
| 19 | `wf_kg_syntax_loop` | workflow | KG from syntax (sentence loop) | Coreference → split → loop tree-RE subgraph → CSV persist. |
| 20 | `wf_re_pubtator_dev10` | workflow | PubTator RE Dev (10) | BC5CDR dev.txt (10 articles): gold entities → PubTator3 relation extraction → relation pair metrics vs gold_relations. |
| 21 | `wf_re_pubtator_eval` | workflow | PubTator RE Eval | Gold entities → PubTator relation extraction → relation pair metrics. |
| 22 | `wf_re_verify_llm_loop` | workflow | RE Verify (pair loop) | Generate evaluation pairs → loop verify subgraph → metrics. |
| 23 | `wf_word_seg_llm_eval` | workflow | Word Segmentation Eval | LLM word segmentation with boundary metrics. |
