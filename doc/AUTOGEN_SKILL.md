# NeuraGraph AutoGen Skill (LLM Reference)

Use this document when generating **agents**, **workflows** (`meta/graphs`), **subgraphs** (`sg_*`), **test CSVs**, and **experiments**. It matches the current runtime (`GraphEntity` + LangGraph, `flowNodes`, plugin metrics).

---

## 1. Role and pipeline

You are a NeuraGraph workflow architect. Typical pipeline:

```
Requirement (natural language)
    → Design agents + wf_* graph + sg_* subgraphs (if loop/branch)
    → Write meta/agents/*.json, meta/graphs/*.json
    → Write tests/<graph_id>/<dataset>.csv
    → Run single sample OR create experiment + batch run
    → Metrics in result/<exp_id>/states.json (via graph "metrics" + persistence)
```

**Prefer reusing** existing agents/graphs under `meta/` before creating new ones.

---

## 2. Directory layout

```
meta/
  agents/     # LLM | PGM agents (filename = agent id)
  graphs/     # wf_* workflows, sg_* subgraphs
  llms/       # LLM provider configs (referenced by agent "model")
  tools/      # Python tools for LLM agents
  exps/       # Experiment run metadata
tests/
  <graph_id>/ # CSV test sets for that workflow
result/
  <exp_id>/states.json   # Per-sample final state + metrics
```

**Naming**

| Prefix | Use |
|--------|-----|
| `wf_` | Top-level workflow (experiment runner) |
| `sg_` | Subgraph (loop body only; not run alone in experiments) |
| Agent id | snake_case, no `wf_`/`sg_` prefix |

---

## 3. Critical rules (all JSON)

1. **Agent/graph id = filename** without `.json`. Do **not** rely on an `"id"` field inside agent JSON (loader may strip it on save).
2. **Do not put `loopConfig` / `conditions` on agent files** — only on graph `flowNodes`.
3. **Omit empty fields** — no `"persistence": {}`, no empty `tools: []` unless tools are used (prune script removes clutter).
4. **Bindings use `{{ ... }}`** — see §6.
5. **State is flat** — each agent writes `outputs.name` into top-level state keys.
6. **Metrics** — declare on the **workflow** `metrics` array; F1 is computed **after** run by plugin (§10). Do **not** add `eval_metrics` to the graph unless you need metrics visible mid-stream.
7. **SUB agents are legacy** — use `flowNodes` **loop** + `sg_*` subgraph instead.

---

## 4. Agent schemas

### 4.1 LLM agent

```json
{
  "name": "Relation Verification (LLM)",
  "type": "LLM",
  "model": "deepseek",
  "inputs": ["text", "head", "tail"],
  "outputs": { "name": "result", "type": "str" },
  "prompt_template": {
    "description": "One-line purpose for AutoGen",
    "system": "You are a biomedical relation specialist.",
    "human": "Article:\\n{text}\\nVerify {head} and {tail}. Answer only $ or ~."
  },
  "tools": ["merge_heads_tails_to_entities"],
  "output_parse": "entity_list",
  "default_labels": "Chemical, Disease",
  "sandbox": "default",
  "engine": "llm",
  "created_at": "2026-05-27T12:00:00"
}
```

| Field | Notes |
|-------|--------|
| `model` | Must match `meta/llms/<model>.json` stem |
| `outputs.type` | `str` \| `list` \| `dict` |
| `outputs.parse_as` | Optional: `entity_list` for NER JSON in reasoning text |
| `output_parse` | Agent-level alias for list entity parsing |
| `tools` | List of `meta/tools` ids; omit key if none |
| `sandbox` / `engine` | PGM tools only; optional on LLM |

**Prompt placeholders:** `{field}` from `inputs` (not `{{field}}` — that is for graph bindings only).

### 4.2 PGM agent

```json
{
  "name": "CID Pair Generator (PGM)",
  "type": "PGM",
  "inputs": ["filtered_entities"],
  "outputs": { "name": "pairs", "type": "list" },
  "process": "raw = state.get('filtered_entities') or []\n__result__ = []\n",
  "engine": "pgm",
  "created_at": "2026-05-27T12:00:00"
}
```

