# NeuraGraph

A lightweight platform for building LLM-powered workflow agents for biomedical NLP and knowledge graph tasks.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Quick Start

```bash
py -m pip install -r requirements.txt
.\start.bat
```

Open `http://127.0.0.1:5001`.

## Documentation

- [doc/MANUAL.md](doc/MANUAL.md): end-user UI walkthrough with screenshots
- [doc/CODE_WIKI.md](doc/CODE_WIKI.md): architecture and coding conventions
- [doc/EXPERIMENT_GUIDE.md](doc/EXPERIMENT_GUIDE.md): startup, schema, metrics, and experiment operations
- [doc/AUTOGEN_SKILL.md](doc/AUTOGEN_SKILL.md): workflow generation reference

## Meta Inventory

### Agents (`meta/agents`)

- `cid_pair_generate`
- `eval_metrics`
- `eval_metrics_relation`
- `eval_metrics_segment`
- `eval_pair_generate`
- `kg_rdf_export`
- `kg_triple_extract_llm`
- `kg_triple_merge`
- `kg_triple_persist`
- `ner_flair_doc`
- `ner_flair_sent`
- `ner_from_tree_llm`
- `ner_llm`
- `ontology_entity_link`
- `ontology_hypernym_filter`
- `ontology_hypernym_identify`
- `ontology_synonym_extract`
- `ontology_synonym_resolve`
- `relation_dti_analyze`
- `relation_extract_llm`
- `relation_from_tree_llm`
- `relation_verify_llm`
- `relation_verify_to_id_pair`
- `relation_verify_to_pair`
- `report_experiment`
- `report_format_json`
- `syntax_dep_parse`
- `text_coreference`
- `text_sentence_split`
- `text_summarize`
- `text_word_segment`

### Graphs (`meta/graphs`)

- `sg_cid_re_verify`
- `sg_ner_flair_sent`
- `sg_ner_llm_tree`
- `sg_preprocess_inner`
- `sg_relation_verify`
- `sg_re_preprocess`
- `sg_re_tree`
- `wf_cid_ner_flair_eval`
- `wf_cid_ner_llm_eval`
- `wf_cid_re_branch`
- `wf_cid_re_llm_linear`
- `wf_doc_ner_flair_eval`
- `wf_doc_ner_llm_eval`
- `wf_doc_ner_loop_branch`
- `wf_doc_re_nested_branch`
- `wf_general_report_linear`
- `wf_kg_flair_full`
- `wf_kg_llm_full`
- `wf_kg_syntax_loop`
- `wf_re_verify_llm_loop`
- `wf_word_seg_llm_eval`

### Tools (`meta/tools`)

- `merge_heads_tails_to_entities`
- `tool_ner_flair`

## Project Layout

```
meta/          agents, graphs, llms, tools, exps
service/       runtime entities and loaders
ui/            Flask app and visual editor
plugin/        plugin loader and plugin definitions
tests/         per-workflow CSV test sets
result/        experiment outputs
utils/         bindings and metrics helpers
doc/           documentation
```
