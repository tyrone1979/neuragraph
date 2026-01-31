import json
from logging import getLogger
from langgraph.graph import StateGraph, START, END
from langgraph.types import Checkpointer
from service.entity.agent import AgentLoader
from service.entity.entity import Entity, EntityLoader
from typing import Dict, Any, Iterator
from service.meta.loader import MetaLoader
from utils.conversion import  T,jsonify_state
from utils.graphutils import compute_states,create_state_typeddict
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
        state=jsonify_state(state)
        if config:
            return self.compiled_graph.stream(state,config=config,
                                          stream_mode=stream_mode,
                                          subgraphs=True)
        else:
            return self.compiled_graph.stream(state,stream_mode=stream_mode,
                                          subgraphs=True)

    async def ainvoke(self, state: T,**kwargs):
        config=kwargs.get("config")
        state=jsonify_state(state)
        return self.compiled_graph.ainvoke(state,config=config)

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



