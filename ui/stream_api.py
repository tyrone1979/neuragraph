# stream_api.py
from flask import Blueprint, request, jsonify,Response
from service.entity.test import TestLoader
from langchain_core.runnables import RunnableConfig
from service.meta.loader import MetaLoader, GraphMetaLoader
from service.entity.agent import AgentLoader
from service.result.loader import (
    ResultLoader,
    build_report_payload_states,
    compact_sample_for_report,
    iter_sample_indices,
)
from service.entity.runner import _apply_plugin_metrics
from service.entity.runner import RunnerLoader
from plugin.plugin_loader import get_plugin
from utils.graphutils import collect_loop_stream_fields, is_loop_flow_node
import json
from datetime import datetime
import asyncio
sse_bp = Blueprint('sse', __name__, url_prefix='/stream')

def process(chunk, graph_id: str | None = None):
    if isinstance(chunk, str):
        pretty_text = format_agent_chunk(chunk)
        safe_chunk = pretty_text.replace("\n", "\\n")
        return f"data: {safe_chunk}\n\n"
    if isinstance(chunk, tuple):
        node_path, payload = chunk
        pretty_text = format_graph_chunk(node_path, payload, graph_id=graph_id)
        safe_chunk = pretty_text.replace("\n", "$$")
        return f"data: {safe_chunk}\n\n"
    if isinstance(chunk, (dict, list)):
        safe_chunk = json.dumps(chunk, ensure_ascii=False, default=str).replace("\n", "\\n")
        return f"data: {safe_chunk}\n\n"
    if chunk is None:
        return ""
    safe_chunk = str(chunk).replace("\n", "\\n")
    return f"data: {safe_chunk}\n\n"

def run(target_id,scope,form_data,config=None):

    try:
        def event_stream():
            runner = RunnerLoader.load(target_id)
            graph_id = None
            if runner is not None:
                meta = getattr(runner, "metadata", None) or {}
                graph_id = meta.get("id") or target_id
            try:
                for chunk in runner.stream(
                        form_data,
                        config=config,
                        stream_mode="updates",
                        subgraphs=True
                ):
                    completed_chunk = process(chunk, graph_id=graph_id)
                    if completed_chunk:
                        yield completed_chunk
            except Exception as ex:
                err = str(ex).replace("\n", "\\n")
                yield f"data: Stream error: {err}\n\n"
            yield "data: [DONE]\n\n"

        return Response(event_stream(), mimetype="text/event-stream")
    except Exception as e:
        return jsonify({'result': f'Error: {str(e)}'}), 500

@sse_bp.route('/test', methods=['GET'])
def stream_test():
    # 1. 一次性判断来源
    agent_id = request.args.get('agentId')
    graph_id = request.args.get('graphId')

    if agent_id:
        target_id, scope = agent_id, 'agent'
    elif graph_id:
        target_id, scope = graph_id, 'graph'
    else:
        return jsonify({'result': 'Missing agentId or graphId'}), 400

    # 2. 收集业务参数
    form_data = {k: v for k, v in request.args.items() if k not in {'agentId', 'graphId', 'testSet'}}
    datetime_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    config: RunnableConfig = {"configurable": {"thread_id": f'test_{datetime_str}'}}
    return run(target_id, scope, form_data,config)

def _is_metrics_list(obj) -> bool:
    """
    判断是否为 {idx: {'f1': float, 'precision': float, 'recall': float}, ...}
    """
    if not isinstance(obj, dict):
        return False
    # 空 dict 也算合格
    if not obj:
        return True
    # 抽检第一个 value
    sample = next(iter(obj.values()))
    return (
        isinstance(sample, dict) and
        {'f1', 'precision', 'recall'}.issubset(sample.keys())
    )

def _snapshot_for_report(
    row: dict | None, state: dict, graph_id: str | None = None
) -> dict:
    """Prefer metrics; otherwise compute from gold columns or compact state."""
    if isinstance(state, dict) and state.get("metrics"):
        return state["metrics"]
    if row and isinstance(state, dict):
        enriched = _apply_plugin_metrics(row, dict(state), graph_id=graph_id)
        if enriched.get("metrics"):
            return enriched["metrics"]
    return compact_sample_for_report(state)


