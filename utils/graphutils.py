from __future__ import annotations

import difflib
import json
import re
from copy import deepcopy
from collections import defaultdict
from pathlib import Path
from typing import Dict, Any, List, TypedDict, Type

from service.meta.loader import MetaLoader, GraphMetaLoader

_WORKFLOW_OPT_SUFFIX = re.compile(
    r"^(?P<base>.+)_opt_(?P<tag>\d{8}_\d{6})(?:_r(?P<round>\d+))?$"
)
_WORKFLOW_COPY_SUFFIX = re.compile(r"^(?P<base>.+)_copy(?:_\d+)?$")
_COMPARE_GRAPH_FIELDS = (
    "name",
    "description",
    "nodes",
    "edges",
    "bindings",
    "flowNodes",
    "metrics",
    "agentVersions",
)

try:
    from langgraph.graph import StateGraph, START, END
except ImportError:
    StateGraph = None
    START = "__start__"
    END = "__end__"

_START_REF = re.compile(r"\{\{\s*START\.(\w+)\s*\}\}")
_SIMPLE_REF = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def create_state_typeddict(state_def: Dict[str, Any] | List[str]) -> Type[TypedDict]:
    """
    把 JSON 里的 state 定义动态变成 TypedDict 子类
    支持两种格式：
    - dict: {"doc": str, "text": str}  → 带类型
    - list: ["doc", "text"]           → 只字段名，类型默认 Any
    """
    if isinstance(state_def, list):
        # list → 转成 {name: Any}
        fields = {key: Any for key in state_def}
    else:
        # dict → 直接用（类型保留）
        fields = state_def

    return TypedDict("DynamicState", fields, total=False)


def compute_states(graph_id):
    graphs = GraphMetaLoader.load(graph_id)
    g = graphs[graph_id]
    state = set()
    for node in g["nodes"]:
        agent = MetaLoader.load("agents", node)
        if not agent:
            continue
        for inp in agent.get("inputs", []):
            state.add(inp)
        outputs = agent.get("outputs", {})
        if "name" in outputs:
            state.add(outputs["name"])

    for _node, binds in (g.get("bindings") or {}).items():
        for field in binds:
            state.add(field)
        for expr in binds.values():
            if not isinstance(expr, str):
                continue
            m = _START_REF.search(expr)
            if m:
                state.add(m.group(1))

    for key in compute_graph_global_inputs(graph_id):
        state.add(key)

    for _nid, flow in (g.get("flowNodes") or {}).items():
        if flow.get("kind") == "loop":
            lc = flow.get("loopConfig") or {}
            arr = lc.get("array", "")
            if isinstance(arr, str):
                m = _SIMPLE_REF.search(arr)
                if m:
                    state.add(m.group(1))
            for field in (lc.get("itemBindings") or {}):
                state.add(field)
            state.update(collect_loop_merge_keys(graph_id, _nid))
            for src, dst in (lc.get("mergeAliases") or {}).items():
                state.add(dst)
            sub_id = flow.get("subgraphId")
            if sub_id:
                state.update(collect_subgraph_agent_inputs(sub_id))
                state.update(collect_subgraph_output_fields(sub_id))

    return sorted(list(state))


def compute_graph_global_inputs(graph_id):
    graphs = GraphMetaLoader.load(graph_id)
    all_outputs = set()
    all_inputs = set()
    first_node_inputs=set()
    # 收集所有 outputs.name

    for idx, node in enumerate(graphs[graph_id]["nodes"]):
        agent = MetaLoader.load("agents",node)
        if not agent:
            continue
        outputs = agent.get("outputs", {})
        if "name" in outputs:
            all_outputs.add(outputs["name"])

        agent = MetaLoader.load("agents",node)
        if idx == 0:
            for inp in agent.get("inputs", []):
                first_node_inputs.add(inp)
        else:
            for inp in agent.get("inputs", []):
                all_inputs.add(inp)


    uncovered_non_first = all_inputs - all_outputs
    global_inputs = first_node_inputs.union(uncovered_non_first)
    return sorted(list(global_inputs))


_LOOP_ACCUM_OUTPUT_TYPES = frozenset({"list", "dict"})


