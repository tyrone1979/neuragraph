# NeuraGraph

A lightweight platform for building LLM-powered workflow agents for biomedical NLP and knowledge graph tasks.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Environment Setup

Requires **Python 3.12** (langchain 1.x+ dependency). Install the main app and plugin sandboxes separately.

### 1. System prerequisites

**Windows** — [Python 3.12](https://www.python.org/downloads/) (check "Add to PATH").

**Linux (Ubuntu/Debian)**

```bash
apt install python3.12 python3.12-venv
```

The `python3.12-venv` package provides `ensurepip` — without it, `python3.12 -m venv` fails with exit status 1.

### 2. Main application

**Windows**

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Linux / macOS**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# langgraph and langgraph-prebuilt share a namespace; reinstall prebuilt last
pip install --force-reinstall --no-deps langgraph-prebuilt==1.1.0
```

> **Why the extra line?** `langgraph` depends on `langgraph-prebuilt`, so pip installs prebuilt *before* langgraph. Since both write to `langgraph/prebuilt/__init__.py`, langsgraph's version (missing `ToolCallTransformer`) overwrites prebuilt's. Reinstalling `langgraph-prebuilt` last fixes this. This is not needed on Windows where pip may resolve in a different order.

Key version requirements (pinned in `requirements.txt`):

| Package | Version |
|---------|---------|
| langchain | 1.3.1 |
| langgraph | 1.2.1 |
| langchain-core | 1.4.0 |
| langchain-openai | 1.2.1 |
| langchain-ollama | 1.1.0 |
| langgraph-checkpoint | 4.1.0 |
| langgraph-prebuilt | 1.1.0 |
| langgraph-sdk | 0.3.14 |

> **Note:** `create_agent` was introduced in langchain 1.0. Older versions (e.g. 0.2.17) do **not** have this API and will fail at import.

### 3. Plugin sandboxes (Flair NER, port 5002)

Heavy PGM plugins run in isolated sidecar venvs defined in `meta/plugins_sandbox.json`. The setup script picks the system Python (preferring 3.12) and creates a dedicated venv under `sandbox/<id>/`.

**Windows**

```powershell
.\sandbox\setup_venv.ps1 -Name flair
```

**Linux / macOS**

```bash
chmod +x sandbox/setup_venv.sh
./sandbox/setup_venv.sh flair
```

Linux sandbox setup installs `torch==2.6.0+cpu` from the PyTorch CPU index for Flair.

To add a custom sandbox, copy `sandbox/_template` to `sandbox/<id>/`, set `enabled: true` in the manifest, then run setup with that id.

Start a single sandbox manually (foreground or background):

**Windows:** `.\scripts\start_plugin_sandbox.ps1 -Name flair`
**Linux / macOS:** `./scripts/start_plugin_sandbox.sh flair` (add `-b` for background)

## Quick Start

After setup above:

**Windows**

```powershell
.\start.bat          # Foreground (Ctrl+C to stop)
```

**Linux / macOS**

```bash
chmod +x start.sh stop.sh status.sh chat.sh sandbox/setup_venv.sh scripts/start_plugin_sandbox.sh

./start.sh           # Start in background (survives terminal close)
./stop.sh            # Stop all background processes
./status.sh          # Check running status
```

Open **http://127.0.0.1:5001**.

Terminal chat: `.\chat.bat` or `./chat.sh` (optional `--llm deepseek`).

> **Background mode** (Linux/macOS): `./start.sh` runs Flask and sandboxes under `nohup` with PIDs tracked in `.pids/` and output logged to `logs/`. Closing the terminal won't stop them. Use `./stop.sh` to shut down cleanly.

## Documentation

| Document | Description |
|----------|-------------|
| [doc/MANUAL.md](doc/MANUAL.md) | **User manual** — full UI walkthrough with 30+ screenshots |
| [doc/EXPERIMENT_GUIDE.md](doc/EXPERIMENT_GUIDE.md) | Startup, metadata schema, metrics, experiments, and optimization pipeline |
| [doc/SUPPLEMENTARY.md](doc/SUPPLEMENTARY.md) | Supplementary Material text (sync to Word for submission) |
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
<summary>37 agents (click to expand)</summary>

| ID | Type | Description |
|----|------|-------------|
| `agent_refiner` | LLM | Analyzes experiment diagnostics and proposes safe prompt/process patches for the optimization loop. |
| `cid_pair_generate` | PGM | Builds chemical-disease head-tail pairs from filtered entities for CID relation verification. |
| `dataset_cid_tuning_build` | PGM | Builds stratified CID tuning and test CSV datasets from PubTator gold annotations. |
| `eval_flair` | PGM | Computes NER precision, recall, and F1 from Flair entity predictions. |
| `eval_llm` | PGM | Computes NER precision, recall, and F1 from LLM entity predictions. |
| `eval_metrics` | PGM | Generic entity-dict metrics calculator (precision, recall, F1). |
| `eval_metrics_relation` | PGM | Computes relation-pair set metrics with optional MeSH ID normalization. |
| `eval_metrics_segment` | PGM | Boundary/segmentation metrics for word-segmentation evaluation. |
| `eval_pair_generate` | PGM | Generates head-tail evaluation pairs from gold entity annotations. |
| `kg_rdf_export` | PGM | Exports knowledge-graph triples to RDF-JSON format. |
| `kg_triple_extract_llm` | LLM | Extracts subject-predicate-object triples from text and entities. |
| `kg_triple_merge` | PGM | Merges relations and entity links into a unified triple list. |
| `kg_triple_persist` | PGM | Persists triples and synonym metadata to CSV output. |
| `llm_link_bulk_update` | PGM | Bulk-updates `model` references across LLM agents when switching connector IDs. |
| `merge_metrics` | PGM | Merges Flair and LLM NER metric dicts for side-by-side comparison. |
| `ner_comparison_report` | LLM | Generates a narrative NER comparison report from merged metrics. |
| `ner_flair_aggregate` | PGM | Aggregates sentence-level Flair NER results to document-level entities. |
| `ner_flair_doc` | PGM | Document-level named entity recognition using Flair models. |
| `ner_flair_sent` | PGM | Sentence-level named entity recognition using Flair models. |
| `ner_from_tree_llm` | LLM | NER guided by a dependency parse tree. |
| `ner_llm` | LLM | Named entity recognition with configurable entity label types. |
| `ontology_entity_link` | LLM | Entity linking and normalization to canonical forms or IDs. |
| `ontology_hypernym_filter` | LLM | Filters entities using hypernym constraints before pair generation. |
| `ontology_synonym_resolve` | LLM | Resolves entity synonyms to canonical names. |
| `relation_extract_llm` | LLM | Extracts relations between annotated entities in text. |
| `relation_extract_pubtator` | PGM | Calls PubTator3 API for chemical-disease relation extraction. |
| `relation_from_tree_llm` | LLM | Relation extraction using a dependency parse tree. |
| `relation_result_to_id_pair` | PGM | Converts a relation verification result to a MeSH ID pair string. |
| `relation_verify_llm` | LLM | Verifies whether a chemical-disease pair has an induce relation. |
| `relation_verify_to_pair` | PGM | Formats a verified relation as an entity pair for metric comparison. |
| `report_comparator` | LLM | Compares two experiment reports and highlights differences. |
| `report_experiment` | LLM | Generates a full experiment report from batch run states. |
| `report_experiment_tool` | LLM | Experiment report with tool-assisted error analysis. |
| `report_format_json` | PGM | Wraps summary text and metadata into a JSON result payload. |
| `syntax_dep_parse` | LLM | Dependency parsing output in CoNLL-U format. |
| `text_coreference` | LLM | Coreference resolution on biomedical documents. |
| `text_sentence_split` | LLM | Splits a document into sentences. |
| `text_summarize` | LLM | Text summarization for documents or passages. |
| `text_word_segment` | LLM | Word/boundary segmentation for evaluation tasks. |

</details>

### Graphs (`meta/graphs`)

<details>
<summary>Workflows and subgraphs (click to expand)</summary>

#### Subgraphs (`sg_*`)

| ID | Name | Description |
|----|------|-------------|
| `sg_cid_re_verify` | CID RE verify pair | Verifies one chemical-disease pair; outputs `id \| id` if induce ($). |
| `sg_ner_flair_sent` | Sentence Flair NER | Runs `ner_flair_sent` on one sentence (loop body). |
| `sg_ner_llm_tree` | Tree-based LLM NER | `syntax_dep_parse` → `ner_from_tree_llm` per sentence. |
| `sg_preprocess_inner` | Inner preprocess loop body | Format / pass-through inner loop step. |
| `sg_re_preprocess` | RE preprocess + NER | Nested inner loop then `ner_llm` (outer loop body for document RE). |
| `sg_re_tree` | Tree-based RE | `syntax_dep_parse` → `relation_from_tree_llm` per sentence. |
| `sg_relation_verify` | Relation verify pair | `relation_verify_llm` → `relation_verify_to_pair` for one head/tail pair. |

#### Workflows (`wf_*`)

| ID | Name | Description |
|----|------|-------------|
| `wf_doc_ner_flair_sent_eval` | Doc NER Eval (Flair, sentence) | Sentence split → loop `sg_ner_flair_sent` → metrics. |
| `wf_cid_ner_llm_eval` | CID NER Eval (LLM) | Chemical/disease NER with LLM and generic metrics. |
| `wf_cid_re_branch` | CID RE (multi-branch gate) | NER then 4-way branch gate before relation extraction. |
| `wf_cid_re_llm_linear` | CID RE Pipeline (linear) | Gold entities → hypernym filter → pair list → foreach RE verify → ID pairs. |
| `wf_doc_ner_flair_eval` | Doc NER Eval (Flair) | Document Flair NER with metrics. |
| `wf_doc_ner_llm_eval` | Doc NER Eval (LLM) | Split document then LLM NER with metrics. |
| `wf_doc_ner_loop_branch` | Doc NER loop + branch | Sentence split → loop Flair NER → 4-way branch → optional LLM → metrics. |
| `wf_doc_re_nested_branch` | Doc RE (nested loop + branch) | Outer loop with nested preprocess + NER, 4-way branch, then RE. |
| `wf_flair_vs_llm_ner` | Flair vs LLM NER Comparison | Runs Flair and LLM NER pipelines and compares metrics side by side. |
| `wf_general_report_linear` | Summarize + format | Summarize text and pack into JSON result. |
| `wf_kg_flair_full` | KG Build (Flair NER) | Flair doc NER → entity link → triple extract → merge → RDF. |
| `wf_kg_llm_full` | KG Build (LLM NER) | LLM NER → entity link → RE → triple merge → RDF export. |
| `wf_kg_syntax_loop` | KG from syntax (sentence loop) | Coreference → split → loop tree-RE subgraph → CSV persist. |
| `wf_re_pubtator_dev10` | PubTator RE Dev (10) | BC5CDR dev set (10 articles): gold entities → PubTator3 RE → relation-pair metrics. |
| `wf_re_pubtator_eval` | PubTator RE Eval | Gold entities → PubTator relation extraction → relation-pair metrics. |
| `wf_re_verify_llm_loop` | RE Verify (pair loop) | Generate evaluation pairs → loop verify subgraph → metrics. |
| `wf_word_seg_llm_eval` | Word Segmentation Eval | LLM word segmentation with boundary metrics. |
| `ner_flair_sent_loop` | Sentence Flair NER loop | Auto-generated loop-body workflow for sentence-level Flair NER. |

Optimized variants (`wf_*_opt_*`) are created automatically by the optimization pipeline.

</details>

### Tools (`meta/tools`)

| ID | Description |
|----|-------------|
| `agent_change_impact_trace` | Estimates per-agent metric contribution from version maps and two experiment states. |
| `agent_version_guard` | Policy-based guard for keep/alert/rollback decisions using metric deltas. |
| `dataset_cid_tuning_build` | Builds a stratified CID tuning CSV (and optional test-remain set) from PubTator gold dev.txt. |
| `dataset_sampler_stratified` | Stratified sampling by text length, entity density, and relation density for quick A/B validation. |
| `error_case_exporter` | Exports worst-k error cases from states into Markdown and JSONL for review/regression. |
| `fn_fp_bucket_analyzer` | Buckets FN/FP into boundary/type/relation/missed-recall categories with examples. |
| `merge_heads_tails_to_entities` | Merges head/tail entity lists into unified `text,type,mesh` lines. |
| `metrics_delta_compare` | Compares baseline and candidate states; returns P/R/F1 deltas and degraded samples. |
| `prompt_patch_apply_safe` | Applies structured prompt patches (append/replace) with validation and safety checks. |
| `report_quality_scorer` | Scores report quality on evidence, executability, and traceability. |
| `tool_ner_flair` | Runs Flair NER on a sentence for given labels; returns a label → mentions dict. |
| `tool_pubtator_relation_extract` | Calls PubTator3 API to extract chemical-disease relations from PMID or text. |

## Project Layout

```
meta/          agents, graphs, llms, tools, exps (+ version snapshots)
service/       runtime entities, optimization, PubTator, chat commands
ui/            Flask app, JointJS editor, experiment wizard, chat widget
plugin/        PGM sandbox, metrics, Flair
tests/         per-agent / per-workflow CSV datasets (no test scripts)
ui_tests/      run_tests.py; suites/; unit/; reports/ (see doc/TESTING.md)
result/        experiment states.json and reports
utils/         bindings, workflow metrics
scripts/       screenshot refresh, optimize CLI
doc/           documentation + images/; TESTING.md (suites, unit tests, report links)
```

## License

MIT — see [LICENSE](LICENSE) if present.