def _load_report_snapshots(exp_id: str, exp_cfg: dict) -> dict:
    snapshots: dict = {}
    results = ResultLoader.load(exp_id)
    rows: list[dict] = []
    if exp_cfg.get("runner_id") and exp_cfg.get("dataset"):
        try:
            _fields, rows = TestLoader.load_by_id_file(
                exp_cfg["runner_id"], exp_cfg["dataset"]
            )
            rows = [dict(r) for r in rows]
        except Exception:
            rows = []

    if results:
        for idx in iter_sample_indices(results):
            row = rows[int(idx) - 1] if int(idx) - 1 < len(rows) else {}
            state = results[idx]
            if isinstance(state, dict):
                snapshots[idx] = _snapshot_for_report(
                    row, state, graph_id=exp_cfg.get("runner_id")
                )
            else:
                snapshots[idx] = state
        return snapshots

    runner_id = exp_cfg.get("runner_id")
    dataset = exp_cfg.get("dataset")
    if not runner_id or not dataset:
        return snapshots
    runner = RunnerLoader.load(runner_id)
    if runner is None:
        return snapshots
    for idx, row in enumerate(rows, start=1):
        config: RunnableConfig = {"configurable": {"thread_id": f"{exp_id}_{idx}"}}
        state = runner.get_state(config)
        values = state.values if state and isinstance(state.values, dict) else {}
        if values:
            snapshots[str(idx)] = _snapshot_for_report(
                row, values, graph_id=runner_id
            )
    return snapshots


def _load_report_agents(graphs_cfg: dict[str, dict]) -> dict[str, dict]:
    """Collect all agent meta referenced by the experiment graph package."""
    agents: dict[str, dict] = {}
    for graph in graphs_cfg.values():
        GraphMetaLoader.load_agents_by_graph(graph, agents)
    return agents


def _resolve_report_agent_versions(
    graphs_cfg: dict[str, dict],
    agents_cfg: dict[str, dict],
    *,
    root_graph_id: str = "",
) -> dict:
    from utils.graphutils import resolve_report_agent_versions

    return resolve_report_agent_versions(
        graphs_cfg, agents_cfg, root_graph_id=root_graph_id
    )


def _build_report_payload(exp_id: str, exp_cfg: dict) -> dict:
    """
    Build full report payload for LLM:
    - experiment config
    - executed graph (including subgraphs when present)
    - all agent meta used by those graphs
    - full states.json content
    """
    runner_id = exp_cfg.get("runner_id")
    graphs_cfg: dict[str, dict] = {}
    if runner_id:
        graphs_cfg = GraphMetaLoader.load(runner_id) or {}

    agents_cfg = _load_report_agents(graphs_cfg)
    agent_versions = _resolve_report_agent_versions(
        graphs_cfg, agents_cfg, root_graph_id=str(runner_id or "")
    )

    raw_states = ResultLoader.load(exp_id)
    if not raw_states:
        exp_for_persistence = dict(exp_cfg)
        exp_for_persistence["exp_id"] = exp_id
        try:
            RunnerLoader.persistence(exp_for_persistence)
            raw_states = ResultLoader.load(exp_id)
        except Exception:
            raw_states = None

    states = build_report_payload_states(raw_states or {}, exp_id=exp_id)

    return {
        "exp_id": exp_id,
        "experiment": exp_cfg,
        "graphs": graphs_cfg,
        "agents": agents_cfg,
        "agent_versions": agent_versions,
        "states": states,
    }


@sse_bp.route('/report/<exp_id>', methods=['GET'])
def stream_report(exp_id):
    exp_cfg = MetaLoader.load("exps", exp_id)
    if not exp_cfg:
        return Response(f"Experiment {exp_id} not found.", mimetype='text/event-stream')
    if exp_cfg.get('status') != 'completed':
        error = f"The experiment {exp_id} is not completed yet."
        return Response(error, mimetype='text/event-stream')

    full_payload = _build_report_payload(exp_id, exp_cfg)
    if not full_payload.get("states"):
        msg = (
            f"No experiment results found for {exp_id}. "
            f"Expected result/{exp_id}/states.json or checkpoint state."
        )
        return Response(msg, mimetype='text/event-stream')

    use_tools = str(request.args.get("use_tools", "0")).lower() in ("1", "true", "yes", "on")
    report_agent_id = "report_experiment_tool" if use_tools else "report_experiment"
    agent = AgentLoader.load(report_agent_id)
    if agent is None:
        msg = f"Report agent not found: {report_agent_id}"
        return Response(msg, mimetype='text/event-stream')
    text_payload = json.dumps(full_payload, ensure_ascii=False, separators=(",", ":"))

    def generate():
        chunk = agent.invoke({'text': text_payload})
        safe_chunk = chunk['text'].replace("\n", "\\n")
        yield f"data: {safe_chunk}\n\n"
        yield "data: [DONE]\n\n"
    return Response(generate(), mimetype='text/event-stream')