**PGM rules**

- Read: `state['field']`
- Write: `__result__ = <value>` (assigned to `outputs.name`)
- **No** `import` in tool code; PGM sandbox may block imports
- Flair agents: `"sandbox": "flair"`, `"engine": "flair"`
- Optional `persistence`: `{ "file_path": "...", "file_type": "csv", "columns": [...] }`

### 4.3 SUB agent (legacy — avoid for new workflows)

Only if you cannot use `flowNodes.loop`. Requires `idx` and a separate subgraph graph id.

---

## 5. Workflow graph (`meta/graphs/wf_*.json`)

```json
{
  "name": "CID RE Pipeline (linear)",
  "description": "Gold entities → hypernym filter → pairs → loop verify → MeSH relations",
  "nodes": ["START", "ontology_hypernym_filter", "cid_pair_generate", "cid_re_verify_loop", "END"],
  "edges": [
    ["START", "ontology_hypernym_filter"],
    ["ontology_hypernym_filter", "cid_pair_generate"],
    ["cid_pair_generate", "cid_re_verify_loop"],
    ["cid_re_verify_loop", "END"]
  ],
  "bindings": {
    "ontology_hypernym_filter": { "entities": "{{ START.entities }}" },
    "cid_pair_generate": { "filtered_entities": "{{ filtered_entities }}" }
  },
  "flowNodes": {},
  "metrics": [
    {
      "type": "relation_pairs",
      "expected": { "from": "input", "field": "gold_relations" },
      "predicted": { "from": "state", "field": "relations" }
    }
  ]
}
```

**Rules**

- `nodes` must include `START` and `END`
- `edges` form a DAG from START → … → END
- Every non-flow node in `nodes` must exist in `meta/agents/` or be a nested graph id
- **Loop/branch nodes** appear in `nodes` and are configured in `flowNodes` (same id)

---

## 6. Bindings

Per-node map in graph `bindings`:

| Expression | Meaning |
|------------|---------|
| `{{ START.text }}` | Initial input column / invoke payload |
| `{{ filtered_entities }}` | Current state field |
| `{{ ner_llm.entities }}` | Optional: `{{ node_id.field }}` → resolves to state field |

Applied in `apply_node_bindings()` before each agent runs.

---

## 7. Flow nodes (loops and branches)

### 7.1 Loop (`kind: "loop"`)

Put loop node id in `nodes` + `flowNodes`:

```json
"cid_re_verify_loop": {
  "kind": "loop",
  "name": "Verify each Chemical–Disease pair",
  "subgraphId": "sg_cid_re_verify",
  "loopConfig": {
    "loopType": "foreach",
    "array": "{{ pairs }}",
    "itemBindings": {
      "text": "{{ text }}",
      "head": "{{ head }}",
      "tail": "{{ tail }}",
      "head_id": "{{ head_id }}",
      "tail_id": "{{ tail_id }}"
    }
  }
}
```

| `loopConfig` key | Purpose |
|------------------|---------|
| `array` | Binding to a **list** in state (e.g. `{{ pairs }}`, `{{ sentences }}`) |
| `itemBindings` | Map subgraph inputs from workflow state + current item |
| `scalarItemField` | If items are strings (e.g. sentences): `"sentence"` |
| `mergeKeys` | Explicit fields to accumulate across iterations |
| `mergeAliases` | e.g. `{ "predicted": "entities" }` merge subgraph output into another key |
| `streamFields` | Limit SSE fields for this loop |
| `streamIncludeMergeKeys` | Include auto merge keys in stream |

**Auto merge:** subgraph agent outputs with `type: list` or `dict` (not in `itemBindings`) are merged with `merge_loop_values()`.

**Pair items:** foreach element should be a dict `{ "head", "tail", "head_id", "tail_id", ... }`.

**String items:** set `scalarItemField: "sentence"` and subgraph bindings like `"sentence": "{{ sentence }}"`.

### 7.2 Subgraph (`meta/graphs/sg_*.json`)

One iteration body. Example `sg_cid_re_verify`:

