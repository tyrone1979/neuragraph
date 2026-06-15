from __future__ import annotations

import json
import re
import shutil
import sys
import uuid
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from service.entity.test import TestLoader
from service.meta.loader import MetaLoader
from service.dataset.registry import get_catalog, require_catalog

DEFAULT_RAW_SOURCE = "data/raw/dev.txt"
DEFAULT_RE_RUNNER = "wf_cid_re_llm_linear"


META_DIR = Path(__file__).resolve().parents[2] / "meta"


def _tokenize_goal(text: str) -> set[str]:
    raw = re.findall(r"[a-zA-Z0-9_]+", str(text or "").lower())
    stop = {
        "the",
        "and",
        "for",
        "with",
        "workflow",
        "agent",
        "run",
        "create",
        "build",
        "then",
        "report",
        "compare",
        "vs",
    }
    return {t for t in raw if len(t) >= 3 and t not in stop}


def find_suitable_agents(goal: str, limit: int = 6) -> list[dict[str, Any]]:
    tokens = _tokenize_goal(goal)
    if not tokens:
        return []
    agents = MetaLoader.loads("agents") or []
    scored: list[tuple[int, dict[str, Any]]] = []
    for a in agents:
        aid = str(a.get("id") or "").strip()
        name = str(a.get("name") or "")
        atype = str(a.get("type") or "")
        prompt = json.dumps(a.get("prompt_template") or {}, ensure_ascii=False)
        text = f"{aid} {name} {atype} {prompt}".lower()
        score = 0
        for tk in tokens:
            if tk in text:
                score += 1
        if "flair" in goal.lower() and "flair" in text:
            score += 3
        if "llm" in goal.lower() and "llm" in text:
            score += 2
        if score > 0:
            scored.append((score, {"id": aid, "name": name, "type": atype, "score": score}))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in scored[: max(1, int(limit))]]


def find_suitable_workflow(goal: str) -> dict[str, Any] | None:
    tokens = _tokenize_goal(goal)
    if not tokens:
        return None
    graphs = MetaLoader.loads("graphs") or []
    agents_map = {str(a.get("id") or ""): a for a in (MetaLoader.loads("agents") or [])}
    best: dict[str, Any] | None = None
    best_score = 0
    goal_lower = goal.lower()
    for g in graphs:
        gid = str(g.get("id") or "").strip()
        gname = str(g.get("name") or "")
        nodes = [str(n) for n in (g.get("nodes") or []) if str(n) not in ("START", "END")]
        node_text_parts: list[str] = []
        for n in nodes:
            node_text_parts.append(n)
            a = agents_map.get(n) or {}
            node_text_parts.append(str(a.get("name") or ""))
            node_text_parts.append(str(a.get("type") or ""))
        graph_text = f"{gid} {gname} {' '.join(node_text_parts)}".lower()
        score = 0
        for tk in tokens:
            if tk in graph_text:
                score += 1
        if "flair" in goal_lower and "flair" in graph_text:
            score += 4
        if "llm" in goal_lower and "llm" in graph_text:
            score += 3
        if "ner" in goal_lower and "ner" in graph_text:
            score += 2
        if "chemical" in goal_lower and "chemical" in graph_text:
            score += 2
        if "disease" in goal_lower and "disease" in graph_text:
            score += 2
        if score > best_score:
            best_score = score
            best = {
                "graph_id": gid,
                "name": gname,
                "score": score,
                "matched_nodes": nodes[:8],
            }
    # Require a minimum confidence for automatic reuse.
    if best and best_score >= 4:
        return best
    return None


def md_card(title: str, items: List[Tuple[str, Any]], tips: List[str] | None = None) -> str:
    lines = [f"### {title}"]
    for k, v in items:
        lines.append(f"- **{k}**: {v}")
    if tips:
        lines.append("")
        lines.append("**Next**")
        for t in tips:
            lines.append(f"- {t}")
    return "\n".join(lines)


def render_pins(session: Dict[str, Any]) -> str:
    pins = (session or {}).setdefault("pins", {})
    if not pins:
        return md_card("Pinned Context", [("status", "empty")], ["Use `/pin graph <id>` or `/pin exp <id>`"])
    return md_card(
        "Pinned Context",
        [(k, f"`{v}`") for k, v in pins.items()],
        ["Use `/pin clear` to clear all pins."],
    )


def list_meta(subdir: str, title: str) -> str:
    cfgs = MetaLoader.loads(subdir) or []
    if not cfgs:
        return f"{title}\n- (empty)"
    lines = [title]
    for cfg in sorted(cfgs, key=lambda x: x.get("id", "")):
        cid = cfg.get("id", "")
        name = cfg.get("name", "")
        ctype = cfg.get("type", "")
        extra = f" [{ctype}]" if ctype else ""
        lines.append(f"- `{cid}`{extra} {name}".rstrip())
    return "\n".join(lines)


def show_meta(subdir: str, cid: str, label: str) -> str:
    cfg = MetaLoader.load(subdir, cid)
    if not cfg:
        return f"{label} `{cid}` not found."
    return f"{label} `{cid}`:\n```json\n{json.dumps(cfg, ensure_ascii=False, indent=2)}\n```"


def _parse_kv_tokens(tokens: list[str]) -> dict[str, str]:
    return {k.strip().lower(): v.strip() for k, v in [p.split("=", 1) for p in tokens if "=" in p]}


def _resolve_runner_id(raw: str, pins: dict) -> str:
    return (raw or pins.get("graph") or pins.get("runner_id") or DEFAULT_RE_RUNNER).strip()


def _source_from_kv(kv: dict[str, str]) -> str:
    return (kv.get("source") or DEFAULT_RAW_SOURCE).strip()


def dataset_registry_view(session: dict | None = None) -> str:
    pins = (session or {}).get("pins") or {}
    agent_id = _resolve_runner_id("", pins)
    source = (pins.get("source_dataset") or pins.get("source") or DEFAULT_RAW_SOURCE).strip()
    try:
        status = require_catalog().registry(source, agent_id=agent_id)
    except Exception as ex:
        return f"Failed to load dataset registry: {ex}"
    src = status["source_raw"]
    files = status.get("test_files") or []
    file_lines = [f"`{f['name']}` ({f.get('count', '?')} rows)" for f in files[:8]]
    if len(files) > 8:
        file_lines.append(f"... +{len(files) - 8} more")
    return md_card(
        "Raw / Test Mapping",
        [
            ("source", f"`{src['path']}` ({src['count']} docs)"),
            ("agent", f"`{agent_id}`"),
            ("tests", ", ".join(file_lines) if file_lines else "(no CSV under tests/)"),
        ],
        [
            "`/dataset build full [agent] source=data/raw/dev.txt format=re`",
            "`/dataset build tuning [agent] size=20`",
            "`/run agent dataset_cid_tuning_build {\"size\":20}`",
            "`/dataset extract test <agent> <out.csv> mode=remain|random|stratified|pmids`",
            "Exp: pick tuning/test CSV from tests/<agent_id>/",
        ],
    )


def _format_from_kv(kv: dict[str, str]) -> str:
    return (kv.get("format") or "re").strip()


def dataset_build_full_cmd(runner_id: str, kv: dict[str, str]) -> str:
    agent_id = _resolve_runner_id(runner_id, {})
    source = _source_from_kv(kv)
    output = kv.get("out") or kv.get("output") or ""
    try:
        result = require_catalog().build_full(
            agent_id,
            source=source,
            format=_format_from_kv(kv),
            output_name=output or None,
        )
    except Exception as ex:
        return f"Failed to build structured full dataset: {ex}"
    lines = [
        f"Built structured full dataset `{result['output']}` for agent `{agent_id}`.",
        f"- source: `{result['source']}`",
        f"- rows: {result['count']}",
    ]
    if result.get("mirror"):
        lines.append(f"- mirror: {len(result['mirror'])} extra output(s)")
    return "\n".join(lines)


def dataset_build_tuning_cmd(runner_id: str, kv: dict[str, str]) -> str:
    agent_id = _resolve_runner_id(runner_id, {})
    source = _source_from_kv(kv)
    try:
        size = int(kv.get("size") or 20)
    except ValueError:
        size = 20
    write_remain = kv.get("write_test_remain", "true").lower() not in ("0", "false", "no")
    try:
        result = require_catalog().build_tuning(
            agent_id,
            source=source,
            format=_format_from_kv(kv),
            size=size,
            tuning_out=kv.get("tuning_out") or kv.get("out") or None,
            test_out=kv.get("test_out") or None,
            write_test_remain=write_remain,
        )
    except Exception as ex:
        return f"Failed to build tuning dataset: {ex}"
    lines = [
        f"Built tuning dataset for agent `{agent_id}`.",
        f"- source: `{result['source']}`",
        f"- tuning: `{result['tuning_output']}` ({result['tuning_count']} rows)",
    ]
    if result.get("test_output"):
        lines.append(f"- test remain: `{result['test_output']}` ({result['test_count']} rows)")
    summary = result.get("summary") or {}
    if summary.get("relation_buckets"):
        lines.append(f"- relation buckets: `{json.dumps(summary['relation_buckets'], ensure_ascii=False)}`")
    return "\n".join(lines)