def get_loop_flow_node(graph_id: str, loop_node_id: str) -> dict[str, Any] | None:
    graphs = GraphMetaLoader.load(graph_id)
    g = graphs.get(graph_id) or {}
    flow = (g.get("flowNodes") or {}).get(loop_node_id)
    if isinstance(flow, dict) and flow.get("kind") == "loop":
        return flow
    return None


def is_loop_flow_node(graph_id: str, node_id: str) -> bool:
    return get_loop_flow_node(graph_id, node_id) is not None


def collect_subgraph_output_fields(subgraph_id: str) -> set[str]:
    """Output field names produced by agents inside a subgraph."""
    graphs = GraphMetaLoader.load(subgraph_id)
    g = graphs.get(subgraph_id) or {}
    fields: set[str] = set()
    for node in g.get("nodes", []):
        if node in ("START", "END"):
            continue
        agent = MetaLoader.load("agents", node)
        if not agent:
            continue
        outputs = agent.get("outputs") or {}
        if "name" in outputs:
            fields.add(outputs["name"])
    return fields


def collect_loop_scalar_item_fields(graph_id: str, loop_node_id: str) -> list[str]:
    """
    Fields populated when the foreach element is a scalar (e.g. one sentence).
    loopConfig.scalarItemField overrides; else itemBindings {{ field }} targets;
    else subgraph binding fields that reference themselves.
    """
    flow = get_loop_flow_node(graph_id, loop_node_id)
    if not flow:
        return []
    lc = flow.get("loopConfig") or {}
    explicit = lc.get("scalarItemField")
    if isinstance(explicit, str):
        return [explicit]
    if isinstance(explicit, list):
        return [str(f) for f in explicit]
    from utils.bindings import item_binding_scalar_targets

    return item_binding_scalar_targets(lc.get("itemBindings"))


def collect_loop_merge_keys(graph_id: str, loop_node_id: str) -> frozenset[str]:
    """
    State keys merged across loop iterations (list append / dict merge).
    loopConfig.mergeKeys overrides; otherwise subgraph agent outputs whose
    type is list or dict, excluding per-iteration itemBindings targets.
    mergeAliases destination fields are included.
    """
    flow = get_loop_flow_node(graph_id, loop_node_id)
    if not flow:
        return frozenset()
    lc = flow.get("loopConfig") or {}
    explicit = lc.get("mergeKeys")
    if isinstance(explicit, list):
        keys = {str(k) for k in explicit}
    else:
        keys: set[str] = set()
        item_keys = set((lc.get("itemBindings") or {}).keys())
        sub_id = flow.get("subgraphId") or loop_node_id
        graphs = GraphMetaLoader.load(sub_id)
        g = graphs.get(sub_id) or {}
        for node in g.get("nodes", []):
            if node in ("START", "END"):
                continue
            agent = MetaLoader.load("agents", node)
            if not agent:
                continue
            outputs = agent.get("outputs") or {}
            oname = outputs.get("name")
            otype = (outputs.get("type") or "str").lower()
            if oname and otype in _LOOP_ACCUM_OUTPUT_TYPES and oname not in item_keys:
                keys.add(oname)
    for _src, dst in (lc.get("mergeAliases") or {}).items():
        keys.add(str(dst))
    return frozenset(keys)


def collect_loop_stream_fields(graph_id: str, loop_node_id: str) -> frozenset[str]:
    """
    Fields to show when streaming a loop node update.
    Default: loopConfig.itemBindings keys + subgraph agent output names.
    Overrides (graph JSON loopConfig):
      - streamFields: explicit list replaces auto derivation
      - streamIncludeMergeKeys: true adds collect_loop_merge_keys()
    """
    flow = get_loop_flow_node(graph_id, loop_node_id)
    if not flow:
        return frozenset()
    lc = flow.get("loopConfig") or {}
    explicit = lc.get("streamFields")
    if isinstance(explicit, list) and explicit:
        return frozenset(str(f) for f in explicit)
    fields: set[str] = set((lc.get("itemBindings") or {}).keys())
    sub_id = flow.get("subgraphId") or loop_node_id
    fields.update(collect_subgraph_output_fields(sub_id))
    if lc.get("streamIncludeMergeKeys"):
        fields.update(collect_loop_merge_keys(graph_id, loop_node_id))
    return frozenset(fields)