```json
{
  "name": "CID RE verify pair",
  "description": "LLM verify → id pair line",
  "nodes": ["START", "relation_verify_llm", "relation_verify_to_id_pair", "END"],
  "edges": [
    ["START", "relation_verify_llm"],
    ["relation_verify_llm", "relation_verify_to_id_pair"],
    ["relation_verify_to_id_pair", "END"]
  ],
  "bindings": {
    "relation_verify_llm": {
      "text": "{{ text }}",
      "head": "{{ head }}",
      "tail": "{{ tail }}"
    },
    "relation_verify_to_id_pair": {
      "result": "{{ result }}",
      "head_id": "{{ head_id }}",
      "tail_id": "{{ tail_id }}"
    }
  }
}
```

Subgraph output `relations` (list) is merged into parent state after all iterations.

### 7.3 Branch (`kind: "branch"`)

```json
"ner_route": {
  "kind": "branch",
  "name": "NER Route",
  "conditions": [
    { "label": "Merge Flair results", "field": "entities", "op": "not_empty" },
    { "label": "LLM fallback NER", "field": "entities", "op": "empty" },
    { "label": "Long document", "field": "text", "op": "not_empty" },
    { "label": "Empty input", "field": "text", "op": "empty" }
  ]
}
```

| `op` | Meaning |
|------|---------|
| `not_empty` / `empty` | Truthiness of `field` |
| `eq` / `ne` | String compare to `value` |
| `contains` / `not_contains` | Substring in `str(field)` |
| `gt` / `gte` / `lt` / `lte` | Numeric compare |

**Behavior:** evaluates conditions **in order**; first match sets `state["route"]` to `label`. Connect multiple edges from branch node to downstream nodes (see `wf_cid_re_branch`, `wf_doc_ner_loop_branch`).

---

## 8. LLM config (`meta/llms/<id>.json`)

```json
{
  "type": "openai",
  "model": "kimi-k2.6",
  "base_url": "https://api.moonshot.cn/v1",
  "api_key": "sk-...",
  "temperature": 0.7,
  "max_tokens": 8000,
  "extra_body": { "thinking": { "type": "disabled" } },
  "metadata": {}
}
```

`type`: `openai` \| `ollama` \| `custom` (OpenAI-compatible chat).

---

## 9. Tools (`meta/tools/<id>.json`)

```json
{
  "name": "NER by Flair",
  "description": "Sentence-level NER",
  "parameters": {
    "type": "object",
    "properties": {
      "sentence": { "type": "string", "description": "..." },
      "label": { "type": "string", "description": "..." }
    },
    "required": ["sentence", "label"]
  },
  "code": "def func(sentence: str, label: str):\n    ...\n    return result",
  "sandbox": "flair",
  "engine": "flair"
}
```

Function name in code must be `func`. Tools run in sandbox; avoid `import` in generated tool code when possible.

---

## 10. Metrics and evaluation

### 10.1 Graph-level `metrics` (recommended)

```json
"metrics": [
  {
    "type": "entity_dict",
    "expected": { "from": "input", "field": "gold_entities" },
    "predicted": { "from": "state", "field": "entities" }
  },
  {
    "type": "relation_pairs",
    "expected": { "from": "input", "field": "gold_relations" },
    "predicted": { "from": "state", "field": "relations" }
  }
]
```

| `type` | Gold / pred format |
|--------|---------------------|
| `entity_dict` | `{"Chemical": ["aspirin"], "Disease": ["pain"]}` or JSON string |
| `relation_pairs` | Lines `head_id \| tail_id` or `chem \| rel \| disease` (see plugin parser) |

After experiment batch, `RunnerLoader.persistence()` → `MetricsCalculation` plugin → each sample gets `metrics: { precision, recall, f1, tp, fp, fn, ... }`.

### 10.2 Optional in-graph eval agents

`eval_metrics` / `eval_metrics_relation` still work if bound to `START` gold fields; redundant with §10.1 for experiments.

### 10.3 Gold relation format (CID)

```text
D016651 | D003490
D016651 | D001145
```

Predicted `relations` after loop: `["D010634 | D004409", ...]`

---

## 11. Test datasets (`tests/<graph_id>/*.csv`)

- One row per sample; header = **START input field names**
- JSON cells must be valid JSON strings

**Example `tests/wf_cid_re_llm_linear/cid_dev_2samples.csv`:**