def dataset_extract_test_cmd(runner_id: str, output_name: str, kv: dict[str, str]) -> str:
    if not runner_id or not output_name:
        return "Usage: /dataset extract test <runner_id> <output.csv> [mode=remain|random|stratified|pmids|full] [size=N] [source=dev.txt] [exclude_tuning=<file>] [pmids=a,b] [seed=42]"
    mode = kv.get("mode") or "remain"
    pmids = [p.strip() for p in (kv.get("pmids") or "").split(",") if p.strip()]
    try:
        size = int(kv["size"]) if kv.get("size") else None
    except ValueError:
        size = None
    try:
        seed = int(kv.get("seed") or 42)
    except ValueError:
        seed = 42
    try:
        result = require_catalog().extract_test(
            runner_id,
            _normalize_dataset_name(output_name),
            source=_source_from_kv(kv),
            format=_format_from_kv(kv),
            mode=mode,
            size=size,
            pmids=pmids or None,
            exclude_tuning_file=kv.get("exclude_tuning") or kv.get("exclude") or None,
            exclude_tuning_agent=kv.get("exclude_agent") or kv.get("exclude_runner") or runner_id,
            seed=seed,
        )
    except Exception as ex:
        return f"Failed to extract test dataset: {ex}"
    lines = [
        f"Extracted test dataset `{result['output']}` for `{runner_id}`.",
        f"- mode: `{result['mode']}`",
        f"- rows: {result['count']}",
    ]
    if result.get("exclude_tuning_file"):
        lines.append(f"- excluded tuning: `{result['exclude_tuning_file']}`")
    if result.get("mirror"):
        lines.append(f"- mirror: {len(result['mirror'])} extra output(s)")
    return "\n".join(lines)


def handle_dataset_command(parts: list[str], session: dict) -> str:
    pins = session.setdefault("pins", {})
    if len(parts) == 1:
        return dataset_registry_view(session)

    sub = parts[1].lower()
    if sub in ("status", "show", "registry"):
        return dataset_registry_view(session)

    if sub == "pin" and len(parts) >= 4:
        key = parts[2].lower()
        val = parts[3]
        pin_map = {
            "raw": "source_dataset",
            "source": "source_dataset",
            "full": "structured_full",
            "tuning": "tuning_dataset",
            "test": "test_dataset",
        }
        pin_key = pin_map.get(key)
        if not pin_key:
            return "Usage: /dataset pin raw|tuning|test|full <path>"
        pins[pin_key] = val
        if key == "test":
            pins["dataset"] = val
        return render_pins(session)

    if sub == "build" and len(parts) >= 3:
        target = parts[2].lower()
        runner_id = parts[3] if len(parts) >= 4 and "=" not in parts[3] else ""
        kv = _parse_kv_tokens(parts[3 if runner_id else 4 :])
        if not runner_id:
            runner_id = _resolve_runner_id("", pins)
        if target == "full":
            return dataset_build_full_cmd(runner_id, kv)
        if target == "tuning":
            return dataset_build_tuning_cmd(runner_id, kv)
        return "Usage: /dataset build full|tuning [runner_id] [size=20] [source=dev.txt] [out=...] [test_out=...]"

    if sub == "extract" and len(parts) >= 4 and parts[2].lower() == "test":
        runner_id = parts[3]
        output_name = parts[4] if len(parts) >= 5 else ""
        kv = _parse_kv_tokens(parts[5:])
        return dataset_extract_test_cmd(runner_id, output_name, kv)

    if sub == "list":
        runner_id = parts[2] if len(parts) >= 3 else _resolve_runner_id("", pins)
        tests = TestLoader.get_by_agent(runner_id)
        lines = [f"Datasets for runner `{runner_id}`"]
        for t in tests:
            lines.append(f"- `{t['name']}` ({t.get('count', 0)} rows)")
        try:
            catalog = require_catalog()
            src_path = pins.get("source_dataset") or pins.get("source") or DEFAULT_RAW_SOURCE
            src = catalog.resolve_source(src_path)
            arts = catalog.load_articles(src_path)
            lines.insert(1, f"- `[raw]` `{src.name}` ({len(arts)} docs)")
        except Exception:
            pass
        return "\n".join(lines) if len(lines) > 1 else lines[0] + "\n- (empty)"

    return (
        "Usage:\n"
        "- `/dataset` — registry status (raw / tuning / test)\n"
        "- `/dataset list [runner_id]`\n"
        "- `/dataset build full [runner] [source=dev.txt] [out=cid_dev_full.csv]`\n"
        "- `/dataset build tuning [runner] size=20 [write_test_remain=true]`\n"
        "- `/dataset extract test <runner> <out.csv> mode=remain|random|stratified|pmids|full`\n"
        "- `/dataset pin raw|tuning|test|full <path>`"
    )


def list_datasets() -> str:
    tests_dir = Path(__file__).resolve().parents[2] / "tests"
    if not tests_dir.exists():
        return "Datasets\n- (empty)"
    rows: list[str] = []
    for runner_dir in sorted(tests_dir.iterdir()):
        if not runner_dir.is_dir():
            continue
        for f in sorted(list(runner_dir.glob("*.csv")) + list(runner_dir.glob("*.txt"))):
            rows.append(f"- `{f.name}` (runner: `{runner_dir.name}`)")
    return "Datasets\n- (empty)" if not rows else "Datasets\n" + "\n".join(rows)


def show_dataset(dataset_id: str) -> str:
    did = (dataset_id or "").strip()
    if not did:
        return "Usage: /show dataset <id_or_filename>"
    tests_dir = Path(__file__).resolve().parents[2] / "tests"
    if not tests_dir.exists():
        return f"Dataset `{did}` not found."
    targets = {did, f"{did}.csv", f"{did}.txt"}
    for runner_dir in sorted(tests_dir.iterdir()):
        if not runner_dir.is_dir():
            continue
        for f in runner_dir.iterdir():
            if not f.is_file():
                continue
            if f.name in targets or f.stem == did:
                return md_card(
                    "Dataset",
                    [
                        ("id", f"`{f.stem}`"),
                        ("filename", f"`{f.name}`"),
                        ("runner", f"`{runner_dir.name}`"),
                        ("size_bytes", f.stat().st_size),
                    ],
                )
    return f"Dataset `{did}` not found."


def _normalize_dataset_name(name: str) -> str:
    raw = (name or "").strip()
    if not raw:
        return ""
    if raw.lower().endswith(".csv") or raw.lower().endswith(".txt"):
        return raw
    return f"{raw}.csv"


def _auto_split_dataset_for_runner(
    runner_id: str,
    source_dataset: str,
    *,
    split_ratio: float = 0.8,
    seed: int = 42,
) -> dict[str, Any]:
    source = _normalize_dataset_name(source_dataset)
    if not source.lower().endswith(".csv"):
        raise ValueError("auto split currently supports CSV source datasets only")
    fields, rows = TestLoader.load_by_id_file(runner_id, source)
    row_list = [dict(r) for r in (rows or [])]
    if not row_list:
        raise ValueError(f"source dataset `{source}` has no rows")
    ratio = min(0.95, max(0.05, float(split_ratio)))
    rng = random.Random(int(seed))
    rng.shuffle(row_list)
    split_idx = max(1, min(len(row_list) - 1, int(round(len(row_list) * ratio))))
    tuning_rows = row_list[:split_idx]
    test_rows = row_list[split_idx:]
    stem = Path(source).stem
    suffix = datetime.now().strftime("%Y%m%d%H%M%S")
    tuning_name = f"{stem}__tune_r{int(ratio * 100)}_s{int(seed)}_{suffix}.csv"
    test_name = f"{stem}__test_r{int((1 - ratio) * 100)}_s{int(seed)}_{suffix}.csv"
    TestLoader.save_csv_rows(runner_id, tuning_name, fields, tuning_rows)
    TestLoader.save_csv_rows(runner_id, test_name, fields, test_rows)
    return {
        "tuning_dataset": tuning_name,
        "test_dataset": test_name,
        "dataset_split": {
            "mode": "auto",
            "source_dataset": source,
            "split_ratio": ratio,
            "seed": int(seed),
            "tuning_count": len(tuning_rows),
            "test_count": len(test_rows),
        },
    }


def _try_parse_json_tail(text: str) -> Dict[str, Any]:
    m = re.search(r"(\{.*\})\s*$", text.strip())
    if not m:
        return {}
    try:
        val = json.loads(m.group(1))
        return val if isinstance(val, dict) else {}
    except Exception:
        return {}


def _find_upstream_node(graph: dict[str, Any], node_id: str) -> str:
    for edge in (graph.get("edges") or []):
        if not isinstance(edge, list) or len(edge) < 2:
            continue
        src, tgt = str(edge[0]), str(edge[1])
        if tgt == node_id and src not in ("START", "END"):
            return src
    return ""


