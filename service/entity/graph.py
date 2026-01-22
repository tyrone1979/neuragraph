import json
from logging import getLogger
from langgraph.graph import StateGraph, START, END
from langgraph.types import Checkpointer
from service.entity.agent import AgentLoader
from service.entity.entity import Entity, EntityLoader
from typing import Dict, Any, List, TypedDict, TypeVar, Type, Iterator
from service.meta.loader import MetaLoader,GraphMetaLoader
T = TypeVar("T", bound=TypedDict)

logger = getLogger(__name__)

class GraphEntity(Entity):
    def __init__(self,  meta: Dict[str, Any],checkpointer: Checkpointer=None):
        super().__init__(meta,checkpointer)
        token_map = {"START": START, "END": END}
        state = compute_states(meta.get("id"))
        StateDict = create_state_typeddict(state)
        sg = StateGraph(StateDict)
        for n in meta["nodes"]:
            sg.add_node(n, _call_agent(n))
        # 3. 画边（token 替换）
        for src, tgt in meta["edges"]:
            src_key = token_map.get(src, src) if isinstance(src, str) else [token_map.get(s, s) for s in src]
            tgt_key = token_map.get(tgt, tgt)
            sg.add_edge(src_key, tgt_key)

        self.compiled_graph = sg.compile(checkpointer=checkpointer)


    def invoke(self, state: T) -> Dict[str, Any]:
        return self.compiled_graph.invoke(state)

    def stream(self, state: T,**kwargs) -> Iterator[dict[str, Any] | Any]:
        config=kwargs.get("config")
        stream_mode=kwargs.get("stream_mode")
        if config:
            return self.compiled_graph.stream(state,config=config,
                                          stream_mode=stream_mode,
                                          subgraphs=True)
        else:
            return self.compiled_graph.stream(state,stream_mode=stream_mode,
                                          subgraphs=True)

    async def ainvoke(self, state: T,**kwargs):
        config=kwargs.get("config")
        return self.compiled_graph.ainvoke(state,config=config)

    async def astream_events(self, input, config):
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

def _call_agent(name: str):
    agent=AgentLoader.load(name)
    if agent.type != "SUB":
        def invoke(s):
            out= agent.invoke(s)
            return out
        return invoke
    else:
        # SUBGRAPH：构建子图调用逻辑
        subgraph = GraphLoader.load(name)  # 递归加载子图
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
                sub_state[agent.idx] = inp
                # 调用子图
                out = subgraph.invoke(sub_state)
                output=out[agent.outputs['name']]

                if isinstance(output, str):
                    output = safe_load(output)  # 先尝试反序列化
                # 第一次初始化
                if results is None:
                    if isinstance(output, list):
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
    state = set()
    # 收集 inputs 和 outputs.name
    for node in graphs[graph_id]["nodes"]:
        agent = MetaLoader.load("agents",node)
        if not agent:
            continue
        # inputs
        for inp in agent.get("inputs", []):
            state.add(inp)
        # outputs
        outputs = agent.get("outputs", {})
        if "name" in outputs:
            state.add(outputs["name"])


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