def collect_subgraph_agent_inputs(subgraph_id: str) -> list[str]:
    """Union of agent input fields and binding targets inside a subgraph."""
    graphs = GraphMetaLoader.load(subgraph_id)
    g = graphs.get(subgraph_id) or {}
    fields: set[str] = set()
    for node in g.get("nodes", []):
        if node in ("START", "END"):
            continue
        agent = MetaLoader.load("agents", node)
        if agent:
            fields.update(agent.get("inputs", []))
    for node_binds in (g.get("bindings") or {}).values():
        if isinstance(node_binds, dict):
            fields.update(node_binds.keys())
    return sorted(fields)


def _call_agent(agent):
    def _invoke(s):
        out = agent.invoke(s)
        return out
    return _invoke

def create_graph(agent,checkpointer=None):
    state = set()
    # inputs
    for inp in agent.inputs:
        state.add(inp)
    outputs = agent.outputs
    if "name" in outputs:
        state.add(outputs["name"])
    StateDict = create_state_typeddict(sorted(list(state)))
    sg = StateGraph(StateDict)
    sg.add_node(agent.id, _call_agent(agent))
    sg.add_edge(START, agent.id)
    sg.add_edge(agent.id, END)
    return sg.compile(checkpointer=checkpointer)


def effective_agent_versions(
    graphs_cfg: Dict[str, Any] | None,
    root_graph_id: str,
) -> Dict[str, str]:
    """Merged pin map: root workflow agentVersions apply to subgraph agents too."""
    graphs_cfg = graphs_cfg or {}
    root = graphs_cfg.get(root_graph_id) or {}
    pins: Dict[str, str] = dict(root.get("agentVersions") or {})
    for gid, g in graphs_cfg.items():
        if gid == root_graph_id:
            continue
        for agent_id, version in (g.get("agentVersions") or {}).items():
            pins.setdefault(str(agent_id), str(version))
    return pins


def resolve_report_agent_versions(
    graphs_cfg: Dict[str, Any] | None,
    agents_cfg: Dict[str, Any] | None,
    *,
    root_graph_id: str = "",
) -> Dict[str, Any]:
    """Version map for reports/UI; subgraph agents inherit root workflow pins."""
    graphs_cfg = graphs_cfg or {}
    agents_cfg = agents_cfg or {}
    if not root_graph_id:
        root_graph_id = next(iter(graphs_cfg), "")
    effective = effective_agent_versions(graphs_cfg, root_graph_id)
    by_graph: Dict[str, Any] = {}
    for gid, g in graphs_cfg.items():
        resolved: Dict[str, str] = {}
        for node_id in (g or {}).get("nodes", []):
            if node_id in ("START", "END"):
                continue
            if MetaLoader.load("graphs", node_id):
                continue
            if node_id not in agents_cfg:
                continue
            resolved[node_id] = effective.get(node_id) or "current"
        by_graph[gid] = {
            "pinned": dict((g or {}).get("agentVersions") or {}),
            "resolved": resolved,
            "is_subgraph": gid != root_graph_id,
            "parent_graph_id": root_graph_id if gid != root_graph_id else "",
        }
    return {
        "root_graph_id": root_graph_id,
        "effective": effective,
        "by_graph": by_graph,
    }


