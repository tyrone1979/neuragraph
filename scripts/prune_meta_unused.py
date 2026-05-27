#!/usr/bin/env python3
"""Remove JSON keys from meta/ that runtime code does not read."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META = ROOT / "meta"

AGENT_KEYS = frozenset({
    "name", "type", "inputs", "outputs", "process", "model", "prompt_template",
    "persistence", "sandbox", "engine", "idx", "tools", "output_parse",
    "default_labels", "created_at", "updated_at",
})
OUTPUT_KEYS = frozenset({"name", "type", "parse_as"})
PROMPT_KEYS = frozenset({"system", "human", "description"})
PERSISTENCE_KEYS = frozenset({"file_path", "file_type", "columns"})

GRAPH_KEYS = frozenset({
    "name", "description", "nodes", "edges", "flowNodes", "bindings", "metrics",
    "created_at", "updated_at",
})
FLOW_NODE_KEYS = frozenset({"kind", "name", "subgraphId", "loopConfig", "conditions"})
LOOP_CONFIG_KEYS = frozenset({
    "loopType", "array", "itemBindings", "mergeKeys", "mergeAliases",
    "scalarItemField", "streamFields", "streamIncludeMergeKeys", "count",
})
BRANCH_COND_KEYS = frozenset({"label", "field", "op", "value", "condition"})
METRICS_SPEC_KEYS = frozenset({"type", "expected", "predicted", "prefix"})
METRIC_REF_KEYS = frozenset({"from", "field", "expr"})

LLM_KEYS = frozenset({
    "type", "model", "base_url", "api_key", "temperature", "max_tokens",
    "extra_body", "metadata", "created_at", "updated_at",
})

TOOL_KEYS = frozenset({
    "name", "description", "parameters", "code", "sandbox", "engine",
    "created_at", "updated_at",
})

EXP_KEYS = frozenset({
    "dataset", "runner_type", "runner_id", "runner_display", "samples", "exp_id",
    "name", "status", "progress", "created_at", "updated_at", "history",
    "model", "prompt_template", "config",
})


def _prune_dict(d: dict, allowed: frozenset, nested: dict[str, frozenset] | None = None) -> dict:
    out = {}
    nested = nested or {}
    for k, v in d.items():
        if k not in allowed:
            continue
        if k in nested and isinstance(v, dict):
            v = {nk: nv for nk, nv in v.items() if nk in nested[k]}
            if not v:
                continue
        if v is None:
            continue
        if v == {} or v == []:
            continue
        out[k] = v
    return out


def prune_agent(data: dict) -> dict:
    out = _prune_dict(data, AGENT_KEYS)
    if "outputs" in out and isinstance(out["outputs"], dict):
        out["outputs"] = {k: v for k, v in out["outputs"].items() if k in OUTPUT_KEYS}
    if "prompt_template" in out and isinstance(out["prompt_template"], dict):
        out["prompt_template"] = {
            k: v for k, v in out["prompt_template"].items() if k in PROMPT_KEYS
        }
    if "persistence" in out and isinstance(out["persistence"], dict):
        p = {k: v for k, v in out["persistence"].items() if k in PERSISTENCE_KEYS}
        if p:
            out["persistence"] = p
        else:
            out.pop("persistence", None)
    if out.get("tools") == []:
        out.pop("tools", None)
    return out


def prune_graph(data: dict) -> dict:
    out = _prune_dict(data, GRAPH_KEYS)
    flow = out.get("flowNodes")
    if isinstance(flow, dict):
        pruned_flow = {}
        for nid, fn in flow.items():
            if not isinstance(fn, dict):
                continue
            pfn = {k: v for k, v in fn.items() if k in FLOW_NODE_KEYS}
            lc = pfn.get("loopConfig")
            if isinstance(lc, dict):
                pfn["loopConfig"] = {k: v for k, v in lc.items() if k in LOOP_CONFIG_KEYS}
            conds = pfn.get("conditions")
            if isinstance(conds, list):
                pfn["conditions"] = [
                    {k: v for k, v in c.items() if k in BRANCH_COND_KEYS}
                    for c in conds
                    if isinstance(c, dict)
                ]
            pruned_flow[nid] = pfn
        out["flowNodes"] = pruned_flow
    metrics = out.get("metrics")
    if isinstance(metrics, list):
        pm = []
        for spec in metrics:
            if not isinstance(spec, dict):
                continue
            ps = {k: v for k, v in spec.items() if k in METRICS_SPEC_KEYS}
            for side in ("expected", "predicted"):
                if isinstance(ps.get(side), dict):
                    ps[side] = {
                        k: v for k, v in ps[side].items() if k in METRIC_REF_KEYS
                    }
            pm.append(ps)
        out["metrics"] = pm
    return out


def prune_llm(data: dict) -> dict:
    return _prune_dict(data, LLM_KEYS)


def prune_tool(data: dict) -> dict:
    return _prune_dict(data, TOOL_KEYS)


def prune_exp(data: dict) -> dict:
    out = _prune_dict(data, EXP_KEYS)
    out.pop("id", None)
    if not out.get("model"):
        out.pop("model", None)
    if not out.get("prompt_template"):
        out.pop("prompt_template", None)
    if not out.get("history"):
        out.pop("history", None)
    if not out.get("config"):
        out.pop("config", None)
    return out


def process_dir(sub: str, prune_fn, skip_backup: bool = True) -> int:
    path = META / sub
    if not path.is_dir():
        return 0
    n = 0
    for f in sorted(path.glob("*.json")):
        if skip_backup and "backup" in f.parts:
            continue
        raw = json.loads(f.read_text(encoding="utf-8"))
        cleaned = prune_fn(raw)
        text = json.dumps(cleaned, indent=2, ensure_ascii=False) + "\n"
        if text != f.read_text(encoding="utf-8"):
            f.write_text(text, encoding="utf-8")
            n += 1
    return n


def main() -> None:
    counts = {
        "agents": process_dir("agents", prune_agent),
        "graphs": process_dir("graphs", prune_graph),
        "llms": process_dir("llms", prune_llm),
        "tools": process_dir("tools", prune_tool),
        "exps": process_dir("exps", prune_exp),
    }
    print("pruned files:", counts)


if __name__ == "__main__":
    main()