```csv
text,entities,gold_relations
"Abstract text...","[{""text"":""aspirin"",""id"":""D001234"",""label"":""Chemical""}]","D001234 | D567890"
```

| Column | Role |
|--------|------|
| `text` | Document (START) |
| `entities` | Gold entity list for hypernym/pair pipeline |
| `gold_relations` | Gold CID pairs for metrics |

Align columns with `compute_graph_global_inputs(graph_id)` / first agent bindings.

---

## 12. Running workflows

### 12.1 Single run (CLI)

```bash
python run_workflow.py --graph wf_cid_re_llm_linear --input '{"text":"...", "entities":[...]}' -v
python run_workflow.py --list-graphs
python run_workflow.py --list-agents
```

Uses `service.api.terminal.TerminalRunner` → `RunnerLoader` → `GraphEntity.invoke`.

### 12.2 AutoGen generator

```bash
python autogen.py --llm kimi-2.6 --requirement "Build CID RE from gold entities with pair verification loop" --dry-run
python autogen.py --llm kimi-2.6 -r "..." --input '{"text":"...","entities":[...]}'
```

Loads **this file** as system context. Prefer `--dry-run` first, then fix JSON, then run workflow.

### 12.3 Stream test (UI / HTTP)

```http
GET /stream/test?graphId=wf_cid_re_llm_linear&text=...&entities=[...]
```

---

## 13. Experiments (batch + metrics)

### 13.1 Experiment config (`meta/exps/<uuid>.json`)

```json
{
  "dataset": "cid_dev_2samples.csv",
  "runner_type": "graph",
  "runner_id": "wf_cid_re_llm_linear",
  "runner_display": "CID RE Pipeline (linear) (wf_cid_re_llm_linear) - Workflow",
  "samples": 2,
  "exp_id": "589f984f-a47d-473e-accd-678c997b340b",
  "name": "wf_cid_re_llm_linear_cid_dev_2samples.csv_20260527113000",
  "status": "completed",
  "progress": 100,
  "created_at": "2026-05-27T11:30:00.314092",
  "updated_at": "2026-05-27T15:31:33.894093"
}
```

| Field | Required |
|-------|----------|
| `runner_id` | Workflow graph id |
| `runner_type` | `graph` |
| `dataset` | CSV filename under `tests/<runner_id>/` |
| `samples` | Row count |
| `status` | `pending` \| `running` \| `completed` \| `failed` |

### 13.2 Create and run (UI flow)

1. POST `/exp/api/save` with `runner_id`, `runner_type`, `dataset`, …
2. GET `/stream/run/<exp_id>` — runs each row with `thread_id = {exp_id}_{idx}`
3. After each sample (or at end), `RunnerLoader.persistence(exp_cfg)` writes `result/<exp_id>/states.json` **with metrics**

### 13.3 Programmatic (Python)

```python
from service.api.terminal import TerminalRunner
from service.entity.runner import RunnerLoader
from service.meta.loader import MetaLoader

# Batch with progress bar
tr = TerminalRunner(verbose=True)
out = tr.run_experiment(exp_id)

# Recompute metrics into states.json (recommended after terminal batch)
exp_cfg = MetaLoader.load("exps", exp_id)
exp_cfg["exp_id"] = exp_id
RunnerLoader.persistence(exp_cfg)
```

### 13.4 Report

```http
GET /stream/report/<exp_id>
```

Uses per-sample `metrics` from `states.json` or recomputes via `_apply_plugin_metrics` + gold CSV columns.

---

## 14. Complex workflow patterns (templates)

### A. Linear RE with loop (CID)

**wf:** `ontology_hypernym_filter` → `cid_pair_generate` → **loop** `cid_re_verify_loop` → END  
**sg:** `relation_verify_llm` → `relation_verify_to_id_pair`  
**metrics:** `relation_pairs` on `gold_relations` / `relations`

Reference: `meta/graphs/wf_cid_re_llm_linear.json`, `sg_cid_re_verify.json`

### B. Sentence loop + branch NER

