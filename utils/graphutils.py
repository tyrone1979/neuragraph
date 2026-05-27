from typing import Dict, Any, List, TypedDict,Type
import re
from service.meta.loader import MetaLoader,GraphMetaLoader

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