def _auto_fill_undefined_flow_nodes(graph_id: str) -> dict[str, Any]:
    """
    Auto-heal graph config when workflow contains loop-like nodes that have
    no agent definition (e.g. `ner_flair_sent_loop`).
    """
    graph = MetaLoader.load("graphs", graph_id)
    if not isinstance(graph, dict):
        return {"changed": False, "fixed_nodes": [], "created_subgraphs": [], "warnings": [f"graph `{graph_id}` not found"]}

    flow_nodes = dict(graph.get("flowNodes") or {})
    changed = False
    fixed_nodes: list[str] = []
    created_subgraphs: list[str] = []
    warnings: list[str] = []

    for node in [str(n) for n in (graph.get("nodes") or []) if str(n) not in ("START", "END")]:
        if MetaLoader.exists("agents", node):
            continue
        if node in flow_nodes:
            continue
        if not node.endswith("_loop"):
            continue

        base_agent_id = node[: -len("_loop")].strip()
        if not base_agent_id:
            continue
        base_agent = MetaLoader.load("agents", base_agent_id)
        if not isinstance(base_agent, dict):
            warnings.append(f"skip `{node}`: base agent `{base_agent_id}` not found")
            continue

        inputs = [str(x) for x in (base_agent.get("inputs") or []) if str(x)]
        preferred_scalar = ""
        for candidate in ("sentence", "text", "item"):
            if candidate in inputs:
                preferred_scalar = candidate
                break
        if not preferred_scalar and inputs:
            preferred_scalar = inputs[0]
        if not preferred_scalar:
            preferred_scalar = "item"

        upstream = _find_upstream_node(graph, node)
        array_expr = "{{ item }}"
        if upstream:
            upstream_agent = MetaLoader.load("agents", upstream) or {}
            upstream_output = upstream_agent.get("outputs") or {}
            upstream_output_name = str(upstream_output.get("name") or "").strip()
            upstream_output_type = str(upstream_output.get("type") or "").strip().lower()
            if upstream_output_name and upstream_output_type == "list":
                array_expr = f"{{{{ {upstream_output_name} }}}}"
        if array_expr == "{{ item }}" and preferred_scalar == "sentence":
            array_expr = "{{ sentences }}"

        item_bindings: dict[str, str] = {preferred_scalar: f"{{{{ {preferred_scalar} }}}}"}
        for inp in inputs:
            if inp not in item_bindings:
                # For scalar foreach loops, non-item fields should come from
                # workflow/global state instead of being rebound to item text.
                item_bindings[inp] = f"{{{{ START.{inp} }}}}"

        loop_cfg: dict[str, Any] = {
            "loopType": "foreach",
            "array": array_expr,
            "itemBindings": item_bindings,
        }
        output_name = str((base_agent.get("outputs") or {}).get("name") or "").strip()
        if output_name and base_agent_id != node:
            loop_cfg["mergeAliases"] = {output_name: base_agent_id}

        flow_nodes[node] = {
            "kind": "loop",
            "name": f"Auto loop for {base_agent_id}",
            "subgraphId": node,
            "loopConfig": loop_cfg,
        }
        changed = True
        fixed_nodes.append(node)

        if not MetaLoader.exists("graphs", node):
            subgraph_cfg = {
                "name": f"Subgraph for {node}",
                "nodes": ["START", base_agent_id, "END"],
                "edges": [["START", base_agent_id], [base_agent_id, "END"]],
                "description": f"Auto-generated subgraph for loop node `{node}`",
            }
            MetaLoader.dump("graphs", node, subgraph_cfg)
            created_subgraphs.append(node)

    if changed:
        graph["flowNodes"] = flow_nodes
        MetaLoader.dump("graphs", graph_id, graph)

    return {
        "changed": changed,
        "fixed_nodes": fixed_nodes,
        "created_subgraphs": created_subgraphs,
        "warnings": warnings,
    }


def _extract_missing_prompt_vars(error_text: str) -> set[str]:
    msg = str(error_text or "")
    m = re.search(r"missing variables\s*\{([^}]*)\}", msg, flags=re.IGNORECASE)
    if not m:
        return set()
    body = m.group(1)
    quoted = re.findall(r"'([^']+)'", body)
    if quoted:
        return {x.strip() for x in quoted if x.strip()}
    parts = [x.strip().strip("\"'") for x in body.split(",")]
    return {x for x in parts if x}


def _auto_create_eval_metric_agent_if_missing(graph_id: str, var_name: str) -> str:
    """
    Create a lightweight eval agent when a missing prompt variable suggests
    metrics output and corresponding eval node exists but config is missing.
    """
    if not isinstance(var_name, str) or not var_name.endswith("_metrics"):
        return ""
    label = var_name[: -len("_metrics")].strip()
    if not label:
        return ""
    eval_node = f"eval_{label}"
    graph = MetaLoader.load("graphs", graph_id) or {}
    nodes = [str(n) for n in (graph.get("nodes") or [])]
    if eval_node not in nodes:
        return ""
    if MetaLoader.exists("agents", eval_node):
        return ""

    input_field = "entities"
    if label.lower() == "flair":
        input_field = "flair_entities"
    elif label.lower() == "llm":
        input_field = "entities"

    process = (
        f"pred = state.get('{input_field}') or {{}}\n"
        "if not isinstance(pred, dict):\n"
        "    pred = {}\n"
        "per_label = {}\n"
        "for label, vals in pred.items():\n"
        "    if isinstance(vals, list):\n"
        "        cleaned = [str(v).strip() for v in vals if str(v).strip()]\n"
        "    else:\n"
        "        cleaned = [str(vals).strip()] if str(vals).strip() else []\n"
        "    per_label[str(label)] = len(set(cleaned))\n"
        "__result__ = {\n"
        "    'total_entities': int(sum(per_label.values())),\n"
        "    'label_count': int(len(per_label)),\n"
        "    'per_label_entity_count': per_label\n"
        "}"
    )
    cfg = {
        "name": f"Auto {label.upper()} NER Metrics",
        "type": "PGM",
        "inputs": [input_field],
        "outputs": {"name": var_name, "type": "dict"},
        "persistence": {},
        "process": process,
        "engine": "pgm",
    }
    MetaLoader.dump("agents", eval_node, cfg)
    return eval_node


def _auto_bind_missing_prompt_vars(graph_id: str, missing_vars: set[str]) -> dict[str, Any]:
    graph = MetaLoader.load("graphs", graph_id)
    if not isinstance(graph, dict):
        return {"changed": False, "bound_agents": []}
    bindings = dict(graph.get("bindings") or {})
    changed = False
    bound_agents: list[str] = []
    nodes = [str(n) for n in (graph.get("nodes") or []) if str(n) not in ("START", "END")]
    for node in nodes:
        agent = MetaLoader.load("agents", node)
        if not isinstance(agent, dict):
            continue
        if str(agent.get("type") or "").upper() != "LLM":
            continue
        inputs = {str(x) for x in (agent.get("inputs") or []) if str(x)}
        need = sorted([v for v in missing_vars if v in inputs])
        if not need:
            continue
        node_bindings = dict(bindings.get(node) or {})
        local_changed = False
        for v in need:
            if v not in node_bindings:
                node_bindings[v] = f"{{{{ {v} }}}}"
                local_changed = True
        if local_changed:
            bindings[node] = node_bindings
            changed = True
            bound_agents.append(node)
    if changed:
        graph["bindings"] = bindings
        MetaLoader.dump("graphs", graph_id, graph)
    return {"changed": changed, "bound_agents": bound_agents}


def _load_autogen_skill_text() -> str:
    skill_path = META_DIR.parent / "doc" / "AUTOGEN_SKILL.md"
    try:
        return skill_path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _collect_repair_context(graph_id: str) -> dict[str, Any]:
    graph = MetaLoader.load("graphs", graph_id) or {}
    graphs: dict[str, Any] = {}
    agents: dict[str, Any] = {}
    queue: list[str] = [graph_id]
    visited: set[str] = set()

    while queue:
        gid = queue.pop(0)
        if gid in visited:
            continue
        visited.add(gid)
        g = MetaLoader.load("graphs", gid)
        if not isinstance(g, dict):
            continue
        graphs[gid] = g
        for node in [str(n) for n in (g.get("nodes") or []) if str(n) not in ("START", "END")]:
            a = MetaLoader.load("agents", node)
            if isinstance(a, dict):
                agents[node] = a
            elif MetaLoader.exists("graphs", node):
                queue.append(node)
        for fn in (g.get("flowNodes") or {}).values():
            if not isinstance(fn, dict):
                continue
            sub_id = str(fn.get("subgraphId") or "").strip()
            if sub_id and sub_id not in visited:
                queue.append(sub_id)
    return {"graphs": graphs, "agents": agents}


