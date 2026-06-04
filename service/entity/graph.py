import json
from logging import getLogger
try:
    from langgraph.graph import StateGraph, START, END
except ImportError:
    StateGraph = None; START = "__start__"; END = "__end__"
try:
    from langgraph.types import Checkpointer
except ImportError:
    Checkpointer = None
from service.entity.agent import AgentLoader
from service.entity.entity import Entity, EntityLoader
from typing import Dict, Any, Iterator
from service.meta.loader import MetaLoader
from utils.conversion import T, jsonify_state
from utils.graphutils import (
    collect_loop_merge_keys,
    collect_loop_scalar_item_fields,
    compute_states,
    create_state_typeddict,
)
from utils.bindings import (
    apply_loop_item_bindings,
    apply_node_bindings,
    merge_loop_values,
    normalize_loop_item,
    resolve_loop_items,
)
logger = getLogger(__name__)

class GraphEntity(Entity):
    def __init__(self,  meta: Dict[str, Any],checkpointer: Checkpointer=None):
        super().__init__(meta,checkpointer)
        token_map = {"START": START, "END": END}
        state = compute_states(meta.get("id"))
        StateDict = create_state_typeddict(state)
        sg = StateGraph(StateDict)
        for n in meta["nodes"]:
            sg.add_node(n, _call_agent(n, meta))
        # 3. 画边（token 替换）
        for src, tgt in meta["edges"]:
            src_key = token_map.get(src, src) if isinstance(src, str) else [token_map.get(s, s) for s in src]
            tgt_key = token_map.get(tgt, tgt)
            sg.add_edge(src_key, tgt_key)

        self.compiled_graph = sg.compile(checkpointer=checkpointer)


    def invoke(self, state: T, **kwargs) -> Dict[str, Any]:
        import uuid
        config = kwargs.get("config") or {
            "configurable": {"thread_id": str(uuid.uuid4())}
        }
        return self.compiled_graph.invoke(jsonify_state(dict(state)), config=config)

    def stream(self, state: T,**kwargs) -> Iterator[dict[str, Any] | Any]:
        config=kwargs.get("config")
        stream_mode=kwargs.get("stream_mode")
        state=jsonify_state(state)
        if config:
            return self.compiled_graph.stream(state,config=config,
                                          stream_mode=stream_mode,
                                          subgraphs=True)
        else:
            return self.compiled_graph.stream(state,stream_mode=stream_mode,
                                          subgraphs=True)

    async def ainvoke(self, state: T, **kwargs):
        config = kwargs.get("config")
        state = jsonify_state(state)
        return await self.compiled_graph.ainvoke(state, config=config)

    async def astream_events(self, input, config):
        input = jsonify_state(input)
        return self.compiled_graph.astream_events(input, config)

    def get_state(self, config):
        return self.compiled_graph.get_state(config)


    def get_state_history(self, config):
        return self.compiled_graph.get_state_history(config)

class GraphLoader(EntityLoader):

    @staticmethod
    def load(id: str,**extra_params) -> GraphEntity | None:
        checkpointer: Checkpointer = extra_params.get("checkpointer")
        meta=MetaLoader.load("graphs",id)
        if meta:
            return GraphEntity(meta, checkpointer=checkpointer)
        return None

def safe_load(s):
    """str -> list | dict | 原字符串"""
    if not isinstance(s, str):
        return s
    s = s.strip()
    if (s.startswith('[') and s.endswith(']')) or \
       (s.startswith('{') and s.endswith('}')):
        try:
            return json.loads(s)
        except ValueError:
            pass
    return s