def build_workflow_agent_roster(
    runner_id: str,
    graphs_cfg: Dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Flat agent roster with effective pinned versions (incl. subgraph agents)."""
    rid = str(runner_id or "").strip()
    if not rid:
        return []
    graphs_cfg = graphs_cfg if graphs_cfg is not None else (GraphMetaLoader.load(rid) or {})
    if not graphs_cfg:
        agent_meta = MetaLoader.load("agents", rid)
        if agent_meta:
            return [
                {
                    "agent_id": rid,
                    "name": str(agent_meta.get("name") or rid),
                    "version": "current",
                    "graph_id": "",
                }
            ]
        return []
    effective = effective_agent_versions(graphs_cfg, rid)
    roster: dict[str, dict[str, str]] = {}
    for gid, g in graphs_cfg.items():
        is_sub = gid != rid
        for node in (g or {}).get("nodes", []):
            if node in ("START", "END"):
                continue
            if MetaLoader.load("graphs", node):
                continue
            am = MetaLoader.load("agents", node)
            if not am:
                continue
            roster[node] = {
                "agent_id": node,
                "name": str(am.get("name") or node),
                "version": str(effective.get(node) or "current"),
                "graph_id": gid if is_sub else "",
            }
    return sorted(roster.values(), key=lambda x: x["agent_id"])


def parse_workflow_family(graph_id: str) -> dict[str, Any]:
    """Map a graph id to its workflow family and variant metadata."""
    gid = str(graph_id or "").strip()
    if not gid:
        return {
            "family_id": "",
            "variant_kind": "unknown",
            "variant_label": "unknown",
            "sort_key": (9, "", 0),
        }

    opt_match = _WORKFLOW_OPT_SUFFIX.match(gid)
    if opt_match:
        base = opt_match.group("base")
        tag = opt_match.group("tag")
        round_num = opt_match.group("round")
        if round_num:
            return {
                "family_id": base,
                "variant_kind": "opt_round",
                "variant_label": f"opt {tag} r{round_num}",
                "sort_key": (1, tag, int(round_num)),
            }
        return {
            "family_id": base,
            "variant_kind": "opt",
            "variant_label": f"opt {tag}",
            "sort_key": (1, tag, 0),
        }

    copy_match = _WORKFLOW_COPY_SUFFIX.match(gid)
    if copy_match:
        base = copy_match.group("base")
        return {
            "family_id": base,
            "variant_kind": "copy",
            "variant_label": "copy",
            "sort_key": (2, gid, 0),
        }

    kind = "subgraph" if gid.startswith("sg_") else "baseline"
    label = "subgraph" if kind == "subgraph" else "baseline"
    return {
        "family_id": gid,
        "variant_kind": kind,
        "variant_label": label,
        "sort_key": (0, "", 0),
    }


def _clean_workflow_display_name(name: str, *, fallback: str = "") -> str:
    text = str(name or fallback or "").strip()
    text = re.sub(r"\s*\[optimized\]\s*", "", text, flags=re.I)
    text = re.sub(r"\s*\(copy\)\s*", "", text, flags=re.I).strip()
    return text or fallback


def enrich_graph_list_item(graph: dict[str, Any]) -> dict[str, Any]:
    """Attach family/version metadata used by the workflow list UI."""
    gid = str(graph.get("id") or "").strip()
    fam = parse_workflow_family(gid)
    pins = dict(graph.get("agentVersions") or {})
    return {
        **graph,
        "family_id": fam["family_id"],
        "variant_kind": fam["variant_kind"],
        "variant_label": fam["variant_label"],
        "sort_key": fam["sort_key"],
        "agent_versions": pins,
        "pinned_agent_count": len(pins),
        "created_at": graph.get("created_at") or "",
        "updated_at": graph.get("updated_at") or "",
        "is_subgraph": gid.startswith("sg_"),
    }


def select_representative_graph_ids(graph_ids: list[str] | None = None) -> list[str]:
    """
    Representative graph ids per workflow family for testing and pruning.

    - Baseline (initial) workflow id is always kept when present (for A/B vs optimized).
    - Among opt/copy variants, only the highest sort_key is kept.
    """
    if graph_ids is None:
        graphs_dir = Path(__file__).resolve().parent.parent / "meta" / "graphs"
        graph_ids = sorted(p.stem for p in graphs_dir.glob("*.json"))

    by_family: dict[str, list[str]] = {}
    for gid in graph_ids:
        gid = str(gid or "").strip()
        if not gid:
            continue
        fam = parse_workflow_family(gid)
        by_family.setdefault(str(fam["family_id"]), []).append(gid)

    selected: list[str] = []
    for family_id, members in by_family.items():
        members.sort(key=lambda g: (parse_workflow_family(g)["sort_key"], g))
        highest = members[-1]
        baseline = family_id if family_id in members else None
        if baseline and baseline != highest:
            selected.extend([baseline, highest])
        else:
            selected.append(highest)
    return sorted(selected)


def redundant_graph_ids(graph_ids: list[str] | None = None) -> list[str]:
    """Graph ids that are not the highest-version representative of their family."""
    if graph_ids is None:
        graphs_dir = Path(__file__).resolve().parent.parent / "meta" / "graphs"
        graph_ids = sorted(p.stem for p in graphs_dir.glob("*.json"))
    keep = set(select_representative_graph_ids(graph_ids))
    return sorted(g for g in graph_ids if g not in keep)


def group_workflow_families(graphs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group workflow graphs by family with chronologically sorted versions."""
    enriched = [enrich_graph_list_item(g) for g in graphs if g.get("id")]
    by_family: dict[str, list[dict[str, Any]]] = {}
    for item in enriched:
        by_family.setdefault(str(item["family_id"]), []).append(item)

    families: list[dict[str, Any]] = []
    for family_id, versions in by_family.items():
        versions.sort(key=lambda x: (x.get("sort_key") or (9, "", 0), x.get("created_at") or ""))
        baseline = next((v for v in versions if v.get("id") == family_id), None)
        display = baseline or versions[-1]
        default_version = versions[-1]
        families.append(
            {
                "family_id": family_id,
                "name": _clean_workflow_display_name(
                    str(display.get("name") or ""),
                    fallback=family_id,
                ),
                "description": str(display.get("description") or ""),
                "is_subgraph": bool(family_id.startswith("sg_")),
                "version_count": len(versions),
                "versions": versions,
                "default_version_id": str(default_version.get("id") or family_id),
            }
        )

    families.sort(key=lambda f: (f.get("is_subgraph", False), str(f.get("name") or "").lower()))
    return families


def _graph_compare_document(graph_id: str, graph: dict[str, Any]) -> dict[str, Any]:
    doc = {field: deepcopy(graph.get(field)) for field in _COMPARE_GRAPH_FIELDS if field in graph}
    graphs_cfg = GraphMetaLoader.load(graph_id) or {}
    doc["effective_agent_versions"] = {
        row["agent_id"]: row["version"]
        for row in build_workflow_agent_roster(graph_id, graphs_cfg)
    }
    return doc


def _json_lines(content: dict[str, Any]) -> list[str]:
    return json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True).splitlines()


