import json

from plugin.plugin_loader import get_plugin,aget_plugin
from service.entity.agent import AgentEntity
from service.entity.graph import GraphEntity
from service.entity.entity import Entity, EntityLoader
from typing import TypedDict, TypeVar, Dict, Any
from service.entity.test import TestLoader
from service.eval.gold_metrics import evaluate_sample
from service.meta.loader import MetaLoader
from langchain_core.runnables import RunnableConfig
from pathlib import Path

T = TypeVar("T", bound=TypedDict)
RESULT_DIR = Path(__file__).resolve().parent.parent.parent  / "result"

def _seek_checkpointer():
    postgres_checkpoint = get_plugin("AsyncPostgresSaver")
    if postgres_checkpoint:
            return postgres_checkpoint
    return get_plugin("InMemorySaver")

async def _seek_acheckpointer():
    postgres_checkpoint =await aget_plugin("PostgresSaver")
    if postgres_checkpoint:
            return postgres_checkpoint
    return get_plugin("InMemorySaver")

class RunnerLoader(EntityLoader):

    @staticmethod
    def load(id: str,**extra_params) -> Entity | None:
        checkpointer = _seek_checkpointer()
        meta = MetaLoader.load("agents", id)
        if meta and not meta['type']=="SUB":
                return AgentEntity(meta, checkpointer=checkpointer)
        else:
                meta = MetaLoader.load("graphs",id)
                return GraphEntity(meta, checkpointer=checkpointer)

    @staticmethod
    async def aload(id: str,**extra_params) -> Entity | None:
        checkpointer = _seek_checkpointer()
        meta=MetaLoader.load("agents",id)
        if meta:
            return AgentEntity(meta, checkpointer=checkpointer)
        else:
            meta = MetaLoader.load("graphs",id)
            return GraphEntity(meta, checkpointer=checkpointer)

    @staticmethod
    def persistence(meta: Dict[str, Any]) -> None:
        exp_id = meta["exp_id"]
        path = RESULT_DIR / exp_id
        path.mkdir(parents=True, exist_ok=True)

        runner = RunnerLoader.load(meta["runner_id"])
        rows = []
        try:
            _, rows = TestLoader.load_by_id_file(meta["runner_id"], meta.get("dataset", ""))
        except Exception:
            rows = []
        total = len(rows) if rows else int(meta.get("samples") or 0)

        result = {}
        for idx in range(1, total + 1):
            config = {"configurable": {"thread_id": f"{exp_id}_{idx}"}}
            state = runner.get_state(config)
            if state and state.values:
                values = dict(state.values)
                row = rows[idx - 1] if idx - 1 < len(rows) else {}
                metrics = evaluate_sample(row, values)
                if metrics:
                    values["metrics"] = metrics
                result[str(idx)] = values

        # 写入文件
        (path / "states.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return result

