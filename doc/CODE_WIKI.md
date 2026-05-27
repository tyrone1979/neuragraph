# NeuraGraph Code Wiki

This document is the single source of truth for project architecture and coding standards.

## 1. Project Scope

NeuraGraph is a lightweight workflow platform for biomedical NLP and knowledge graph pipelines.
Typical tasks include:

- Named entity recognition (chemical, disease, etc.)
- Relation extraction (for example CID pairs)
- Loop and branch orchestration across subgraphs
- Experiment execution with built-in precision/recall/F1 metrics

## 2. Architecture Overview

```
UI (Flask templates + JS editor)
  -> API Blueprints (agents / graph / llms / tools / exp / stream)
  -> Service Layer (AgentEntity, GraphEntity, RunnerLoader)
  -> Meta Layer (MetaLoader, GraphMetaLoader)
  -> Plugin Layer (PGM sandbox, checkpointers, metrics)
  -> Filesystem data (meta/, tests/, result/)
```

## 3. Directory Layout

```
meta/          agent, graph, llm, tool, experiment JSON
service/       runtime entities and loaders
ui/            Flask app, templates, static assets
plugin/        plugin loader and plugin implementations
tests/         per-workflow CSV datasets
result/        experiment outputs (states.json)
utils/         graph bindings and metrics helpers
scripts/       maintenance scripts
doc/           project documentation
```

## 4. Core Runtime Components

### 4.1 `service/entity/agent.py`

- `AgentEntity` supports `LLM`, `PGM`, and legacy `SUB`.
- `invoke()` maps configured `inputs` from state, executes model or code, writes `outputs.name`.
- PGM execution is sandboxed and returns values through `__result__`.

### 4.2 `service/entity/graph.py`

- `GraphEntity` compiles `nodes`/`edges` into a workflow DAG.
- Applies graph `bindings` before node execution.
- Supports `flowNodes` for loop and branch behavior.

### 4.3 `service/entity/runner.py`

- `RunnerLoader` dispatches by id to an agent or workflow.
- `persistence()` writes run outputs and computes configured metrics.

### 4.4 `service/meta/loader.py`

- `MetaLoader.load/loads/dump/delete` manages JSON files in `meta/*`.
- IDs are derived from file names.

## 5. Runtime Metadata Rules

### 5.1 Agents (`meta/agents/*.json`)

Common runtime fields:

- `name`, `type`, `inputs`, `outputs`
- `model`, `prompt_template` for LLM
- `process` for PGM
- optional `tools`, `sandbox`, `engine`, `persistence`

### 5.2 Graphs (`meta/graphs/*.json`)

Common runtime fields:

- `name`, `description`
- `nodes`, `edges`
- `bindings`
- optional `flowNodes` and `metrics`

### 5.3 LLMs / Tools / Experiments

- LLM files define provider and model endpoint settings.
- Tool files define function parameters and executable code.
- Experiment files define `runner_id`, dataset, status, and progress.

## 6. Plugin System

Plugins are loaded through `plugin/plugin_loader.py` and consumed via `get_plugin(name)`.
Important built-ins:

- PGM sandbox executor
- Memory/Postgres checkpointer
- Metrics calculation plugin

## 7. Coding Guidelines

### 7.1 Language and style

- Use Python 3.11+.
- Follow PEP 8.
- Prefer explicit naming and small focused functions.
- Add type hints when practical.

### 7.2 Metadata and workflow conventions

- Keep IDs stable and filename-aligned.
- Use `wf_` for top-level workflows and `sg_` for subgraphs.
- Prefer `flowNodes.loop` over legacy `SUB` for new pipelines.
- Keep state keys flat and predictable.

### 7.3 Safety and maintainability

- Keep PGM code deterministic and minimal.
- Avoid broad imports in sandboxed code.
- Never commit virtual environments, model binaries, or cache artifacts.

## 8. Development and Validation

- Start service with `start.bat` (Windows) or `python -m ui.app`.
- Validate workflows in the Graph editor test panel before batch experiments.
- After experiment runs, verify `result/<exp_id>/states.json`.

## 9. Related Documentation

- `README.md` for quick start and complete index.
- `doc/EXPERIMENT_GUIDE.md` for startup, schema, and experiment operations.
- `doc/MANUAL.md` for UI walkthrough with screenshots.
- `doc/AUTOGEN_SKILL.md` for generation-oriented workflow authoring.

