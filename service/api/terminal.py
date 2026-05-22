"""
service/api/terminal.py
终端程序直接调用 service 层的统一入口。
和 Flask 后端共用同一套 AgentEntity / GraphEntity / RunnerLoader。
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from service.entity.runner import RunnerLoader
from service.meta.loader import MetaLoader


class TerminalRunner:
    """终端统一执行器——直接复用 service 层 RunnerLoader。"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def run(self, target_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        智能分发：先尝试 agent，再尝试 graph。
        和 Flask 后端调用方式完全一致。
        """
        meta_agent = MetaLoader.load("agents", target_id)
        if meta_agent and meta_agent.get("type") != "SUB":
            return self._run_agent(target_id, inputs)

        meta_graph = MetaLoader.load("graphs", target_id)
        if meta_graph:
            return self._run_graph(target_id, inputs)

        return {"status": "error", "message": f"'{target_id}' not found as agent or graph"}

    def run_agent(self, agent_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return self._run_agent(agent_id, inputs)

    def run_graph(self, graph_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return self._run_graph(graph_id, inputs)

    def _run_agent(self, agent_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        try:
            runner = RunnerLoader.load(agent_id)
            if not runner:
                return {"status": "error", "message": f"Agent '{agent_id}' not found"}
            result = runner.invoke(inputs)
            return {"status": "success", "result": result}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def _run_graph(self, graph_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        try:
            runner = RunnerLoader.load(graph_id)
            if not runner:
                return {"status": "error", "message": f"Graph '{graph_id}' not found"}
            result = runner.invoke(inputs)
            return {"status": "success", "result": result}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}


def draw_workflow(graph_id: str) -> str:
    """为终端绘制 workflow 结构图。"""
    meta = MetaLoader.load("graphs", graph_id)
    if not meta:
        return f"[Workflow '{graph_id}' not found]"

    nodes = meta.get("nodes", [])
    edges = meta.get("edges", [])

    lines = [f"   Workflow: {meta.get('name', graph_id)}", "   " + "-" * 50]

    # 获取 agent 类型和名称
    node_info = {}
    for n in nodes:
        if n in ("START", "END"):
            continue
        am = MetaLoader.load("agents", n)
        t = am.get("type", "?") if am else "?"
        name = am.get("name", n) if am else n
        node_info[n] = f"[{t}] {name}"

    # 按边顺序展示
    edge_map = {e[0]: e[1] for e in edges if len(e) >= 2}
    lines.append("    START   -->")
    current = "START"
    while current in edge_map:
        nxt = edge_map[current]
        if nxt == "END":
            break
        lines.append(f"       --> {node_info.get(nxt, nxt)}")
        current = nxt
    lines.append("       -->  END")
    lines.append("   " + "-" * 50)
    return "\n".join(lines)


def list_configs(name: str) -> List[Dict]:
    cfgs = MetaLoader.loads(name)
    return cfgs or []


def config_exists(name: str, cid: str) -> bool:
    return MetaLoader.exists(name, cid)


def save_config(name: str, cid: str, data: Dict) -> bool:
    return MetaLoader.dump(name, cid, data)


def load_config(name: str, cid: str) -> Optional[Dict]:
    return MetaLoader.load(name, cid)