@sse_bp.route('/run/<exp_id>', methods=['GET'])
def stream_exp_batch(exp_id):
    """Batch-run experiment samples. Uses sync graph.invoke (same as local runner) to avoid
    nested asyncio event-loop deadlocks inside Flask SSE workers."""
    exp_cfg = MetaLoader.load("exps", exp_id)
    dataset = exp_cfg["dataset"]
    runner_id = exp_cfg["runner_id"]
    _fields, data = TestLoader.load_by_id_file(runner_id, dataset)
    total = len(data)
    exp_cfg["exp_id"] = exp_id

    def generate():
        runner = RunnerLoader.load(runner_id)
        if runner is None:
            yield f'data: {json.dumps({"status": "failed", "error": f"runner not found: {runner_id}"})}\n\n'
            yield "data: [DONE]\n\n"
            return

        completed = 0
        for idx, row in enumerate(data, start=1):
            config: RunnableConfig = {"configurable": {"thread_id": f"{exp_id}_{idx}"}}
            try:
                running_msg = {
                    "status": "running",
                    "batch_status": "running",
                    "percent": int(completed / total * 100) if total else 0,
                    "completed": completed,
                    "total": total,
                    "current_index": idx,
                }
                yield f"data: {json.dumps(running_msg)}\n\n"

                if hasattr(runner, "compiled_graph"):
                    runner.compiled_graph.invoke(dict(row), config=config)
                else:
                    runner.invoke(dict(row), config=config)

                completed += 1
                try:
                    RunnerLoader.persistence(exp_cfg)
                    MetaLoader.update(
                        "exps",
                        exp_id,
                        {
                            "progress": int(completed / total * 100) if total else 100,
                            "status": "running" if completed < total else "completed",
                        },
                    )
                except Exception as persist_ex:
                    err = {"status": "failed", "error": f"persistence: {persist_ex}"}
                    yield f"data: {json.dumps(err)}\n\n"

                done_msg = {
                    "status": "completed",
                    "batch_status": "completed" if completed >= total else "running",
                    "percent": int(completed / total * 100) if total else 100,
                    "completed": completed,
                    "total": total,
                    "current_index": idx,
                }
                yield f"data: {json.dumps(done_msg)}\n\n"
            except Exception as e:
                msg = {
                    "status": "failed",
                    "percent": int(completed / total * 100) if total else 0,
                    "completed": completed,
                    "total": total,
                    "current_index": idx,
                    "error": str(e),
                }
                yield f"data: {json.dumps(msg)}\n\n"
                break
        yield "data: [DONE]\n\n"

    return Response(generate(), mimetype="text/event-stream")


import textwrap
from typing import List


def ascii_block(value) -> str:
    # ------------------- 1. 统一转为行列表 -------------------
    if isinstance(value, list):
        raw_lines = [str(v).strip() for v in value if str(v).strip()]
    elif isinstance(value, str):
        raw_lines = [line.rstrip() for line in value.splitlines() if line.strip()]
    else:
        return str(value)


    if not raw_lines:
        return ""

    # ------------------- 2. 先判断是否可能是 CoNLL-U -------------------
    # 特征：大部分行有 \t，且行数 > 3，且很多行以数字开头
    is_conllu = (
        any('\t' in line for line in raw_lines) and
        len(raw_lines) > 3 and
        any(line.split('\t')[0].isdigit() for line in raw_lines if '\t' in line)
    )

    if is_conllu:
        return _render_conllu(raw_lines)

    # ------------------- 3. 再判断是否是 | 分隔的表格 -------------------
    if any('|' in line for line in raw_lines):
        return _render_pipe_table(raw_lines)

    # ------------------- 4. 普通多行或 bullet list -------------------
    if len(raw_lines) > 1:
        if isinstance(value, list):
            return '\n'.join(f"- {line}" for line in raw_lines)
        else:
            return '\n'.join(raw_lines)
    else:
        return raw_lines[0] if raw_lines else ""