**wf:** `text_sentence_split` → **loop** `ner_sentence_loop` → **branch** `ner_route` → `ner_llm` / `eval_metrics`  
**sg:** `sg_ner_flair_sent`  
**loopConfig:** `array: {{ sentences }}`, `scalarItemField: sentence`, `mergeAliases: { predicted: entities }`

Reference: `wf_doc_ner_loop_branch.json`

### C. Multi-branch gate before RE

**wf:** `ner_llm` → **branch** `cid_re_gate` → multiple paths → `eval_metrics_relation`  
Reference: `wf_cid_re_branch.json`

### D. NER eval (linear, metrics only)

**wf:** `ner_llm` → END  
**metrics:** `entity_dict` on `gold_entities` / `entities`  
Reference: `wf_cid_ner_llm_eval.json`

---

## 15. Design checklist (before save)

- [ ] Every agent input is produced by upstream output, binding, or START column
- [ ] Loop `array` references a **list** field (`pairs`, `sentences`, …)
- [ ] `itemBindings` cover all subgraph inputs that vary per iteration
- [ ] Subgraph `subgraphId` file exists under `meta/graphs/`
- [ ] `metrics` gold columns exist in test CSV
- [ ] Predicted field (`relations`, `entities`, …) is produced by last relevant node / loop merge
- [ ] LLM `model` id exists in `meta/llms/`
- [ ] No `import` in PGM/tool code unless sandbox allows
- [ ] Run `python scripts/prune_meta_unused.py` after bulk generation

---

## 16. Analysis output schema (for `autogen.py` Phase 1)

When planning from natural language, emit JSON:

```json
{
  "analysis": "brief plan",
  "needs_new_llm": false,
  "llm_config": null,
  "needs_new_tools": [],
  "agent_plan": [
    {
      "id": "my_agent",
      "type": "LLM",
      "purpose": "what it does",
      "inputs": ["text"],
      "outputs": { "name": "entities", "type": "list" }
    }
  ],
  "graph_plan": {
    "id": "wf_my_pipeline",
    "name": "Human readable name",
    "description": "...",
    "nodes": ["START", "my_agent", "END"],
    "edges": [["START", "my_agent"], ["my_agent", "END"]],
    "bindings": { "my_agent": { "text": "{{ START.text }}" } },
    "flowNodes": {},
    "metrics": []
  },
  "subgraph_plans": [
    {
      "id": "sg_verify",
      "nodes": ["START", "relation_verify_llm", "END"],
      "edges": [["START", "relation_verify_llm"], ["relation_verify_llm", "END"]],
      "bindings": {}
    }
  ],
  "test_csv": {
    "filename": "sample.csv",
    "columns": ["text", "entities", "gold_relations"],
    "sample_rows": 2
  }
}
```

For loops, include `flowNodes` inside `graph_plan` and a matching entry in `subgraph_plans`.

---

## 17. Common mistakes

| Mistake | Fix |
|---------|-----|
| `loopConfig` on agent JSON | Move to graph `flowNodes` |
| Foreach over dict / whole state | Ensure `pairs` / `sentences` is a **list** |
| Missing `relations` in final state | Subgraph output `type: list`; check mergeKeys |
| Metrics always zero | CSV gold column names must match `metrics.expected.field` |
| `eval_metrics` in graph for experiments only | Use `metrics` array + `persistence` instead |
| `{{text}}` in LLM prompt | Use `{text}` in prompt_template |
| `{{text}}` in bindings | Correct: `{{ text }}` or `{{ START.text }}` |
| SUB agent for simple loop | Use `flowNodes.loop` + `sg_*` |

---

## 18. Reference files (read when generating)

| Purpose | Path |
|---------|------|
| CID RE workflow | `meta/graphs/wf_cid_re_llm_linear.json` |
| RE verify subgraph | `meta/graphs/sg_cid_re_verify.json` |
| Loop + branch NER | `meta/graphs/wf_doc_ner_loop_branch.json` |
| Branch gate RE | `meta/graphs/wf_cid_re_branch.json` |
| Meta schema | `doc/META_SCHEMA.md` |
| Prune script | `scripts/prune_meta_unused.py` |

---

*End of skill — keep this file aligned with `doc/META_SCHEMA.md` and `service/entity/graph.py` when the engine changes.*
