# NeuraGraph Code Wiki

Architecture, module map, and coding standards for contributors.

User-facing UI guide: [SUPPLEMENTARY.md](SUPPLEMENTARY.md) · [MANUAL.md](MANUAL.md) · Operations: [EXPERIMENT_GUIDE.md](EXPERIMENT_GUIDE.md)

---

## 1. Project Scope

NeuraGraph is a lightweight workflow platform for biomedical NLP and knowledge graph pipelines:

- Named entity recognition (chemical, disease, document/sentence level)
- Relation extraction (CID, PubTator, DTI)
- Loop and branch orchestration via LangGraph-style DAGs
- Batch experiments with precision/recall/F1 metrics
- **Agent optimization loop** — LLM-driven prompt patching with version pinning

---

## 2. Architecture Overview

```
Browser (Bootstrap + JointJS + jQuery)
  │
  ├─ Flask Blueprints (ui/*_api.py)
  │     ├─ /agents, /graph, /llms, /tools  — CRUD + versions
  │     ├─ /exp                              — experiments + optimization wizard
  │     ├─ /testset, /dataset                — CSV datasets
  │     ├─ /stream                           — SSE batch run & reports
  │     └─ /chat                             — floating assistant
  │
  ├─ Service Layer (service/)
  │     ├─ AgentEntity, GraphEntity, RunnerLoader
  │     ├─ experiment_optimize, optimization_pipeline
  │     ├─ pubtator_client, relation_normalize, dataset/ (catalog + parsers)
  │     └─ chat/commands (shared slash command core)
  │
  ├─ Meta Layer (service/meta/)
  │     └─ MetaLoader, agent/tool version snapshots
  │
  ├─ Plugin Layer (plugin/)
  │     └─ PGM sandbox, Flair, metrics, checkpointers
  │
  └─ Filesystem
        meta/    agents, graphs, llms, tools, exps
        tests/   per-agent sample.csv + per-graph CSV datasets
        result/  experiment states.json + reports
```

---

## 3. Directory Layout

```
meta/
  agents/              Agent JSON definitions
  agent_versions/      Version snapshots per agent
  graphs/              wf_* workflows, sg_* subgraphs
  tools/               LLM-callable Python tools
  tool_versions/       Tool version snapshots
  llms/                Provider configs
  exps/                Experiment metadata
service/
  entity/              AgentEntity, GraphEntity, RunnerLoader, TestLoader
  meta/                MetaLoader, version helpers
  result/              ResultLoader (states.json)
  experiment_optimize.py
  optimization_pipeline.py
  optimize_suggestion_filter.py
  pubtator_client.py
  relation_normalize.py
  relation_normalize.py
  dataset/
    data_parser.py       CIDParser, ChemDisGeneParser, Article/Entity/Relation
    core.py              DatasetCatalog (raw gold → CSV)
    parsers.py           CDR / ChemDisGene / plain-text parsers
    rows.py              re / ner / pubtator row builders
  chat/commands.py
ui/
  app.py               Flask app factory
  *_api.py             Route blueprints
  templates/           Jinja2 pages + components
  static/js/           graphs.js, experiment.js, chat_widget.js, …
plugin/
  plugin_loader.py
  plugins.py           Metrics, Flair, PGM executor, DatasetCatalog, parsers
utils/
  workflow_metrics.py  Post-run metric computation
  graphutils.py        Bindings, agent roster, version resolution
scripts/
  refresh_manual_screenshots.py
  run_optimize_exp.py
doc/
  MANUAL.md, EXPERIMENT_GUIDE.md, …
tests/                 Unit tests + per-workflow CSV data
result/                Experiment outputs
```

---

## 4. Core Runtime Components

### 4.1 `service/entity/agent.py` — AgentEntity

- Types: `LLM`, `PGM`, legacy `SUB`
- `invoke()` maps `inputs` from flat state, executes, writes `outputs.name`
- Resolves pinned versions via `agentVersions` on parent graph
- PGM: sandboxed execution; result via `__result__`

### 4.2 `service/entity/graph.py` — GraphEntity

- Compiles `nodes`/`edges` to executable DAG (LangGraph)
- Applies per-node `bindings` before invocation
- `flowNodes`: loop (`foreach`) and branch controllers
- Subgraph nodes reference `sg_*` graphs

### 4.3 `service/entity/runner.py` — RunnerLoader

- Dispatches by id to agent or workflow
- `persistence()` writes outputs and runs graph `metrics` specs
- Used by `/stream/run` SSE batch runner

### 4.4 `service/meta/loader.py` — MetaLoader

- `load/loads/dump/delete` for JSON under `meta/*`
- ID = filename stem

### 4.5 Version system

| Module | Role |
|--------|------|
| `service/meta/agent_version.py` | Snapshot on agent save |
| `service/meta/tool_version.py` | Snapshot on tool save |
| Graph `agentVersions` | Pin specific versions in optimized workflows |
| UI modals | `entity_list.js`, `graphs.js` — diff & history |

### 4.6 Optimization

| Module | Role |
|--------|------|
| `experiment_optimize.py` | Main loop: reports → refiner → patch → candidate graph → F1 compare |
| `optimization_pipeline.py` | Maps wizard steps to runnable units |
| `optimize_suggestion_filter.py` | Blocks disallowed agent modifications |
| `agent_refiner` agent | LLM that proposes prompt patches |

### 4.7 Metrics & normalization

