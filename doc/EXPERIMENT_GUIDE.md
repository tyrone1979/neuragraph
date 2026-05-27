# NeuraGraph Operations Guide

This document merges startup instructions, runtime metadata schema, and experiment operations.

## 1. Startup

### 1.1 Recommended startup (Windows)

```powershell
.\start.bat
```

The app should be available at `http://127.0.0.1:5001`.

### 1.2 Manual startup

```powershell
.\venv\Scripts\Activate.ps1
python -m ui.app
```

### 1.3 Common startup issues

- `ModuleNotFoundError: flask_cors` -> `py -m pip install flask-cors`
- missing project dependencies -> `py -m pip install -r requirements.txt`
- import path issues -> launch from repository root

## 2. Runtime Metadata Schema

Only fields listed in this section are required at runtime.

### 2.1 Agents (`meta/agents/<id>.json`)

- `name`, `type`
- `inputs`
- `outputs.name`, `outputs.type`, optional `outputs.parse_as`
- LLM-only: `model`, `prompt_template.system`, `prompt_template.human`, optional `tools`
- PGM-only: `process`
- optional: `sandbox`, `engine`, `persistence`, `output_parse`, `default_labels`, `idx`

### 2.2 Graphs (`meta/graphs/<id>.json`)

- `name`, `description`
- `nodes`, `edges`
- optional `bindings`
- optional `flowNodes` (`kind: loop | branch`)
- optional `metrics` (post-run evaluation configuration)

### 2.3 Loop config (`flowNodes.<node>.loopConfig`)

- `loopType` (`foreach` default)
- `array` (for example `{{ pairs }}`)
- `itemBindings`
- optional `mergeKeys`, `mergeAliases`, `scalarItemField`, `streamFields`

### 2.4 LLMs (`meta/llms/<id>.json`)

- `type`, `model`, `base_url`, `api_key`
- optional `temperature`, `max_tokens`, `extra_body`, `metadata`

### 2.5 Tools (`meta/tools/<id>.json`)

- `name`, `description`
- `parameters` (JSON schema)
- `code`
- optional `sandbox`, `engine`

### 2.6 Experiments (`meta/exps/<id>.json`)

- `runner_id`, `runner_type`, `dataset`
- `samples`, `status`, `progress`
- `name`, `exp_id`, `created_at`, `updated_at`

## 3. Metrics in Experiments

Configure metrics on workflow graphs using the `metrics` array.
Metrics are computed after sample execution by `RunnerLoader.persistence`.
No in-graph `eval_metrics` node is required for final report scoring.

Example:

```json
"metrics": [
  {
    "type": "relation_pairs",
    "expected": { "from": "input", "field": "gold_relations" },
    "predicted": { "from": "state", "field": "relations" }
  }
]
```

Supported metric types:

- `entity_dict`
- `relation_pairs`

## 4. Experiment Workflow

### 4.1 Create an experiment

Create a file in `meta/exps/` or use UI (`/exp/new`) with:

- workflow id (`runner_id`)
- `runner_type` as `graph`
- dataset CSV filename under `tests/<runner_id>/`

### 4.2 Run batch execution

- UI: start from experiment page
- API: `GET /stream/run/<exp_id>`

### 4.3 Read outputs

- detailed states: `result/<exp_id>/states.json`
- generated report stream: `GET /stream/report/<exp_id>`

## 5. BC5CDR Evaluation Notes

For BC5CDR-style evaluation:

- Task 1: Chemical NER
- Task 2: Disease NER
- Task 3: CID relation extraction

Core metrics:

```
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2 * Precision * Recall / (Precision + Recall)
```

Use both micro and macro reporting when comparing methods.

## 6. Recommended Validation Checklist

- workflow runs successfully for at least one sample in UI test mode
- all required CSV columns match graph START inputs and metric gold fields
- expected and predicted fields in `metrics` exist in input/state
- `result/<exp_id>/states.json` contains `metrics` objects per sample

## 7. Related Documents

- `README.md` for quick start and index
- `doc/CODE_WIKI.md` for architecture and coding conventions
- `doc/MANUAL.md` for UI walkthrough with screenshots
- `doc/AUTOGEN_SKILL.md` for generation-oriented authoring guidance