def compare_workflow_graphs(left_id: str, right_id: str) -> dict[str, Any] | None:
    """Unified diff between two workflow graph configs."""
    left = MetaLoader.load("graphs", left_id)
    right = MetaLoader.load("graphs", right_id)
    if not left or not right:
        return None

    left_doc = _graph_compare_document(left_id, left)
    right_doc = _graph_compare_document(right_id, right)
    diff = difflib.unified_diff(
        _json_lines(left_doc),
        _json_lines(right_doc),
        fromfile=left_id,
        tofile=right_id,
        lineterm="",
    )
    left_pins = left_doc.get("effective_agent_versions") or {}
    right_pins = right_doc.get("effective_agent_versions") or {}
    changed_agents = sorted(
        agent_id
        for agent_id in set(left_pins) | set(right_pins)
        if left_pins.get(agent_id) != right_pins.get(agent_id)
    )
    return {
        "left": left_id,
        "right": right_id,
        "diff": "\n".join(diff),
        "agent_version_changes": [
            {
                "agent_id": agent_id,
                "left": left_pins.get(agent_id, "current"),
                "right": right_pins.get(agent_id, "current"),
            }
            for agent_id in changed_agents
        ],
    }


def _agents_in_graph_package(graphs_cfg: Dict[str, Any]) -> set[str]:
    """Agent node ids used anywhere in a workflow package (root + subgraphs)."""
    found: set[str] = set()
    for graph in (graphs_cfg or {}).values():
        for node in (graph or {}).get("nodes", []):
            if node in ("START", "END"):
                continue
            if MetaLoader.load("agents", node):
                found.add(node)
    return found


def count_agent_workflow_references() -> Dict[str, int]:
    """
    Count how many top-level workflows reference each agent (directly or via subgraphs).

    Each file under meta/graphs/*.json is one workflow; nested subgraph configs are
    included when scanning that workflow's GraphMetaLoader package.
    """
    counts: Dict[str, int] = defaultdict(int)
    graphs = MetaLoader.loads("graphs") or []
    for graph in graphs:
        graph_id = str(graph.get("id") or "").strip()
        if not graph_id:
            continue
        graphs_cfg = GraphMetaLoader.load(graph_id)
        if not graphs_cfg:
            continue
        for agent_id in _agents_in_graph_package(graphs_cfg):
            counts[agent_id] += 1
    return dict(counts)