| Module | Role |
|--------|------|
| `utils/workflow_metrics.py` | Compute metrics from graph spec after run |
| `service/relation_normalize.py` | MeSH ID normalization for relation_pairs |
| `plugin/plugins.py` | `MetricsCalculation` plugin |

### 4.8 PubTator integration

| Module | Role |
|--------|------|
| `service/pubtator_client.py` | API client, entity filters, relation parsing |
| `relation_extract_pubtator` agent | PubTator-based relation extraction |

### 4.9 Datasets & plugins

| Module | Role |
|--------|------|
| `service/dataset/data_parser.py` | `CIDParser`, `ChemDisGeneParser`, `Article` / `Entity` / `Relation` |
| `service/dataset/core.py` | `DatasetCatalog` — `build_tuning`, `build_full`, `save_structured` |
| `service/dataset/parsers.py` | Native parsers; `load_articles_from_source` |
| `plugin/plugins.py` | `DatasetCatalogPlugin`, `CdrParserPlugin`, `ChemDisGeneParserPluginClass` |
| `ui_tests/utils/agent_sample_row_fixtures.py` | One-row fixtures for all agents |
| [doc/DATA_FORMAT.md](DATA_FORMAT.md) | Raw gold → CSV conventions |
| [doc/META_INVENTORY.md](META_INVENTORY.md) | Full agent/graph list (auto-generated) |

---

## 5. UI Module Map

| Template / JS | Route | Purpose |
|---------------|-------|---------|
| `index.html` | `/` | Dashboard |
| `agent_list.html`, `agent_form.html`, `agent.js` | `/agents` | Agent CRUD, test, version diff |
| `graph_list.html`, `graph.html`, `graphs.js`, `graph_visual_editor.js` | `/graph` | Workflow list (families), JointJS editor |
| `experiment_list.html`, `exp_tree_table.html`, `exp_list.js` | `/exp` | Tree: family → version → dataset |
| `experiment.html`, `experiment.js` | `/exp/<id>` | 4-step wizard, SSE, optimization |
| `runner_selector.html` | component | Workflow/agent search in forms |
| `testset` templates | `/testset` | CSV upload, preview, split |
| `chat_widget.js` | all pages | Floating `/chat` assistant |
| `base.html` | layout | Nav, chat FAB |

Screenshot capture: `scripts/refresh_manual_screenshots.py` → `doc/images/`.

---

## 6. Metadata Conventions

### Agents

- Filename = agent id (snake_case, no `wf_`/`sg_` prefix)
- Do **not** put `loopConfig` on agents — only on graph `flowNodes`
- Prefer omitting empty optional fields

### Graphs

- `wf_*` — experiment runners; `sg_*` — subgraph loop bodies only
- Bindings: `{{ START.field }}` or `{{ state_key }}`
- Declare `metrics` on workflow, not inside loop subgraphs when possible

### Experiments

- Always set `test_dataset` and `tuning_dataset` for optimization
- Keep `dataset` synced to `test_dataset` for legacy readers

### State

- Flat dict keys at top level
- Each agent writes exactly one primary output key (`outputs.name`)

---

## 7. Coding Guidelines

### Style

- Python 3.11+ (README badge: 3.12+)
- PEP 8, type hints where practical
- Small focused functions; match surrounding file style

### Safety

- PGM/tool code: minimal imports, deterministic logic
- Never commit `.env`, venv, model weights, `result/` dumps

### Testing

See **[TESTING.md](TESTING.md)** for suite descriptions, unit tests, and links to committed reports under `ui_tests/reports/`.

- Entry: `ui_tests/run_tests.py` (`--suite regression-exp|regression-graph|regression-tool|regression-agent|agents|agents-live|unit|all`)
- Playwright: `ui_tests/suites/playwright_regression_*.py` (graph G1–G4: `playwright_regression_graph.py`)
- Agent batch: mock (`--suite agents`) vs live LLM (`--suite agents-live` / `agent_invoke_mock_llm_suite.py --live-llm`)
- Unit tests: `ui_tests/unit/test_*.py`
- Reports: `ui_tests/reports/agent_test_report_*_latest.md`, `graph_suite_report_latest.md`

### Documentation

- User UI changes → update `doc/MANUAL.md` + refresh screenshots
- Schema/API changes → update `doc/EXPERIMENT_GUIDE.md`
- New slash commands → update `doc/CHAT_COMMANDS.md`

---

## 8. Development Workflow

1. `.\start.bat` or `python -m ui.app`
2. Edit meta JSON or use UI editors
3. Single-sample test in graph editor
4. Batch experiment on small CSV
5. Check `result/<exp_id>/states.json`
6. Run `py -3 -m pytest tests/` before commit

---

## 9. Related Documentation

| Doc | Audience |
|-----|----------|
| [SUPPLEMENTARY.md](SUPPLEMENTARY.md) | Paper supplementary — features, examples, component inventory |
| [MANUAL.md](MANUAL.md) | End users — UI walkthrough with screenshots |
| [EXPERIMENT_GUIDE.md](EXPERIMENT_GUIDE.md) | Operators — schema, metrics, optimization |
| [CHAT_COMMANDS.md](CHAT_COMMANDS.md) | Assistant / terminal command reference |
| [AUTOGEN_SKILL.md](AUTOGEN_SKILL.md) | LLM agents generating workflows |
| [README.md](../README.md) | Quick start and project layout |
