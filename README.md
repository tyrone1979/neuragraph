# NeuraGraph

A lightweight platform for building LLM-powered workflow agents for biomedical NLP and knowledge graph tasks.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Quick Start

```bash
py -m pip install -r requirements.txt
.\start.bat
```

Open **http://127.0.0.1:5001**.

## Documentation

| Document | Description |
|----------|-------------|
| [doc/MANUAL.md](doc/MANUAL.md) | **User manual** — full UI walkthrough with 30+ screenshots |
| [doc/EXPERIMENT_GUIDE.md](doc/EXPERIMENT_GUIDE.md) | Startup, metadata schema, metrics, experiments, and optimization pipeline |
| [doc/CODE_WIKI.md](doc/CODE_WIKI.md) | Architecture and coding conventions |
| [doc/CHAT_COMMANDS.md](doc/CHAT_COMMANDS.md) | Floating assistant / terminal slash commands |
| [doc/AUTOGEN_SKILL.md](doc/AUTOGEN_SKILL.md) | LLM workflow generation reference |

### Refresh UI screenshots

```powershell
.\start.bat
py -3 scripts/refresh_manual_screenshots.py
py -3 scripts/capture_supplemental_screenshots.py
```

Screenshots are saved to `doc/images/` and embedded in `MANUAL.md`.

## Core Features

- **Visual workflow editor** — JointJS DAG, loops/branches, subgraphs, per-node test
- **Agents** — LLM / PGM / legacy SUB; version history and diff
- **Batch experiments** — test + tuning datasets, auto-split, SSE progress
- **Optimization pipeline** — baseline → tuning report → agent refine → optimized workflow comparison
- **Floating assistant** — slash commands shared with `chat.py` terminal
- **PubTator / CID** — relation extraction and BC5CDR-style metrics

## Meta Inventory

### Agents (`meta/agents`)

<details>
<summary>42 agents (click to expand)</summary>

- `agent_refiner`
- `cid_pair_generate`
- `dataset_cid_tuning_build`
- `eval_flair`
- `eval_llm`
- `eval_metrics`
- `eval_metrics_relation`
- `eval_metrics_segment`
- `eval_pair_generate`
- `kg_rdf_export`
- `kg_triple_extract_llm`
- `kg_triple_merge`
- `kg_triple_persist`
- `merge_metrics`
- `ner_comparison_report`
- `ner_flair_aggregate`
- `ner_flair_doc`
- `ner_flair_sent`
- `ner_from_tree_llm`
- `ner_llm`
- `ontology_entity_link`
- `ontology_hypernym_filter`
- `ontology_hypernym_identify`
- `ontology_mesh_lookup`
- `ontology_synonym_extract`
- `ontology_synonym_resolve`
- `relation_dti_analyze`
- `relation_extract_llm`
- `relation_extract_pubtator`
- `relation_from_tree_llm`
- `relation_result_to_id_pair`
- `relation_verify_llm`
- `relation_verify_to_pair`
- `report_comparator`
- `report_experiment`
- `report_experiment_tool`
- `report_format_json`
- `syntax_dep_parse`
- `text_coreference`
- `text_sentence_split`
- `text_summarize`
- `text_word_segment`

</details>

### Graphs (`meta/graphs`)

<details>
<summary>Workflows and subgraphs (click to expand)</summary>

**Subgraphs (`sg_*`)**: `sg_cid_re_verify`, `sg_ner_flair_sent`, `sg_ner_llm_tree`, `sg_preprocess_inner`, `sg_re_preprocess`, `sg_re_tree`, `sg_relation_verify`

**Evaluation / pipelines (`wf_*`)**:

- NER: `wf_cid_ner_flair_eval`, `wf_cid_ner_llm_eval`, `wf_doc_ner_flair_eval`, `wf_doc_ner_llm_eval`, `wf_doc_ner_loop_branch`, `wf_flair_vs_llm_ner`, `wf_word_seg_llm_eval`
- RE / CID: `wf_cid_re_branch`, `wf_cid_re_llm_linear`, `wf_doc_re_nested_branch`, `wf_re_pubtator_dev10`, `wf_re_pubtator_eval`, `wf_re_verify_llm_loop`
- KG: `wf_kg_flair_full`, `wf_kg_llm_full`, `wf_kg_syntax_loop`
- Other: `wf_general_report_linear`, `ner_flair_sent_loop`

Optimized variants (`wf_*_opt_*`) are created automatically by the optimization pipeline.

</details>

### Tools (`meta/tools`)

- `agent_change_impact_trace`
- `agent_version_guard`
- `dataset_cid_tuning_build`
- `dataset_sampler_stratified`
- `error_case_exporter`
- `fn_fp_bucket_analyzer`
- `merge_heads_tails_to_entities`
- `metrics_delta_compare`
- `prompt_patch_apply_safe`
- `report_quality_scorer`
- `tool_ner_flair`
- `tool_pubtator_relation_extract`

## Project Layout

```
meta/          agents, graphs, llms, tools, exps (+ version snapshots)
service/       runtime entities, optimization, PubTator, chat commands
ui/            Flask app, JointJS editor, experiment wizard, chat widget
plugin/        PGM sandbox, metrics, Flair
tests/         unit tests + per-workflow CSV datasets
result/        experiment states.json and reports
utils/         bindings, workflow metrics
scripts/       screenshot refresh, optimize CLI
doc/           documentation + images/
```

## License

MIT — see [LICENSE](LICENSE) if present.
