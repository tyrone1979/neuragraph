# NeuraGraph Operations Guide

This document merges startup instructions, runtime metadata schema, metrics, experiment operations, and the **optimization pipeline**.

Related: [SUPPLEMENTARY.md](SUPPLEMENTARY.md) · [MANUAL.md](MANUAL.md) (UI walkthrough with screenshots) · [CODE_WIKI.md](CODE_WIKI.md) · [CHAT_COMMANDS.md](CHAT_COMMANDS.md)

---

## 1. Startup

### 1.1 Recommended startup (Windows)

```powershell
.\start.bat
```

The app is available at **http://127.0.0.1:5001**. Plugin sandboxes listen on port **5002** (and related ports).

### 1.2 Manual startup

```powershell
.\venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
python -m ui.app
```

### 1.3 Common startup issues

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError: flask_cors` | `py -m pip install flask-cors` |
| Missing deps | `py -m pip install -r requirements.txt` |
| Import path errors | Launch from repository root |
| PubTator HTTPS on Windows | Ensure `requests` and `certifi` installed |

### 1.4 Refresh documentation screenshots

With the server running:

```powershell
py -3 scripts/refresh_manual_screenshots.py
py -3 scripts/capture_supplemental_screenshots.py
```

Output: `doc/images/*.png` (referenced by `MANUAL.md`).

---

## 2. Runtime Metadata Schema

Only fields listed here are required at runtime. IDs equal filenames without `.json`.

### 2.1 Agents (`meta/agents/<id>.json`)

| Field | Required | Notes |
|-------|----------|-------|
| `name`, `type` | ✓ | `LLM` \| `PGM` \| `SUB` (legacy) |
| `inputs` | ✓ | State keys read by agent |
| `outputs.name`, `outputs.type` | ✓ | State key written; optional `parse_as` |
| `model`, `prompt_template` | LLM | `model` = `meta/llms/<id>` stem |
| `process` | PGM | Python; assign `__result__` |
| `tools` | optional | Tool ids for LLM function calling |
| `sandbox`, `engine`, `persistence` | optional | PGM / Flair |

**Version snapshots**: `meta/agent_versions/<agent_id>/<version>.json` — created on save; used by optimization pinning.

### 2.2 Graphs (`meta/graphs/<id>.json`)

| Field | Required | Notes |
|-------|----------|-------|
| `name`, `description` | ✓ | |
| `nodes`, `edges` | ✓ | Include `START`, `END` |
| `bindings` | optional | `{{ START.field }}` per node |
| `flowNodes` | optional | `loop` or `branch` controllers |
| `metrics` | optional | Post-run P/R/F1 (see §3) |
| `agentVersions` | optional | Map `agent_id → version` for pinned snapshots |

**Naming**: `wf_*` top-level workflows; `sg_*` subgraphs (loop bodies). Optimization creates variants like `wf_cid_re_llm_linear_opt_20260529_143039_r1`.

### 2.3 Loop config (`flowNodes.<node>.loopConfig`)

| Field | Default | Notes |
|-------|---------|-------|
| `loopType` | `foreach` | |
| `array` | — | e.g. `{{ pairs }}` |
| `itemBindings` | — | Per-iteration bindings |
| `mergeKeys`, `mergeAliases` | optional | Merge loop outputs |
| `scalarItemField`, `streamFields` | optional | Streaming merge |

### 2.4 LLMs (`meta/llms/<id>.json`)

`type`, `model`, `base_url`, `api_key`; optional `temperature`, `max_tokens`, `extra_body`, `api_version`.

### 2.5 Tools (`meta/tools/<id>.json`)

`name`, `description`, `parameters` (JSON schema), `code`; optional `sandbox`, `engine`.

Version snapshots: `meta/tool_versions/<tool_id>/`.

### 2.6 Experiments (`meta/exps/<id>.json`)

| Field | Notes |
|-------|-------|
| `runner_id`, `runner_type` | Workflow or agent id |
| `dataset` | **Legacy** single dataset; still written for compatibility |
| `test_dataset` | Held-out evaluation CSV under `tests/<runner_id>/` |
| `tuning_dataset` | CSV used during optimization / refine rounds |
| `dataset_split` | Optional auto-split config `{ source, ratio, seed, ... }` |
| `samples`, `status`, `progress` | Runtime state |
| `optimization_flow_steps` | Step statuses for UI wizard |
| `name`, `exp_id`, `created_at`, `updated_at` | Metadata |

**Legacy fallback**: if only `dataset` is set, both test and tuning resolve to that file.

**Tree list grouping** (UI): Family → Version (runner variant) → Dataset pair → Experiment rows.

---

## 3. Metrics in Experiments

Configure metrics on workflow graphs using the `metrics` array. Computed after each sample by `RunnerLoader.persistence` via the metrics plugin — no in-graph `eval_metrics` node is required for final scoring.

### 3.1 Example: relation pairs

```json
"metrics": [
  {
    "type": "relation_pairs",
    "expected": { "from": "input", "field": "gold_relations" },
    "predicted": { "from": "state", "field": "relations" }
  }
]
```

### 3.2 Supported types

| Type | Use case |
|------|----------|
| `entity_dict` | NER span dict comparison |
| `relation_pairs` | Head–tail relation sets |

### 3.3 Relation normalization

For MeSH / PubTator pipelines, `service/relation_normalize.py` normalizes relation identifiers before metric comparison. Graph-level metrics in `utils/workflow_metrics.py` preserve eval-agent F1 when recomputing `rel_*` fields.

### 3.4 Formulas (BC5CDR-style)

```
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1        = 2 * P * R / (P + R)
```

Report both micro and macro when comparing methods.

---

## 4. Experiment Workflow (UI Wizard)

The experiment page (`/exp/<exp_id>`) is a **4-step wizard**:

| Step | Tab | Actions |
|------|-----|---------|
| 1 | Configure | Runner, test/tuning CSV, auto-split, preview |
| 2 | Baseline | Run test set → baseline report |
| 3 | Tuning & Optimize | Tuning baseline → tuning report → optimize rounds |
| 4 | Optimized Test | Run optimized workflow on test set → compare reports |

Screenshots: `doc/images/page_exp_*.png` — see [MANUAL.md §5](MANUAL.md#5-experiment-and-optimization).

### 4.1 Create an experiment

**UI**: `/exp/new` — select runner, datasets, click **Next** (saves via `POST /exp/api/save`).

**JSON** (`meta/exps/<uuid>.json`):

```json
{
  "runner_id": "wf_cid_re_llm_linear",
  "runner_type": "graph",
  "test_dataset": "test.csv",
  "tuning_dataset": "tuning.csv",
  "dataset": "test.csv",
  "status": "pending"
}
```

**Chat**: `/create experiment wf_cid_re_llm_linear test.csv graph`

### 4.2 Auto-split datasets

Enable **Auto split** in Configure step, or call:

```
POST /testset/api/split
```

Uses `service/dataset_cid.py` for stratified CID splits. Config stored in `dataset_split` on the experiment.

### 4.3 Batch execution (baseline / tuning / final)

| Action | API |
|--------|-----|
| Run all samples (SSE) | `GET /stream/run/<exp_id>` |
| Optimization step (SSE) | `POST /exp/api/<exp_id>/optimization-step/<step>/start` |
| Full optimize loop | `POST /exp/api/optimize-loop/start` |
| Preflight / resume state | `GET /exp/api/<exp_id>/optimization-preflight` |

Progress events update `optimization_flow_steps` and the UI step bars (`optimizationFlowBaseline`, etc.).

### 4.4 Reports

| Output | Source |
|--------|--------|
| Baseline report | `GET /stream/report/<exp_id>` or optimization step `baseline_test_report` |
| Tuning report | Step `baseline_tuning_report` |
| Optimized report | Step `final_test_report` |
| Comparison | UI `#optimizationCompare` from preflight API |

Reports are generated by `report_experiment` / `report_experiment_tool` agents. Markdown stored under `result/<exp_id>/`.

### 4.5 Read raw outputs

| Path | Content |
|------|---------|
| `result/<exp_id>/states.json` | Per-sample final state + `metrics` |
| `meta/exps/<exp_id>.json` | Config + optimization metadata |

---

## 5. Optimization Pipeline

Implemented in:

- `service/experiment_optimize.py` — agent refine loop, candidate/pinned/best experiments
- `service/optimization_pipeline.py` — step orchestration for UI wizard
- `service/optimize_suggestion_filter.py` — filters unsafe LLM patch suggestions
- `scripts/run_optimize_exp.py` — headless CLI runner

### 5.1 Flow steps

| Step ID | Description |
|---------|-------------|
| `baseline_test` | Batch run on **test_dataset** |
| `baseline_test_report` | LLM report from baseline states |
| `baseline_tuning` | Batch run on **tuning_dataset** |
| `baseline_tuning_report` | LLM report from tuning states |
| `optimize_rounds` | `agent_refiner` analyzes reports, patches agents, creates `wf_*_opt_*_rN` graphs, runs candidate experiments |
| `final_test` | Batch run optimized workflow on test set |
| `final_test_report` | Final report + comparison |

### 5.2 Experiment naming conventions

| Prefix / pattern | Meaning |
|------------------|---------|
| `opt_cand_*` | Candidate round experiment |
| `opt_pinned_*` | Pinned best-so-far |
| `opt_best_*` | Declared best run |
| `opt_base_tune_*` | Tuning baseline experiments |
| `wf_*_opt_<timestamp>_rN` | Optimized workflow graph copy |

### 5.3 CLI optimization

```powershell
py -3 scripts/run_optimize_exp.py --exp-id <baseline_exp_id> [--max-updates 3]
```

### 5.4 Chat optimization

```
/optimize <exp_id> [max_updates]
```

---

## 6. PubTator & CID Workflows

| Workflow | Purpose |
|----------|---------|
| `wf_re_pubtator_dev10` | PubTator relation extraction (dev set) |
| `wf_re_pubtator_eval` | PubTator evaluation |
| `wf_cid_re_llm_linear` | CID relation linear LLM pipeline |

Supporting services:

- `service/pubtator_client.py` — fetch/parse/filter PubTator annotations
- `service/relation_normalize.py` — MeSH normalization for metrics
- `service/dataset_cid.py` — build/split tuning CSVs

Agent: `relation_extract_pubtator`, `agent_refiner`, `eval_metrics_relation`.

---

## 7. Validation Checklist

- [ ] Workflow passes single-sample **Test Workflow** in graph editor
- [ ] CSV columns match START inputs and `metrics.expected.field`
- [ ] `test_dataset` and `tuning_dataset` exist under `tests/<runner_id>/`
- [ ] `result/<exp_id>/states.json` contains `metrics` per sample
- [ ] Baseline report renders before starting optimize rounds
- [ ] Optimized workflow id appears in experiment tree under same family

---

## 8. Related Documents

- [README.md](../README.md) — quick start and project layout
- [SUPPLEMENTARY.md](SUPPLEMENTARY.md) — component inventory and evaluation protocol
- [MANUAL.md](MANUAL.md) — detailed UI guide with screenshots
- [CODE_WIKI.md](CODE_WIKI.md) — architecture and coding conventions
- [CHAT_COMMANDS.md](CHAT_COMMANDS.md) — slash command reference
- [AUTOGEN_SKILL.md](AUTOGEN_SKILL.md) — LLM workflow generation reference