def _parse_json_response(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", raw, flags=re.IGNORECASE)
    if not m:
        return {}
    try:
        obj = json.loads(m.group(1))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _sanitize_llm_prompt_template(agent_cfg: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize invalid LangChain placeholders in LLM prompt templates.
    Example: {merged[a]} / {obj.key} -> {merged} / {obj}
    """
    cfg = dict(agent_cfg or {})
    if str(cfg.get("type") or "").upper() != "LLM":
        return cfg
    pt = cfg.get("prompt_template")
    if not isinstance(pt, dict):
        return cfg

    def _sanitize_text(text: Any) -> Any:
        if not isinstance(text, str):
            return text
        out = text
        out = re.sub(r"\{([a-zA-Z_]\w*)\[[^{}]+\]\}", r"{\1}", out)
        out = re.sub(r"\{([a-zA-Z_]\w*)\.[^{}]+\}", r"{\1}", out)
        return out

    safe_pt = dict(pt)
    safe_pt["system"] = _sanitize_text(safe_pt.get("system"))
    safe_pt["human"] = _sanitize_text(safe_pt.get("human"))
    cfg["prompt_template"] = safe_pt
    return cfg


def _normalize_error_signature(msg: str) -> str:
    text = str(msg or "").strip().replace("\\n", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    text = text.strip().strip('"').strip("'")
    if len(text) > 280:
        text = text[:277] + "..."
    return text


def _summarize_experiment_errors(exp_id: str, top_k: int = 3) -> dict[str, Any]:
    exp = MetaLoader.load("exps", exp_id) or {}
    history = exp.get("history") or []
    failed = [x for x in history if str(x.get("status") or "").lower() == "failed"]
    if not failed:
        return {"failed_samples": 0, "latest_error": "", "top_errors": []}

    counts: dict[str, int] = {}
    latest_error = _normalize_error_signature(str(failed[-1].get("error") or ""))
    for item in failed:
        sig = _normalize_error_signature(str(item.get("error") or ""))
        if not sig:
            continue
        counts[sig] = counts.get(sig, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    top_errors = [{"error": err, "count": cnt} for err, cnt in ranked[: max(1, int(top_k))]]
    return {
        "failed_samples": len(failed),
        "latest_error": latest_error,
        "top_errors": top_errors,
    }


def _is_experiment_success_status(status: Any) -> bool:
    s = str(status or "").strip().lower()
    return s in {"success", "completed"}


def _llm_skill_guided_repair(graph_id: str, errors: list[str], llm_id: str = "deepseek") -> dict[str, Any]:
    """
    Use AUTOGEN_SKILL.md as repair policy to generate structured graph/agent patches.
    """
    if not errors:
        return {"changed": False, "notes": []}
    skill_text = _load_autogen_skill_text()
    if not skill_text.strip():
        return {"changed": False, "notes": ["AUTOGEN_SKILL.md unavailable"]}

    try:
        import autogen

        cm = autogen.ConfigManager(META_DIR)
        llms = cm.load_all("llms") or {}
        chosen = llm_id if llm_id in llms else ("deepseek" if "deepseek" in llms else (next(iter(llms.keys())) if llms else ""))
        if not chosen:
            return {"changed": False, "notes": ["no llm config for skill-guided repair"]}
        client = autogen.LLMClient(llms[chosen])
    except Exception as ex:
        return {"changed": False, "notes": [f"repair llm init failed: {ex}"]}

    ctx = _collect_repair_context(graph_id)
    system = (
        "You are a NeuraGraph runtime repair assistant. "
        "Follow the AUTOGEN skill strictly to fix workflow/agent config errors.\n\n"
        "AUTOGEN_SKILL:\n"
        f"{skill_text}\n\n"
        "Output JSON only with schema:\n"
        "{\n"
        '  "notes": ["..."],\n'
        '  "graph_updates": [{"id":"graph_id","config":{...full graph json...}}],\n'
        '  "agent_updates": [{"id":"agent_id","config":{...full agent json...}}]\n'
        "}\n"
        "Rules:\n"
        "- Prefer minimal edits that directly resolve runtime errors.\n"
        "- Keep existing IDs.\n"
        "- If no safe fix, return empty update arrays.\n"
    )
    user = (
        "Repair this failed workflow execution.\n\n"
        f"target_graph_id: {graph_id}\n"
        f"errors: {json.dumps(errors, ensure_ascii=False, indent=2)}\n"
        f"current_graphs: {json.dumps(ctx.get('graphs') or {}, ensure_ascii=False, indent=2)}\n"
        f"current_agents: {json.dumps(ctx.get('agents') or {}, ensure_ascii=False, indent=2)}\n"
    )

    try:
        reply = client.chat(system, user)
    except Exception as ex:
        return {"changed": False, "notes": [f"repair llm call failed: {ex}"]}

    payload = _parse_json_response(reply)
    if not payload:
        return {"changed": False, "notes": ["repair llm returned non-json output"]}

    changed = False
    notes: list[str] = [str(x) for x in (payload.get("notes") or []) if str(x).strip()]
    updated_graphs: list[str] = []
    updated_agents: list[str] = []

    for item in (payload.get("graph_updates") or []):
        if not isinstance(item, dict):
            continue
        gid = str(item.get("id") or "").strip()
        cfg = item.get("config")
        if not gid or not isinstance(cfg, dict):
            continue
        MetaLoader.dump("graphs", gid, cfg)
        changed = True
        updated_graphs.append(gid)

    for item in (payload.get("agent_updates") or []):
        if not isinstance(item, dict):
            continue
        aid = str(item.get("id") or "").strip()
        cfg = item.get("config")
        if not aid or not isinstance(cfg, dict):
            continue
        safe_cfg = _sanitize_llm_prompt_template(cfg)
        MetaLoader.dump("agents", aid, safe_cfg)
        changed = True
        updated_agents.append(aid)

    if updated_graphs:
        notes.append("skill-guided graph updates: " + ", ".join(updated_graphs))
    if updated_agents:
        notes.append("skill-guided agent updates: " + ", ".join(updated_agents))
    return {"changed": changed, "notes": notes}


def _auto_repair_graph_after_failed_experiment(graph_id: str, exp_id: str, llm_id: str = "deepseek") -> dict[str, Any]:
    exp = MetaLoader.load("exps", exp_id) or {}
    history = exp.get("history") or []
    errors = [str(item.get("error") or "") for item in history if str(item.get("status") or "") == "failed"]

    repair_notes: list[str] = []
    changed = False

    base_repair = _auto_fill_undefined_flow_nodes(graph_id)
    if base_repair.get("changed"):
        changed = True
        nodes = ", ".join(base_repair.get("fixed_nodes") or []) or "(unknown)"
        repair_notes.append(f"filled undefined loop nodes: {nodes}")
    for w in (base_repair.get("warnings") or []):
        repair_notes.append(f"note: {w}")

    missing_vars: set[str] = set()
    for err in errors:
        missing_vars.update(_extract_missing_prompt_vars(err))
    if missing_vars:
        created_eval_nodes: list[str] = []
        for v in sorted(missing_vars):
            created = _auto_create_eval_metric_agent_if_missing(graph_id, v)
            if created:
                created_eval_nodes.append(created)
                changed = True
        if created_eval_nodes:
            repair_notes.append("created missing eval agents: " + ", ".join(created_eval_nodes))
        bind_result = _auto_bind_missing_prompt_vars(graph_id, missing_vars)
        if bind_result.get("changed"):
            changed = True
            repair_notes.append(
                "added bindings for missing prompt vars to nodes: "
                + ", ".join(bind_result.get("bound_agents") or [])
            )

    llm_repair = _llm_skill_guided_repair(graph_id, errors, llm_id=llm_id)
    if llm_repair.get("changed"):
        changed = True
    repair_notes.extend([str(x) for x in (llm_repair.get("notes") or []) if str(x).strip()])

    return {"changed": changed, "notes": repair_notes, "missing_vars": sorted(list(missing_vars))}


def run_workflow_or_agent(kind: str, target_id: str, inputs: Dict[str, Any]) -> str:
    from service.api.terminal import TerminalRunner

    runner = TerminalRunner(verbose=False)
    if not inputs:
        return (
            f"`{kind}` `{target_id}` requires input JSON.\n"
            f"Example: `/run {kind} {target_id} {{\"text\":\"...\"}}`"
        )
    if kind == "workflow":
        _auto_fill_undefined_flow_nodes(target_id)
    result = runner.run_graph(target_id, inputs) if kind == "workflow" else runner.run_agent(target_id, inputs)
    if result.get("status") != "success":
        return f"Run failed: {result.get('message', 'unknown error')}"
    payload = json.dumps(result.get("result", {}), ensure_ascii=False, indent=2)
    return f"Run succeeded for `{kind}` `{target_id}`:\n```json\n{payload}\n```"


def run_experiment(exp_id: str, llm_id: str = "deepseek") -> str:
    from service.api.terminal import TerminalRunner

    runner = TerminalRunner(verbose=False)
    exp_meta = MetaLoader.load("exps", exp_id) or {}
    graph_id = ""
    if str(exp_meta.get("runner_type") or "").strip().lower() == "graph":
        graph_id = str(exp_meta.get("runner_id") or "").strip()
        if graph_id:
            _auto_fill_undefined_flow_nodes(graph_id)
    result = runner.run_experiment(exp_id)
    auto_repair_notes: list[str] = []
    if (not _is_experiment_success_status(result.get("status"))) and graph_id:
        repair = _auto_repair_graph_after_failed_experiment(graph_id, exp_id, llm_id=llm_id)
        if repair.get("changed"):
            auto_repair_notes.extend([str(x) for x in (repair.get("notes") or []) if str(x).strip()])
            retry_result = runner.run_experiment(exp_id)
            if retry_result:
                result = retry_result
                auto_repair_notes.append("auto-retry executed once")
    summary = {
        "status": result.get("status"),
        "exp_id": result.get("exp_id"),
        "total": result.get("total"),
        "success": result.get("success"),
        "failed": result.get("failed"),
        "elapsed": round(float(result.get("elapsed", 0.0)), 2),
        "message": result.get("message"),
    }
    exp_link = f"/exp/{summary.get('exp_id')}" if summary.get("exp_id") else "/exp"
    err_summary = _summarize_experiment_errors(exp_id)
    top_error = ""
    if err_summary.get("top_errors"):
        first = (err_summary.get("top_errors") or [{}])[0]
        top_error = f"{first.get('count', 0)}x {first.get('error', '')}".strip()
    return md_card(
        "Experiment Run Result",
        [
            ("exp_id", f"`{summary.get('exp_id', '')}`"),
            ("status", summary.get("status", "")),
            ("success", summary.get("success", 0)),
            ("failed", summary.get("failed", 0)),
            ("elapsed_s", summary.get("elapsed", 0.0)),
            ("latest_error", err_summary.get("latest_error", "") or "(none)"),
        ],
        (
            [f"Open detail: [{summary.get('exp_id', 'experiment')}]({exp_link})"]
            + ([f"top_error: {top_error}"] if top_error else [])
            + auto_repair_notes
        ),
    )


def delete_meta(subdir: str, cid: str) -> str:
    if not MetaLoader.exists(subdir, cid):
        return f"`{cid}` not found in `{subdir}`."
    ok = MetaLoader.delete(subdir, cid)
    return f"Deleted `{cid}` from `{subdir}`." if ok else f"Failed to delete `{cid}`."


def _delete_result_dir(exp_id: str) -> bool:
    result_dir = META_DIR.parent / "result" / exp_id
    if not result_dir.exists():
        return False
    try:
        shutil.rmtree(result_dir)
        return True
    except Exception:
        return False


def clean_experiment(exp_id: str) -> str:
    eid = (exp_id or "").strip()
    if not eid:
        return "Usage: /clean exp <exp_id>|all"
    if eid.lower() == "all":
        exps = MetaLoader.loads("exps") or []
        meta_deleted = 0
        result_deleted = 0
        for item in exps:
            cid = str(item.get("id") or "").strip()
            if not cid:
                continue
            if MetaLoader.exists("exps", cid) and MetaLoader.delete("exps", cid):
                meta_deleted += 1
            if _delete_result_dir(cid):
                result_deleted += 1
        return md_card(
            "Experiment Cleanup",
            [
                ("scope", "`all`"),
                ("meta_deleted", meta_deleted),
                ("result_dirs_deleted", result_deleted),
            ],
        )

    meta_deleted = False
    if MetaLoader.exists("exps", eid):
        meta_deleted = MetaLoader.delete("exps", eid)
    result_deleted = _delete_result_dir(eid)
    if not meta_deleted and not result_deleted:
        return f"Nothing to clean for exp `{eid}`."
    return md_card(
        "Experiment Cleanup",
        [
            ("exp_id", f"`{eid}`"),
            ("meta_deleted", meta_deleted),
            ("result_dir_deleted", result_deleted),
        ],
    )


def _move_path(src: Path, dst: Path) -> bool:
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            if dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink()
        shutil.move(str(src), str(dst))
        return True
    except Exception:
        return False


def backup_experiment(exp_id: str) -> str:
    """
    Move experiment metadata and result out of active directories so it no
    longer appears in UI experiment lists.
    """
    eid = (exp_id or "").strip()
    if not eid:
        return "Usage: /backup exp <exp_id>|all"

    exps_dir = META_DIR / "exps"
    exps_backup_dir = META_DIR / "exps_backup"
    result_dir = META_DIR.parent / "result"
    result_backup_dir = META_DIR.parent / "result_backup"

    def _backup_one(one_id: str) -> tuple[bool, bool]:
        meta_src = exps_dir / f"{one_id}.json"
        meta_dst = exps_backup_dir / f"{one_id}.json"
        result_src = result_dir / one_id
        result_dst = result_backup_dir / one_id
        meta_moved = _move_path(meta_src, meta_dst) if meta_src.exists() else False
        result_moved = _move_path(result_src, result_dst) if result_src.exists() else False
        return meta_moved, result_moved

    if eid.lower() == "all":
        all_exps = MetaLoader.loads("exps") or []
        total = 0
        meta_moved_count = 0
        result_moved_count = 0
        for item in all_exps:
            one_id = str(item.get("id") or "").strip()
            if not one_id:
                continue
            total += 1
            m_moved, r_moved = _backup_one(one_id)
            meta_moved_count += 1 if m_moved else 0
            result_moved_count += 1 if r_moved else 0
        return md_card(
            "Experiment Backup",
            [
                ("scope", "`all`"),
                ("experiments_seen", total),
                ("meta_moved", meta_moved_count),
                ("result_dirs_moved", result_moved_count),
                ("hidden_from_ui", "yes"),
            ],
        )

    m_moved, r_moved = _backup_one(eid)
    if not m_moved and not r_moved:
        return f"Nothing to backup for exp `{eid}`."
    return md_card(
        "Experiment Backup",
        [
            ("exp_id", f"`{eid}`"),
            ("meta_moved", m_moved),
            ("result_dir_moved", r_moved),
            ("meta_backup", f"`{(exps_backup_dir / f'{eid}.json').as_posix()}`" if m_moved else "(none)"),
            ("result_backup", f"`{(result_backup_dir / eid).as_posix()}`" if r_moved else "(none)"),
            ("hidden_from_ui", "yes"),
        ],
    )


def check_sandbox_status(sandbox_name: str) -> str:
    name = (sandbox_name or "").strip()
    if not name:
        return "Usage: /check sandbox <name>"
    try:
        from plugin.plugin_client import is_available
        from plugin.plugin_config import url_for_sandbox
        from plugin.sandbox_manifest import get_sandbox
    except Exception as ex:
        return f"Sandbox check unavailable: {ex}"

    spec = get_sandbox(name)
    if not spec:
        return md_card(
            "Sandbox Status",
            [("sandbox", f"`{name}`"), ("status", "unknown")],
            ["Not found in `meta/plugins_sandbox.json`."],
        )

    running = bool(is_available(name, force_check=True))
    url = url_for_sandbox(name)
    return md_card(
        "Sandbox Status",
        [
            ("sandbox", f"`{name}`"),
            ("status", "running" if running else "not_running"),
            ("url", f"`{url}`"),
            ("port", getattr(spec, "port", "")),
        ],
        (
            [f"Start command: `./scripts/start_plugin_sandbox.ps1 -Name {name}`"]
            if not running
            else []
        ),
    )


def create_testset(runner_id: str, filename: str, source_file: str = "", count: int = 5) -> str:
    runner_id = (runner_id or "").strip()
    filename = (filename or "").strip()
    source_file = (source_file or "").strip()
    if not runner_id or not filename:
        return "Missing runner_id or filename."
    if not filename.lower().endswith(".csv"):
        filename = f"{filename}.csv"
    if source_file:
        try:
            fields, rows = TestLoader.load_by_id_file(runner_id, source_file)
        except Exception as e:
            return f"Failed to load source dataset `{source_file}`: {e}"
        if not rows:
            return f"Source dataset `{source_file}` has no rows."
        rows = [dict(r) for r in rows]
        picked = [dict(rows[i % len(rows)]) for i in range(max(1, int(count)))]
        TestLoader.save_csv_rows(runner_id, filename, fields, picked)
        return f"Created testset `{filename}` for runner `{runner_id}` from `{source_file}` with {len(picked)} rows."
    fields = ["text", "entities", "gold_relations"]
    base_rows = [
        {
            "text": "Aspirin reduces fever in patients with influenza.",
            "entities": '[{"text":"Aspirin","id":"D001241","label":"Chemical"},{"text":"influenza","id":"D007251","label":"Disease"}]',
            "gold_relations": "D001241 | D007251",
        },
        {
            "text": "Metformin is used for type 2 diabetes treatment.",
            "entities": '[{"text":"Metformin","id":"D008687","label":"Chemical"},{"text":"type 2 diabetes","id":"D003924","label":"Disease"}]',
            "gold_relations": "D008687 | D003924",
        },
        {
            "text": "Ibuprofen can relieve pain caused by arthritis.",
            "entities": '[{"text":"Ibuprofen","id":"D007052","label":"Chemical"},{"text":"arthritis","id":"D001168","label":"Disease"}]',
            "gold_relations": "D007052 | D001168",
        },
    ]
    n = max(1, int(count))
    rows = [dict(base_rows[i % len(base_rows)]) for i in range(n)]
    TestLoader.save_csv_rows(runner_id, filename, fields, rows)
    return f"Created template testset `{filename}` for runner `{runner_id}` with {len(rows)} rows."


def create_experiment(
    runner_id: str,
    dataset: str,
    runner_type: str = "graph",
    *,
    tuning_dataset: str = "",
    test_dataset: str = "",
    split_ratio: float | None = None,
    split_seed: int = 42,
) -> str:
    runner_id = (runner_id or "").strip()
    dataset = _normalize_dataset_name(dataset)
    runner_type = (runner_type or "graph").strip()
    if not runner_id or not dataset:
        return "Missing runner_id or dataset."
    split_info = None
    if split_ratio is not None:
        try:
            split_info = _auto_split_dataset_for_runner(
                runner_id,
                dataset,
                split_ratio=float(split_ratio),
                seed=int(split_seed),
            )
        except Exception as ex:
            return f"Failed to auto split dataset: {ex}"
        tuning_dataset = split_info["tuning_dataset"]
        test_dataset = split_info["test_dataset"]
    tuning_dataset = _normalize_dataset_name(tuning_dataset or "")
    test_dataset = _normalize_dataset_name(test_dataset or dataset)
    if not tuning_dataset:
        tuning_dataset = test_dataset
    if not test_dataset:
        test_dataset = tuning_dataset
    try:
        _fields, rows = TestLoader.load_by_id_file(runner_id, test_dataset)
        sample_count = len(rows or [])
    except Exception:
        sample_count = 0
    exp_id = str(uuid.uuid4())
    data = {
        "dataset": test_dataset,
        "tuning_dataset": tuning_dataset,
        "test_dataset": test_dataset,
        "runner_type": runner_type,
        "runner_id": runner_id,
        "runner_display": runner_id,
        "samples": sample_count,
        "exp_id": exp_id,
        "name": f"{runner_id}_{test_dataset}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "status": "pending",
        "progress": 0,
    }
    if split_info:
        data["dataset_split"] = split_info["dataset_split"]
    MetaLoader.dump("exps", exp_id, data)
    return md_card(
        "Experiment Created",
        [
            ("exp_id", f"`{exp_id}`"),
            ("runner_id", f"`{runner_id}`"),
            ("test_dataset", f"`{test_dataset}`"),
            ("tuning_dataset", f"`{tuning_dataset}`"),
            ("samples", sample_count),
        ],
        [f"Open detail: [{exp_id}](/exp/{exp_id})", f"Run now: `/run experiment {exp_id}`"],
    )


def create_experiment_record(
    runner_id: str,
    dataset: str,
    runner_type: str = "graph",
    *,
    tuning_dataset: str = "",
    test_dataset: str = "",
    split_ratio: float | None = None,
    split_seed: int = 42,
) -> dict[str, Any]:
    runner_id = (runner_id or "").strip()
    dataset = _normalize_dataset_name(dataset)
    runner_type = (runner_type or "graph").strip()
    if not runner_id or not dataset:
        raise ValueError("Missing runner_id or dataset.")
    split_info = None
    if split_ratio is not None:
        split_info = _auto_split_dataset_for_runner(
            runner_id,
            dataset,
            split_ratio=float(split_ratio),
            seed=int(split_seed),
        )
        tuning_dataset = split_info["tuning_dataset"]
        test_dataset = split_info["test_dataset"]
    tuning_dataset = _normalize_dataset_name(tuning_dataset or "")
    test_dataset = _normalize_dataset_name(test_dataset or dataset)
    if not tuning_dataset:
        tuning_dataset = test_dataset
    if not test_dataset:
        test_dataset = tuning_dataset
    try:
        _fields, rows = TestLoader.load_by_id_file(runner_id, test_dataset)
        sample_count = len(rows or [])
    except Exception:
        sample_count = 0
    exp_id = str(uuid.uuid4())
    data = {
        "dataset": test_dataset,
        "tuning_dataset": tuning_dataset,
        "test_dataset": test_dataset,
        "runner_type": runner_type,
        "runner_id": runner_id,
        "runner_display": runner_id,
        "samples": sample_count,
        "exp_id": exp_id,
        "name": f"{runner_id}_{test_dataset}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "status": "pending",
        "progress": 0,
    }
    if split_info:
        data["dataset_split"] = split_info["dataset_split"]
    MetaLoader.dump("exps", exp_id, data)
    return data


def _compare_flair_llm_from_states(exp_id: str) -> dict[str, Any]:
    from service.result.loader import ResultLoader, iter_sample_indices

    states = ResultLoader.load(exp_id) or {}
    keys = iter_sample_indices(states)
    if not keys:
        return {"available": False, "reason": "no sample states"}

    def _as_entity_text_set(v: Any) -> set[str]:
        vals: list[str] = []
        obj = v
        if isinstance(v, str):
            try:
                obj = json.loads(v)
            except Exception:
                obj = v
        if isinstance(obj, list):
            for x in obj:
                if isinstance(x, dict):
                    vals.append(str(x.get("text") or "").strip().lower())
                else:
                    vals.append(str(x).strip().lower())
        elif isinstance(obj, str):
            vals.extend([s.strip().lower() for s in obj.splitlines() if s.strip()])
        return {x for x in vals if x}

    flair_total = 0
    llm_total = 0
    overlap_total = 0
    both_count = 0
    for k in keys:
        item = states.get(k) or {}
        if not isinstance(item, dict):
            continue
        flair_raw = None
        llm_raw = None
        for fkey in ("flair_entities", "ner_flair", "flair_result", "entities_flair"):
            if fkey in item:
                flair_raw = item.get(fkey)
                break
        for lkey in ("llm_entities", "ner_llm", "llm_result", "entities_llm"):
            if lkey in item:
                llm_raw = item.get(lkey)
                break
        # Common current workflow key for LLM NER output.
        if llm_raw is None and "entities" in item:
            llm_raw = item.get("entities")

        # Fallback to metrics totals when raw entities are missing.
        f_count = None
        l_count = None
        if isinstance(item.get("flair_metrics"), dict):
            try:
                f_count = int((item.get("flair_metrics") or {}).get("total_entities"))
            except Exception:
                f_count = None
        if isinstance(item.get("llm_metrics"), dict):
            try:
                l_count = int((item.get("llm_metrics") or {}).get("total_entities"))
            except Exception:
                l_count = None

        if flair_raw is not None and llm_raw is not None:
            fset = _as_entity_text_set(flair_raw)
            lset = _as_entity_text_set(llm_raw)
            flair_total += len(fset)
            llm_total += len(lset)
            overlap_total += len(fset & lset)
            both_count += 1
            continue

        if f_count is not None and l_count is not None:
            flair_total += max(0, f_count)
            llm_total += max(0, l_count)
            # Metrics fallback cannot derive overlap reliably.
            both_count += 1

    if both_count == 0:
        return {
            "available": False,
            "reason": "workflow states do not expose both Flair and LLM entity outputs with known keys",
        }
    return {
        "available": True,
        "samples_with_both": both_count,
        "flair_entities_total": flair_total,
        "llm_entities_total": llm_total,
        "overlap_entities_total": overlap_total,
    }


def _preflight_llm_agents_for_workflow(graph_id: str, llms: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """
    Preflight check for all LLM agents referenced by a workflow.
    - Ensure mapped LLM config exists.
    - Probe a tiny call to detect quota/auth/network failures early.
    """
    graph = MetaLoader.load("graphs", graph_id) or {}
    nodes = [str(n) for n in (graph.get("nodes") or []) if str(n) not in ("START", "END")]
    agents: list[dict[str, Any]] = []
    for n in nodes:
        a = MetaLoader.load("agents", n)
        if isinstance(a, dict):
            agents.append(a)
    llm_agents = [a for a in agents if str(a.get("type") or "").upper() == "LLM"]
    if not llm_agents:
        return {"ok": True, "checked_models": [], "checked_agents": []}

    checked_models: set[str] = set()
    checked_agents: list[str] = []
    failures: list[dict[str, str]] = []

    import autogen

    for a in llm_agents:
        aid = str(a.get("id") or a.get("name") or "").strip()
        model_id = str(a.get("model") or "").strip()
        if not model_id:
            failures.append({"agent_id": aid, "reason": "agent model is empty"})
            continue
        checked_agents.append(aid)
        if model_id in checked_models:
            continue
        checked_models.add(model_id)

        llm_cfg = llms.get(model_id)
        if not isinstance(llm_cfg, dict):
            failures.append({"agent_id": aid, "reason": f"LLM config not found for model `{model_id}`"})
            continue
        try:
            client = autogen.LLMClient(llm_cfg)
            # Minimal token probe: enough to verify auth/quota/connectivity.
            _ = client.chat("You are a connectivity checker.", "Reply exactly: OK")
        except Exception as ex:
            msg = str(ex)
            failures.append({"agent_id": aid, "reason": msg})

    if failures:
        return {
            "ok": False,
            "checked_models": sorted(list(checked_models)),
            "checked_agents": checked_agents,
            "failures": failures,
        }
    return {
        "ok": True,
        "checked_models": sorted(list(checked_models)),
        "checked_agents": checked_agents,
    }


def run_orchestration(goal: str, llm_id: str = "deepseek", session: Dict[str, Any] | None = None) -> str:
    """
    Agentic orchestration:
    generate workflow -> create experiment -> run -> report -> compare.
    """
    import autogen
    from service.api.terminal import TerminalRunner
    from service.experiment_optimize import _build_report_payload, _generate_report

    session = session or {"pins": {}}
    pins = session.setdefault("pins", {})
    goal = (goal or "").strip()
    if not goal:
        return "Missing orchestration goal. Usage: /orchestrate <goal>"

    steps: list[str] = []
    steps.append("1) Building execution plan from goal")
    cm = autogen.ConfigManager(META_DIR)
    llms = cm.load_all("llms")
    chosen = llm_id if llm_id in llms else (next(iter(llms.keys())) if llms else None)
    if not chosen:
        return "No LLM config found for orchestration."
    llm_cfg = llms[chosen]

    generated: list[str] = []
    reused = find_suitable_workflow(goal)
    if reused:
        graph_id = str(reused.get("graph_id") or "").strip()
        steps.append(f"2) Reused existing workflow: `{graph_id}` (score={reused.get('score', 0)})")
    else:
        engine = autogen.AutoGen(llm_cfg, verbose=False)
        engine.cm = cm
        candidate_agents = find_suitable_agents(goal, limit=6)
        goal_for_build = goal
        if candidate_agents:
            ids = [str(x.get("id") or "").strip() for x in candidate_agents if str(x.get("id") or "").strip()]
            if ids:
                goal_for_build += "\n\nReuse existing agents when applicable: " + ", ".join(ids)
                steps.append(f"2) No matching workflow found; generating new workflow with agent reuse hints: {', '.join(ids[:4])}")
        else:
            steps.append("2) No matching workflow found; generating a new workflow")
        plan = engine.analyze(goal_for_build)
        generated = [str(p) for p in engine.generate(plan)]
        errors = engine.validate(plan)
        if errors:
            return md_card(
                "Orchestration Failed",
                [("stage", "generate_workflow"), ("reason", "workflow validation failed")],
                [f"validation errors:\n```json\n{json.dumps(errors, ensure_ascii=False, indent=2)}\n```"],
            )
        graph_id = str((plan.get("graph_plan") or {}).get("id") or "").strip()
        if not graph_id:
            return "Orchestration failed: generated workflow id is empty."
        steps.append(f"3) Workflow generated: `{graph_id}`")

    pins["graph"] = graph_id
    pins["runner_id"] = graph_id

    repair = _auto_fill_undefined_flow_nodes(graph_id)
    if repair.get("changed"):
        fixed = ", ".join([f"`{x}`" for x in (repair.get("fixed_nodes") or [])]) or "(none)"
        steps.append(f"3) Auto-repaired undefined flow nodes: {fixed}")
    for w in (repair.get("warnings") or []):
        steps.append(f"3) Auto-repair note: {w}")

    preflight = _preflight_llm_agents_for_workflow(graph_id, llms)
    if not preflight.get("ok", False):
        return md_card(
            "Orchestration Failed",
            [
                ("stage", "preflight_llm"),
                ("graph_id", f"`{graph_id}`"),
                ("reason", "LLM preflight check failed"),
                ("checked_models", ", ".join(preflight.get("checked_models", [])) or "(none)"),
            ],
            [
                "details:\n```json\n"
                + json.dumps(preflight.get("failures", []), ensure_ascii=False, indent=2)
                + "\n```"
            ],
        )
    steps.append(
        "3) LLM preflight passed"
        + (
            f" (models: {', '.join(preflight.get('checked_models', []))})"
            if preflight.get("checked_models")
            else ""
        )
    )

    dataset = str(pins.get("dataset") or f"{graph_id}_auto5.csv")
    create_testset(graph_id, dataset, "", count=5)
    pins["dataset"] = dataset
    steps.append(f"4) Dataset prepared: `{dataset}`")

    exp = create_experiment_record(graph_id, dataset, "graph")
    exp_id = exp["exp_id"]
    pins["exp"] = exp_id
    steps.append(f"5) Experiment created: `{exp_id}`")

    runner = TerminalRunner(verbose=False)
    use_live_progress = bool(getattr(sys.stdout, "isatty", lambda: False)())
    if use_live_progress:
        def _progress_callback(current: int, total: int, elapsed: float, success_count: int, fail_count: int):
            line = TerminalRunner.format_progress_bar(
                current=current,
                total=total,
                elapsed=elapsed,
                width=24,
                unicode_mode=True,
                color_enabled=True,
            )
            sys.stdout.write("\r" + line)
            sys.stdout.flush()
    else:
        _progress_callback = None

    run_result = runner.run_experiment(exp_id, progress_callback=_progress_callback)
    if use_live_progress:
        sys.stdout.write("\n")
        sys.stdout.flush()
    if not _is_experiment_success_status(run_result.get("status")):
        repair = _auto_repair_graph_after_failed_experiment(graph_id, exp_id, llm_id=chosen)
        if repair.get("changed"):
            steps.append("6) Experiment failed; auto-repair applied")
            for note in (repair.get("notes") or []):
                steps.append(f"   - {note}")
            run_result = runner.run_experiment(exp_id, progress_callback=_progress_callback)
            if use_live_progress:
                sys.stdout.write("\n")
                sys.stdout.flush()
            if _is_experiment_success_status(run_result.get("status")):
                steps.append("6) Auto-retry succeeded")
            else:
                err_summary = _summarize_experiment_errors(exp_id)
                return md_card(
                    "Orchestration Failed",
                    [
                        ("stage", "run_experiment"),
                        ("exp_id", f"`{exp_id}`"),
                        ("reason", run_result.get("message", "unknown")),
                        ("latest_error", err_summary.get("latest_error", "") or "(none)"),
                    ],
                    (
                        ["auto-repair attempted but retry still failed"]
                        + [
                            f"top_error: {x.get('count', 0)}x {x.get('error', '')}"
                            for x in (err_summary.get("top_errors") or [])
                        ]
                    ),
                )
        else:
            err_summary = _summarize_experiment_errors(exp_id)
            return md_card(
                "Orchestration Failed",
                [
                    ("stage", "run_experiment"),
                    ("exp_id", f"`{exp_id}`"),
                    ("reason", run_result.get("message", "unknown")),
                    ("latest_error", err_summary.get("latest_error", "") or "(none)"),
                ],
                [
                    f"top_error: {x.get('count', 0)}x {x.get('error', '')}"
                    for x in (err_summary.get("top_errors") or [])
                ],
            )
    steps.append("6) Experiment run completed")

    exp_cfg = MetaLoader.load("exps", exp_id) or exp
    payload = _build_report_payload(exp_id, exp_cfg)
    report_md = _generate_report(payload)
    report_path = Path(__file__).resolve().parents[2] / "result" / exp_id / "report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_md, encoding="utf-8")
    steps.append("7) Report generated")

    cmp_summary = _compare_flair_llm_from_states(exp_id)
    steps.append("8) Flair vs LLM comparison generated")

    return md_card(
        "Agentic Orchestration Result",
        [
            ("goal", goal),
            ("llm", f"`{chosen}`"),
            ("graph_id", f"`{graph_id}`"),
            ("workflow_mode", "reused" if reused else "generated"),
            ("exp_id", f"`{exp_id}`"),
            ("report_path", f"`{report_path.as_posix()}`"),
            ("comparison", json.dumps(cmp_summary, ensure_ascii=False)),
        ],
        [
            f"generated files: {len(generated)}",
            "steps:\n" + "\n".join([f"- {x}" for x in steps]),
            f"open report page: [/exp/{exp_id}](/exp/{exp_id})",
        ],
    )


def copy_workflow(source_id: str, target_id: str) -> str:
    source_id = (source_id or "").strip()
    target_id = (target_id or "").strip()
    if not source_id or not target_id:
        return "Missing source workflow id or target workflow id."
    source = MetaLoader.load("graphs", source_id)
    if not source:
        return f"Workflow `{source_id}` not found."
    if MetaLoader.exists("graphs", target_id):
        return f"Workflow `{target_id}` already exists."
    copied = dict(source)
    copied["name"] = f"{source.get('name', source_id)} (copy)"
    MetaLoader.dump("graphs", target_id, copied)
    return md_card("Workflow Copied", [("source", f"`{source_id}`"), ("target", f"`{target_id}`")], [f"View copied workflow: `/show workflow {target_id}`"])


def start_optimize_loop(
    exp_id: str,
    max_updates: int = 1,
    *,
    tuning_dataset: str = "",
    test_dataset: str = "",
) -> str:
    from service.experiment_optimize import run_optimize_loop_by_exp

    exp_id = (exp_id or "").strip()
    if not exp_id:
        return "Missing exp_id."
    try:
        summary = run_optimize_loop_by_exp(
            exp_id,
            max_agent_updates=max_updates,
            tuning_dataset=_normalize_dataset_name(tuning_dataset),
            test_dataset=_normalize_dataset_name(test_dataset),
        )
    except Exception as e:
        return f"Optimize loop failed: {e}"
    brief = {
        "baseline_exp_id": summary.get("baseline_exp_id"),
        "final_best_exp_id": summary.get("final_best_exp_id"),
        "suggestion_count": summary.get("suggestion_count", 0),
        "accepted_version_map": summary.get("accepted_version_map", {}),
    }
    return "Optimize loop finished:\n```json\n" + json.dumps(brief, ensure_ascii=False, indent=2) + "\n```"


def preview_slash(cmd: str, session: Dict[str, Any]) -> str:
    raw = (cmd or "").strip()
    parts = raw.split()
    if not parts:
        return "Empty command."
    pins = (session or {}).setdefault("pins", {})
    c0 = parts[0].lower()
    action = "read"
    if c0 in ("/run", "/create", "/copy", "/optimize", "/delete", "/clean", "/backup"):
        action = "write"
    resolved: List[Tuple[str, Any]] = [("command", f"`{raw}`"), ("mode", "`dry-run preview`"), ("risk", "`high`" if action == "write" else "`low`")]
    if c0 == "/create" and len(parts) >= 2 and parts[1].lower() in ("experiment", "exp"):
        runner = parts[2] if len(parts) >= 3 else (pins.get("graph") or pins.get("runner_id") or "")
        dataset = parts[3] if len(parts) >= 4 else (pins.get("dataset") or "")
        resolved.append(("resolved_runner", f"`{runner or '(missing)'}`"))
        resolved.append(("resolved_dataset", f"`{dataset or '(missing)'}`"))
        extra_tokens = parts[4:] if len(parts) >= 5 else []
        if extra_tokens and "=" not in extra_tokens[0]:
            resolved.append(("resolved_runner_type", f"`{extra_tokens[0]}`"))
            extra_tokens = extra_tokens[1:]
        kv = {k: v for k, v in [p.split("=", 1) for p in extra_tokens if "=" in p]}
        if kv.get("tuning"):
            resolved.append(("resolved_tuning_dataset", f"`{kv.get('tuning')}`"))
        if kv.get("test"):
            resolved.append(("resolved_test_dataset", f"`{kv.get('test')}`"))
        if kv.get("split"):
            resolved.append(("resolved_split_ratio", f"`{kv.get('split')}`"))
    if c0 in ("/run", "/show") and len(parts) >= 3 and parts[1].lower() in ("experiment", "exp"):
        exp_id = parts[2] if len(parts) >= 3 else (pins.get("exp") or "")
        resolved.append(("resolved_exp", f"`{exp_id or '(missing)'}`"))
    if pins:
        resolved.extend((f"pin.{k}", f"`{v}`") for k, v in pins.items())
    return md_card("Execution Preview", resolved, ["Run the command directly to execute."])


def execute_slash_command(cmd: str, session: Dict[str, Any] | None = None, llm_id: str = "deepseek") -> str | None:
    raw = (cmd or "").strip()
    parts = raw.split()
    if not parts:
        return "Empty command."
    session = session or {"pins": {}}
    pins = session.setdefault("pins", {})
    c0 = parts[0].lower()

    if c0 in ("/help", "/h"):
        return (
            "Commands:\n"
            "- `/list workflows|agents|tools|datasets|llms|experiments`\n"
            "- `/show workflow|agent|tool|dataset|llm|experiment <id>`\n"
            "- `/pin show|clear|graph <id>|exp <id>|dataset <file>`\n"
            "- `/dryrun <slash_command>`\n"
            "- `/run workflow|agent <id> {json_inputs}`\n"
            "- `/run experiment <exp_id>`\n"
            "- `/create testset <runner_id> <filename> [source_file] [count]`\n"
            "- `/create experiment [runner_id] [dataset] [runner_type] [tuning=<file>] [test=<file>] [split=<0.8>] [seed=<42>]` (supports pins)\n"
            "- `/dataset` — CID raw/tuning/test registry; build & extract structured sets\n"
            "- `/copy workflow <source_id> <target_id>`\n"
            "- `/optimize <exp_id> [max_updates] [tuning=<file>] [test=<file>]`\n"
            "- `/orchestrate <goal>`\n"
            "- `/delete workflow|agent|tool|llm|experiment <id>`\n"
            "- `/clean exp <exp_id>|all`\n"
            "- `/backup exp <exp_id>|all`\n"
            "- `/check sandbox <name>`"
        )

    if c0 == "/dryrun":
        preview_cmd = raw[len("/dryrun") :].strip()
        if not preview_cmd:
            return "Usage: /dryrun <slash_command>"
        session["last_preview"] = {"command": preview_cmd, "at": datetime.now().isoformat()}
        return preview_slash(preview_cmd, session)

    if c0 == "/pin":
        if len(parts) == 1 or (len(parts) >= 2 and parts[1].lower() == "show"):
            return render_pins(session)
        sub = parts[1].lower()
        if sub == "clear":
            if len(parts) >= 3:
                key = parts[2].lower()
                if key in pins:
                    pins.pop(key, None)
                    return f"Cleared pin `{key}`."
                return f"Pin `{key}` not found."
            pins.clear()
            return "Cleared all pins."
        if len(parts) < 3:
            return "Usage: /pin graph|exp|dataset <value>"
        val = parts[2]
        if sub in ("graph", "workflow", "runner"):
            pins["graph"] = val
            pins["runner_id"] = val
            return render_pins(session)
        if sub in ("exp", "experiment"):
            pins["exp"] = val
            return render_pins(session)
        if sub == "dataset":
            pins["dataset"] = val
            pins["test_dataset"] = val
            return render_pins(session)
        if sub in ("source", "raw"):
            pins["source_dataset"] = val
            return render_pins(session)
        if sub == "tuning":
            pins["tuning_dataset"] = val
            return render_pins(session)
        if sub == "test":
            pins["test_dataset"] = val
            pins["dataset"] = val
            return render_pins(session)
        return f"Unsupported pin target: `{sub}`"

    if c0 == "/dataset":
        return handle_dataset_command(parts, session)

    if c0 == "/list":
        sub = parts[1].lower() if len(parts) > 1 else "workflows"
        if sub in ("workflow", "workflows", "graph", "graphs"):
            return list_meta("graphs", "Workflows")
        if sub in ("agent", "agents"):
            return list_meta("agents", "Agents")
        if sub in ("tool", "tools"):
            return list_meta("tools", "Tools")
        if sub in ("dataset", "datasets"):
            return list_datasets()
        if sub in ("llm", "llms"):
            return list_meta("llms", "LLMs")
        if sub in ("experiment", "experiments", "exp", "exps"):
            return list_meta("exps", "Experiments")
        return f"Unsupported list type: `{sub}`"

    if c0 == "/show" and len(parts) >= 3:
        sub = parts[1].lower()
        cid = parts[2]
        if sub in ("workflow", "graph"):
            return show_meta("graphs", cid, "Workflow")
        if sub == "agent":
            return show_meta("agents", cid, "Agent")
        if sub == "tool":
            return show_meta("tools", cid, "Tool")
        if sub in ("dataset", "datasets"):
            return show_dataset(cid)
        if sub == "llm":
            return show_meta("llms", cid, "LLM")
        if sub in ("experiment", "exp"):
            return show_meta("exps", cid, "Experiment")

    if c0 == "/run" and len(parts) >= 3:
        sub = parts[1].lower()
        cid = parts[2]
        inputs = _try_parse_json_tail(raw)
        if sub in ("workflow", "graph"):
            return run_workflow_or_agent("workflow", cid, inputs)
        if sub == "agent":
            return run_workflow_or_agent("agent", cid, inputs)
        if sub in ("experiment", "exp"):
            return run_experiment(cid, llm_id=llm_id)

    if c0 == "/delete" and len(parts) >= 3:
        sub = parts[1].lower()
        cid = parts[2]
        if sub in ("workflow", "graph"):
            return delete_meta("graphs", cid)
        if sub == "agent":
            return delete_meta("agents", cid)
        if sub == "tool":
            return delete_meta("tools", cid)
        if sub == "llm":
            return delete_meta("llms", cid)
        if sub in ("experiment", "exp"):
            return delete_meta("exps", cid)

    if c0 == "/clean" and len(parts) >= 3:
        sub = parts[1].lower()
        target = parts[2]
        if sub in ("experiment", "exp", "exps"):
            return clean_experiment(target)

    if c0 == "/backup" and len(parts) >= 3:
        sub = parts[1].lower()
        target = parts[2]
        if sub in ("experiment", "exp", "exps"):
            return backup_experiment(target)

    if c0 == "/check" and len(parts) >= 3:
        sub = parts[1].lower()
        target = parts[2]
        if sub == "sandbox":
            return check_sandbox_status(target)

    if c0 == "/create" and len(parts) >= 2:
        sub = parts[1].lower()
        if sub == "testset":
            if len(parts) < 4:
                return "Usage: /create testset <runner_id> <filename> [source_file] [count]"
            runner_id = parts[2]
            filename = parts[3]
            source_file = parts[4] if len(parts) >= 5 else ""
            try:
                count = int(parts[5]) if len(parts) >= 6 else 5
            except ValueError:
                count = 5
            return create_testset(runner_id, filename, source_file, count)
        if sub in ("experiment", "exp"):
            runner_id = parts[2] if len(parts) >= 3 else (pins.get("graph") or pins.get("runner_id") or "")
            dataset = parts[3] if len(parts) >= 4 else (pins.get("dataset") or "")
            runner_type = "graph"
            extra_tokens = parts[4:] if len(parts) >= 5 else []
            if extra_tokens and "=" not in extra_tokens[0]:
                runner_type = extra_tokens[0]
                extra_tokens = extra_tokens[1:]
            kv = {k.strip().lower(): v.strip() for k, v in [p.split("=", 1) for p in extra_tokens if "=" in p]}
            tuning_dataset = kv.get("tuning", "")
            test_dataset = kv.get("test", "")
            split_ratio = None
            if kv.get("split"):
                try:
                    split_ratio = float(kv["split"])
                except Exception:
                    split_ratio = None
            split_seed = 42
            if kv.get("seed"):
                try:
                    split_seed = int(kv["seed"])
                except Exception:
                    split_seed = 42
            if not runner_id or not dataset:
                return "Usage: /create experiment [runner_id] [dataset] [runner_type] [tuning=<file>] [test=<file>] [split=<0.8>] [seed=<42>]\nTip: pin defaults via `/pin graph <id>` and `/pin dataset <file>`."
            return create_experiment(
                runner_id,
                dataset,
                runner_type,
                tuning_dataset=tuning_dataset,
                test_dataset=test_dataset,
                split_ratio=split_ratio,
                split_seed=split_seed,
            )

    if c0 == "/copy" and len(parts) >= 4:
        sub = parts[1].lower()
        if sub in ("workflow", "graph"):
            return copy_workflow(parts[2], parts[3])

    if c0 == "/optimize" and len(parts) >= 2:
        exp_id = parts[1]
        max_updates = 1
        extra_tokens = parts[2:] if len(parts) >= 3 else []
        if extra_tokens and "=" not in extra_tokens[0]:
            try:
                max_updates = int(extra_tokens[0])
            except ValueError:
                max_updates = 1
            extra_tokens = extra_tokens[1:]
        kv = {k.strip().lower(): v.strip() for k, v in [p.split("=", 1) for p in extra_tokens if "=" in p]}
        return start_optimize_loop(
            exp_id,
            max_updates=max_updates,
            tuning_dataset=kv.get("tuning", ""),
            test_dataset=kv.get("test", ""),
        )

    if c0 == "/orchestrate":
        goal = raw[len("/orchestrate") :].strip()
        if not goal:
            return "Usage: /orchestrate <goal>"
        return run_orchestration(goal, llm_id=llm_id, session=session)

    return None


def command_catalog() -> List[Dict[str, str]]:
    return [
        {"cmd": "/help", "desc": "Show command help"},
        {"cmd": "/pin show", "desc": "Show pinned context"},
        {"cmd": "/pin graph wf_cid_re_llm_linear", "desc": "Pin default workflow"},
        {"cmd": "/pin dataset cid_dev_2samples.csv", "desc": "Pin default dataset"},
        {"cmd": "/dryrun /create experiment", "desc": "Preview command execution"},
        {"cmd": "/create experiment", "desc": "Create experiment using pinned defaults"},
        {"cmd": "/create experiment wf_demo source.csv graph split=0.8 seed=42", "desc": "Create exp with auto train/test split"},
        {"cmd": "/clean exp <exp_id>", "desc": "Delete exp meta + result folder"},
        {"cmd": "/clean exp all", "desc": "Delete all experiments and results"},
        {"cmd": "/backup exp <exp_id>", "desc": "Move exp out of active UI list"},
        {"cmd": "/backup exp all", "desc": "Backup all active experiments"},
        {"cmd": "/check sandbox flair", "desc": "Check flair sandbox health"},
        {"cmd": "/orchestrate build flair vs llm ner workflow then run and report compare", "desc": "Generate->run->report->compare pipeline"},
        {"cmd": "/list experiments", "desc": "List experiments"},
    ]
