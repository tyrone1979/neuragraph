# NeuraGraph

A lightweight platform for building LLM-powered agent workflows for biomedical NLP and knowledge-graph tasks.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## What it does

- Compose **workflows** (`meta/graphs`) from **agents** (LLM / PGM / loop / branch flow nodes).
- Run **experiments** on CSV test sets under `tests/<graph_id>/`.
- Stream node output over SSE; persist checkpoint state to `result/<exp_id>/states.json`.
- Compute **precision / recall / F1** via the `MetricsCalculation` plugin after each run (no eval node required in the graph).

Typical pipelines: NER, relation extraction (CID), hypernym filtering, pair verification loops, KG triple export.

## Quick start

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Windows (recommended)
.\start.bat
# or: python -m ui.app
```

Open **http://127.0.0.1:5001**

Optional: HunFlair2 under `models/hunflair2-ner/` for Flair NER agents.

### First steps in the UI

1. **LLMs** — add at least one model config (`meta/llms/`).
2. **Workflows** — open e.g. `wf_cid_re_llm_linear` or `wf_doc_ner_llm_eval`.
3. **Datasets** — CSV in `tests/<workflow_id>/` (columns must match workflow inputs + gold fields).
4. **Experiments** — select workflow + dataset → run → view report.

## Example workflows

| Graph ID | Description |
|----------|-------------|
| `wf_cid_re_llm_linear` | Gold entities → hypernym filter → pairs → loop RE verify → MeSH relation lines |
| `wf_cid_ner_llm_eval` | Document LLM NER + metrics |
| `wf_doc_ner_loop_branch` | Sentence loop + branch (Flair vs LLM) |
| `wf_re_verify_llm_loop` | Pair generation + verify loop |
| `wf_kg_syntax_loop` | Per-sentence tree-based RE |
| `wf_kg_llm_full` | Full KG pipeline (NER → link → triples) |

Subgraphs (`sg_*`) are loop/branch bodies; run **`wf_*`** graphs in experiments.

## Metrics (experiments)

Graph JSON may declare:

```json
"metrics": [{
  "type": "relation_pairs",
  "expected": { "from": "input", "field": "gold_relations" },
  "predicted": { "from": "state", "field": "relations" }
}]
```

When a run finishes, `RunnerLoader.persistence` loads each sample’s checkpoint + CSV row and calls `MetricsCalculation`. Results appear in `states.json` under `metrics` and in the experiment report.

See [doc/META_SCHEMA.md](doc/META_SCHEMA.md) for all supported meta fields.

## Documentation

| Document | Description |
|----------|-------------|
| [doc/MANUAL.md](doc/MANUAL.md) | UI walkthrough (LLM, agents, workflows, experiments) |
| [doc/STARTUP_GUIDE.md](doc/STARTUP_GUIDE.md) | Install, `start.bat`, troubleshooting |
| [doc/CODE_GUIDELINES.md](doc/CODE_GUIDELINES.md) | Code style and layout |
| [doc/CODE_WIKI.md](doc/CODE_WIKI.md) | Architecture, modules, APIs |
| [doc/META_SCHEMA.md](doc/META_SCHEMA.md) | Runtime JSON schema for `meta/` |
| [doc/EXPERIMENT_GUIDE.md](doc/EXPERIMENT_GUIDE.md) | BC5CDR / pharmacology evaluation notes |
| [doc/AUTOGEN_SKILL.md](doc/AUTOGEN_SKILL.md) | **LLM skill**: generate complex workflows, loops, metrics, experiments |

Agents live in `meta/agents/<id>.json` (browse in UI or on disk).

## Project layout

```
meta/          agents, graphs, llms, tools, exps
service/       GraphEntity, AgentEntity, Runner, metrics
ui/            Flask app + visual editor
plugin/        MetricsCalculation, Flair tagger, checkpointers
tests/         per-workflow CSV test sets
result/        experiment outputs (states.json)
utils/         bindings, graphutils, workflow_metrics
scripts/       prune_meta_unused.py, smoke tests, migrations
```

## Maintenance scripts

```bash
# Remove unused keys from meta JSON (safe to re-run)
python scripts/prune_meta_unused.py
```

## Citation

```bibtex
@misc{neuragraph2026,
  author = {Lei Zhao},
  title = {NeuraGraph: A Lightweight Platform for LLM-Powered Agent Workflows},
  year = {2026},
  howpublished = {\url{https://github.com/tyrone1979/neuragraph}}
}
```
