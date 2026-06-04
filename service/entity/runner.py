import json

from plugin.plugin_loader import get_plugin,aget_plugin
from service.entity.agent import AgentEntity
from service.entity.graph import GraphEntity
from service.entity.entity import Entity, EntityLoader
from typing import TypedDict, TypeVar, Dict, Any
from service.entity.test import TestLoader
from service.meta.loader import MetaLoader
from langchain_core.runnables import RunnableConfig
from pathlib import Path

T = TypeVar("T", bound=TypedDict)
RESULT_DIR = Path(__file__).resolve().parent.parent.parent  / "result"


def _apply_plugin_metrics(
    row: Dict[str, Any],
    values: Dict[str, Any],
    graph_id: str | None = None,
) -> Dict[str, Any]:
    """Attach precision/recall/f1 from graph metrics config + test row gold columns."""
    from utils.workflow_metrics import compute_workflow_metrics

    metrics = compute_workflow_metrics(graph_id, row or {}, values or {})
    if not metrics:
        return values
    out = dict(values)
    out["metrics"] = metrics
    return out


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

        from service.result.loader import (
            REPORT_CHART_SAMPLE_THRESHOLD,
            write_sample_full,
            write_states_bundle,
        )

        result = {}
        archive_full = total > REPORT_CHART_SAMPLE_THRESHOLD
        for idx in range(1, total + 1):
            config = {"configurable": {"thread_id": f"{exp_id}_{idx}"}}
            state = runner.get_state(config)
            if state and state.values:
                values = dict(state.values)
                row = rows[idx - 1] if idx - 1 < len(rows) else {}
                values = _apply_plugin_metrics(
                    row, values, graph_id=meta.get("runner_id")
                )
                result[str(idx)] = values
                if archive_full:
                    write_sample_full(exp_id, idx, values)

        if not result:
            import logging
            logging.getLogger(__name__).warning(
                "persistence: no checkpoint state for exp %s (samples=%s)", exp_id, total
            )
            return {}

        write_states_bundle(exp_id, result)
        return result