def _render_conllu(lines: List[str]) -> str:
    # CoNLL-U 固定 10 列
    COLUMNS = 10
    col_names = ["ID", "FORM", "LEMMA", "UPOS", "XPOS", "FEATS", "HEAD", "DEPREL", "DEPS", "MISC"]

    # 解析每一行，确保补齐到 10 列（用 _ 填充）
    rows = []
    for line in lines:
        if not line.strip() or line.startswith('#'):  # 注释或空行保留原样
            rows.append([line])
            continue
        parts = line.split('\t')
        # 补齐到 10 列
        parts += ['_'] * (COLUMNS - len(parts))
        parts = parts[:COLUMNS]  # 防止超长
        rows.append(parts)

    if not rows:
        return "(empty CoNLL-U)"

    # 计算每列最大宽度
    widths = [0] * COLUMNS
    for row in rows:
        if len(row) == 1:  # 注释行
            continue
        for i in range(COLUMNS):
            widths[i] = max(widths[i], len(row[i]))

    # 列宽至少容纳表头
    for i in range(COLUMNS):
        widths[i] = max(widths[i], len(col_names[i]))

    # 加点 padding
    widths = [w + 2 for w in widths]

    sep = '+' + '+'.join('-' * w for w in widths) + '+'

    result = [sep]
    # 表头
    header = '|' + '|'.join(col_names[i].center(widths[i]) for i in range(COLUMNS)) + '|'
    result.append(header)
    result.append(sep)

    # 数据行
    for row in rows:
        if len(row) == 1:  # 注释或空行
            result.append(row[0])  # 原样输出
            continue
        line = '|'
        for i in range(COLUMNS):
            cell = row[i] if i < len(row) else '_'
            line += cell.ljust(widths[i]) + '|'
        result.append(line)
    result.append(sep)

    return '\n'.join(result)


def _render_pipe_table(lines: List[str]) -> str:
    rows = [line.split('|') for line in lines]
    col_cnt = max(len(r) for r in rows) if rows else 1

    MAX_COL_W = 30
    wrapped = []
    for row in rows:
        wrapped_row = [textwrap.wrap(cell.strip(), MAX_COL_W) or [''] for cell in row]
        while len(wrapped_row) < col_cnt:
            wrapped_row.append([''])
        wrapped.append(wrapped_row)

    heights = [max(len(cell) for cell in row) for row in wrapped]
    widths = [0] * col_cnt
    for col in range(col_cnt):
        max_w = 0
        for row in wrapped:
            for line in row[col]:
                max_w = max(max_w, len(line))
        widths[col] = max_w + 2

    sep = '+' + '+'.join('-' * w for w in widths) + '+'

    result = [sep]
    # 表头
    header = '|' + '|'.join(f'Col{i+1}'.center(widths[i]) for i in range(col_cnt)) + '|'
    result.append(header)
    result.append(sep)

    for h, row in zip(heights, wrapped):
        for ln in range(h):
            line = '|'
            for col in range(col_cnt):
                text = row[col][ln] if ln < len(row[col]) else ''
                line += text.ljust(widths[col]) + '|'
            result.append(line)
        result.append(sep)

    return '\n'.join(result)

def format_agent_chunk(payload):
    #block = ascii_block(payload)
    block=payload
    return block

def format_graph_chunk(node_path, payload, graph_id: str | None = None):
    path_parts = []
    for item in node_path:
        if isinstance(item, str) and ':' in item:
            path_parts.append(item.split(':')[0])
        else:
            path_parts.append(f"#{item}")

    if not isinstance(payload, dict) or not payload:
        return ''

    blocks = []
    for current_node, value in payload.items():
        full_path_parts = path_parts + [str(current_node)]
        node_path_str = " -> ".join(full_path_parts) if full_path_parts else "START"
        loop_stream_fields = None
        if graph_id and is_loop_flow_node(graph_id, str(current_node)):
            loop_stream_fields = collect_loop_stream_fields(graph_id, str(current_node))
        if isinstance(value, dict):
            for field_name, content in value.items():
                if loop_stream_fields is not None and field_name not in loop_stream_fields:
                    continue
                block = ascii_block(content)
                blocks.append(
                    f"Node Path: {node_path_str}\n"
                    f"Output: {current_node} | Field: {field_name}\n"
                    f"{block}\n"
                    + "-" * 60 + "\n"
                )
        else:
            block = ascii_block(value)
            blocks.append(
                f"Node Path: {node_path_str}\n"
                f"Output: {current_node}\n"
                f"{block}\n"
                + "-" * 60 + "\n"
            )
    return "\n".join(blocks)