def _call_agent(name: str, graph_meta: dict | None = None):
    graph_meta = graph_meta or {}
    bindings_map = graph_meta.get("bindings") or {}
    flow_nodes = graph_meta.get("flowNodes") or {}
    agent_versions = graph_meta.get("agentVersions") or {}
    pinned_version = agent_versions.get(name)
    flow = flow_nodes.get(name)

    if flow and flow.get("kind") == "loop":
        subgraph_id = flow.get("subgraphId") or name
        subgraph = GraphLoader.load(subgraph_id)
        loop_cfg = flow.get("loopConfig") or {}
        array_expr = loop_cfg.get("array") or "{{ text }}"

        if subgraph is None:
            def passthrough(_s):
                # Missing subgraph should be a no-op update.
                # Returning full state causes concurrent key writes in LangGraph.
                return {}
            return passthrough

        item_bindings = loop_cfg.get("itemBindings") or {}
        graph_id = graph_meta.get("id") or name
        merge_keys = collect_loop_merge_keys(graph_id, name)
        merge_aliases = loop_cfg.get("mergeAliases") or {}
        scalar_fields = collect_loop_scalar_item_fields(graph_id, name)

        def invoke_loop(s):
            items = resolve_loop_items(array_expr, s)
            accum = dict(s)
            n_items = len(items) if isinstance(items, list) else 0
            for idx, item in enumerate(items):
                if isinstance(item, dict) and item.get("error"):
                    continue
                head = item.get("head", "?") if isinstance(item, dict) else "?"
                tail = item.get("tail", "?") if isinstance(item, dict) else "?"
                # Silenced for batch runs — verbose per-pair logging generates
                # excessive terminal output that obscures progress bars.
                iter_state = jsonify_state(
                    apply_loop_item_bindings(
                        accum, item, item_bindings, scalar_fields=scalar_fields
                    )
                )
                out = subgraph.invoke(iter_state)
                if not isinstance(out, dict):
                    continue
                accum.update({k: v for k, v in out.items() if k not in merge_keys})
                for key in merge_keys:
                    if key in out and out[key] is not None:
                        accum[key] = merge_loop_values(accum.get(key), out[key])
                for src, dst in merge_aliases.items():
                    if src in out and out[src] is not None:
                        accum[dst] = merge_loop_values(accum.get(dst), out[src])
            return accum

        return invoke_loop

    if flow and flow.get("kind") == "branch":
        conditions = flow.get("conditions") or []

        def _truthy(val):
            if val is None:
                return False
            if isinstance(val, (list, dict)):
                return len(val) > 0
            if isinstance(val, str):
                return bool(val.strip())
            return bool(val)

        def _eval_cond(cond, state):
            if isinstance(cond, str):
                expr = cond.strip()
                if expr.startswith("!"):
                    return not _truthy(state.get(expr[1:].strip()))
                return _truthy(state.get(expr))
            field = cond.get("field") or cond.get("condition", "")
            if isinstance(field, str) and field.startswith("!"):
                return not _truthy(state.get(field[1:].strip()))
            op = (cond.get("op") or "not_empty").lower()
            raw = state.get(field) if field else None
            val = cond.get("value", "")
            if op in ("exists", "not_empty"):
                return _truthy(raw)
            if op in ("not_exists", "empty"):
                return not _truthy(raw)
            if op == "eq":
                return str(raw) == str(val)
            if op == "ne":
                return str(raw) != str(val)
            if op == "contains":
                return str(val) in str(raw or "")
            if op == "not_contains":
                return str(val) not in str(raw or "")
            try:
                num_raw, num_val = float(raw), float(val)
                if op == "gt":
                    return num_raw > num_val
                if op == "gte":
                    return num_raw >= num_val
                if op == "lt":
                    return num_raw < num_val
                if op == "lte":
                    return num_raw <= num_val
            except (TypeError, ValueError):
                pass
            return _truthy(raw)

        def invoke_branch(s):
            out = dict(s)
            route = "skip"
            for cond in conditions:
                label = cond.get("label", "branch") if isinstance(cond, dict) else str(cond)
                if _eval_cond(cond, s):
                    route = label
                    break
            if route == "skip" and not conditions:
                route = "continue" if s.get("entities") else "skip"
            out["route"] = route
            return out

        return invoke_branch

    agent = AgentLoader.load_version(name, pinned_version) if pinned_version else AgentLoader.load(name)
    if agent is None and pinned_version:
        logger.warning(
            "Pinned version not found for agent '%s': %s. Falling back to current.",
            name,
            pinned_version,
        )
        agent = AgentLoader.load(name)
    if agent is None:
        def passthrough(_s):
            # Missing agent node should not emit state updates.
            # Returning full state can trigger INVALID_CONCURRENT_GRAPH_UPDATE.
            return {}
        return passthrough

    if agent.type != "SUB":
        def invoke(s):
            bound = apply_node_bindings(s, name, bindings_map)
            return agent.invoke(bound)
        return invoke
    else:
        subgraph = GraphLoader.load(name)
        def invoke(s):

            inputs = s[agent.inputs[0]]
            if isinstance(inputs, str):
                if '|' in inputs:
                    inputs = inputs.split('|')
                elif ',' in inputs:
                    inputs = inputs.split(',')
                else:
                    inputs = json.loads(inputs)
            results= None
            for inp in inputs:
                # 子图输入：当前 state + 输入注入
                sub_state = dict(s)

                for index in agent.idx:
                    if isinstance(inp,dict) and index in inp:
                        sub_state[index] = inp[index]
                    else:
                        sub_state[index]=inp
                # 调用子图
                out = subgraph.invoke(sub_state)
                output=out[agent.outputs['name']]

                if isinstance(output, str):
                    output = safe_load(output)  # 先尝试反序列化
                # 第一次初始化
                if results is None:
                    if isinstance(output, list) or isinstance(output,tuple):
                        results = []  # 以后永远是 list
                    else:
                        results = {}  # 以后永远是 dict

                if isinstance(results, list):
                    if isinstance(output, list):
                        results.extend(output)
                    else:
                        results.append(output)  # 单元素也塞进 list
                elif isinstance(output, dict):
                    for k, v in output.items():
                        results.setdefault(k, [])
                        if isinstance(v, list):
                            results[k].extend(v)
                        else:
                            results[k].append(v)

            return {agent.outputs['name']: results}

        return invoke



