#service/meta/loader.py
from pathlib import Path
from typing import List, Dict, Any
import json
from logging import getLogger
from datetime import datetime
logger = getLogger(__name__)


def _get_path(name):
    path = Path(__file__).resolve().parent.parent.parent / "meta" / name
    path.mkdir(parents=True, exist_ok=True)
    return path


class MetaLoader:
    @staticmethod
    def load(name:str, id:str) -> Dict[str, Any] | None:
        try:
            path=_get_path(name)
            cfg_path = path  / f"{id}.json"
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            # 确保配置中有id字段
            cfg["id"] = id
            return cfg
        except FileNotFoundError as e:
            return None

    @staticmethod
    def loads(name) -> List[Dict[str, Any]] | None:
        try:
            path=_get_path(name)
            cfgs = []
            for file in path.glob("*.json"):
                cfg = json.loads(file.read_text(encoding="utf-8"))
                cfg['id'] = file.stem
                cfgs.append(cfg)
            return cfgs
        except FileNotFoundError as e:
            logger.error(e)
            return None

    @staticmethod
    def dump(name:str,id:str, data: Dict[str, Any]) -> bool:
        try:
            path=_get_path(name)
            cfg_path = path / f"{id}.json"
            # 确保目录存在
            data.pop("id", None)  # 防止前端乱传
            if 'created_at' not in data:
                data['created_at'] = datetime.now().isoformat()
            cfg_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return True
        except FileNotFoundError as e:
            logger.error(e)
            return False

    @staticmethod
    def count(name) -> int:
        path = _get_path(name)
        return len(list(path.glob("*.json")))

    @staticmethod
    def delete(name:str,id:str) -> bool:
        try:
            path = _get_path(name)
            file = path / f"{id}.json"
            file.unlink()
            return True
        except FileNotFoundError as e:
            logger.error(e)
            return False

    @staticmethod
    def exists(name:str, id:str) -> bool:
        path = _get_path(name)
        file = path / f"{id}.json"
        return file.exists()

    @staticmethod
    def update(name:str,id:str, data: Dict[str, Any]) -> bool:
        try:
            path = _get_path(name)
            cfg_path = path / f"{id}.json"
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            cfg['id'] = id
            cfg.update(data)
            cfg['updated_at'] = datetime.now().isoformat()
            cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
            return True
        except FileNotFoundError as e:
            logger.error(e)
            return False


class GraphMetaLoader:
    @staticmethod
    def load(graph_id: str):
        graphs_cfg = {}
        visited = set()

        def _load(gid):
            if gid in visited:
                return
            visited.add(gid)
            cfg = MetaLoader.load("graphs", gid)
            if not cfg:
                return
            if gid == graph_id:
                from utils.graphutils import rebase_workflow_variant_from_baseline

                cfg = rebase_workflow_variant_from_baseline(gid, dict(cfg))
            graphs_cfg[gid] = dict(cfg)
            graphs_cfg[gid]["id"] = gid
            for node in cfg.get("nodes", []):
                if node in ("START", "END"):
                    continue
                if MetaLoader.load("graphs", node):
                    _load(node)
            for bind_key in (cfg.get("bindings") or {}):
                if bind_key in ("START", "END"):
                    continue
                if MetaLoader.load("graphs", bind_key):
                    _load(bind_key)
            for fn in (cfg.get("flowNodes") or {}).values():
                if not isinstance(fn, dict):
                    continue
                sub_id = fn.get("subgraphId")
                if sub_id and MetaLoader.load("graphs", sub_id):
                    _load(sub_id)

        _load(graph_id)
        return graphs_cfg

    @staticmethod
    def load_agents_by_graph(graph, agents):
        for agent in graph.get('nodes', []):
            if agent in ('START', 'END'):
                continue
            a = MetaLoader.load("agents", agent)
            if a:
                agents[agent] = a
                if 'id' not in agents[agent]:
                    agents[agent]['id'] = agent
        return agents



