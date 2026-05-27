from typing import Dict, Any, List, TypedDict,Type
import re
from service.meta.loader import MetaLoader,GraphMetaLoader

try:
    from langgraph.graph import StateGraph, START, END
except ImportError:
    StateGraph = None
    START = "__start__"
    END = "__end__"


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
    start_ref = re.compile(r"\{\{\s*START\.(\w+)\s*\}\}")
    simple_ref = re.compile(r"\{\{\s*(\w+)\s*\}\}")

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
            m = start_ref.search(expr)
            if m:
                state.add(m.group(1))

    for key in compute_graph_global_inputs(graph_id):
        state.add(key)

    for _nid, flow in (g.get("flowNodes") or {}).items():
        if flow.get("kind") == "loop":
            lc = flow.get("loopConfig") or {}
            arr = lc.get("array", "")
            if isinstance(arr, str):
                m = simple_ref.search(arr)
                if m:
                    state.add(m.group(1))
            state.update({"sentence", "text", "item", "head", "tail", "entity_link"})

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




