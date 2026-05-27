# Meta JSON Schema (runtime)

Only fields listed here are read by NeuraGraph at execution time. Other keys are stripped by `scripts/prune_meta_unused.py`.

## Agents (`meta/agents/<id>.json`)

| Field | Used by |
|-------|---------|
| `name`, `type` | UI, `AgentEntity` |
| `inputs` | State schema, prompts, bindings |
| `outputs.name`, `outputs.type`, `outputs.parse_as` | Result field + parsing |
| `model` | LLM agents → `meta/llms/<model>.json` |
| `prompt_template.system`, `.human`, `.description` | LLM prompt; description for AutoGen |
| `process` | PGM code (`__result__ = …`) |
| `tools` | LLM tool ids |
| `sandbox`, `engine` | PGM/tool sandbox routing |
| `persistence` | Optional CSV export (`file_path`, `file_type`, `columns`) |
| `output_parse` | e.g. `entity_list` for NER JSON in reasoning text |
| `default_labels` | Injected as `labels` when missing |
| `idx` | SUB agents (legacy loop) |

**Not stored on agents:** `loopConfig`, `conditions`, `layer`, `granularity` — those belong on graph `flowNodes`.

## Graphs (`meta/graphs/<id>.json`)

| Field | Used by |
|-------|---------|
| `name`, `description` | UI |
| `nodes`, `edges` | `GraphEntity` DAG |
| `bindings` | Per-node `{{ START.field }}` / `{{ field }}` resolution |
| `flowNodes` | Loop / branch nodes (`kind`, `subgraphId`, `loopConfig`, `conditions`) |
| `metrics` | Post-run F1 via `MetricsCalculation` (see below) |

### `flowNodes.*.loopConfig`

| Key | Purpose |
|-----|---------|
| `loopType` | `foreach` (default), `for`, `while` |
| `array` | Binding expr, e.g. `{{ pairs }}` |
| `itemBindings` | Per-iteration subgraph inputs |
| `mergeKeys` | Explicit list fields to accumulate across iterations |
| `mergeAliases` | e.g. `{"predicted": "entities"}` |
| `scalarItemField` | When array items are strings (e.g. `sentence`) |
| `streamFields`, `streamIncludeMergeKeys` | SSE stream filtering |

Merge keys default: subgraph outputs with `type: list` or `dict`, excluding `itemBindings` targets.

### `metrics` (experiment evaluation)

```json
"metrics": [{
  "type": "relation_pairs",
  "expected": { "from": "input", "field": "gold_relations" },
  "predicted": { "from": "state", "field": "relations" }
}]
```

Types: `relation_pairs` | `entity_dict`.  
**No in-graph `eval_metrics` node required** — after each experiment sample, `RunnerLoader.persistence` calls `utils/workflow_metrics.py` → plugin `MetricsCalculation`.

## LLMs (`meta/llms/<id>.json`)

`type` (`openai` | `ollama` | `custom`), `model`, `base_url`, `api_key`, `temperature`, `max_tokens`, `extra_body`, `metadata`.

## Tools (`meta/tools/<id>.json`)

`name`, `description`, `parameters`, `code`, `sandbox`, `engine`.

## Experiments (`meta/exps/<id>.json`)

`runner_id`, `runner_type`, `runner_display`, `dataset`, `samples`, `status`, `progress`, `name`, `exp_id`, `created_at`, `updated_at`, optional `history`.

Results: `result/<exp_id>/states.json` (includes computed `metrics` per sample).
