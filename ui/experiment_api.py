# exp_api.py
from flask import Blueprint,  render_template, request, jsonify, Response
import uuid
import json
import time
import threading
import random
from datetime import datetime
from pathlib import Path
from ui.components.paginated_api import get_paginated_data
from service.result.loader import ResultLoader, iter_sample_indices
from dataclasses import is_dataclass,asdict
from langchain_core.runnables import RunnableConfig

from service.entity.test import TestLoader
from service.meta.loader import MetaLoader, GraphMetaLoader
from service.entity.runner import RunnerLoader
from service.experiment_optimize import (
    run_optimize_loop_by_exp,
    run_optimize_loop_by_exp_with_progress,
    optimization_preflight,
    generate_baseline_test_report,
    init_optimization_flow_steps,
)
from service.optimization_pipeline import (
    FLOW_STEP_ORDER,
    optimization_flow_state,
    run_optimization_pipeline,
    run_optimization_step,
)
exp_bp = Blueprint('exp', __name__, url_prefix='/exp')

_optimize_tasks: dict[str, dict] = {}
_optimize_lock = threading.Lock()
_ROOT = Path(__file__).resolve().parent.parent


def _resolve_runner_agent_roster(runner_id: str) -> list[dict]:
    """List agents in a workflow (including subgraphs) with pinned versions."""
    rid = str(runner_id or "").strip()
    if not rid:
        return []
    agent_meta = MetaLoader.load("agents", rid)
    graph_meta = MetaLoader.load("graphs", rid)
    if agent_meta and not graph_meta:
        return [
            {
                "agent_id": rid,
                "name": str(agent_meta.get("name") or rid),
                "version": "current",
                "graph_id": "",
            }
        ]
    graphs_cfg = GraphMetaLoader.load(rid) or {}
    roster: dict[str, dict] = {}
    for gid, g in graphs_cfg.items():
        pinned = (g or {}).get("agentVersions") or {}
        for node in (g or {}).get("nodes", []):
            if node in ("START", "END"):
                continue
            if MetaLoader.load("graphs", node):
                continue
            am = MetaLoader.load("agents", node)
            if not am:
                continue
            roster[node] = {
                "agent_id": node,
                "name": str(am.get("name") or node),
                "version": str(pinned.get(node) or "current"),
                "graph_id": gid if gid != rid else "",
            }
    return sorted(roster.values(), key=lambda x: x["agent_id"])


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def _normalize_dataset_name(name: str) -> str:
    raw = str(name or "").strip()
    if not raw:
        return ""
    if raw.lower().endswith(".csv") or raw.lower().endswith(".txt"):
        return raw
    return f"{raw}.csv"


def _resolve_exp_datasets(exp_cfg: dict) -> tuple[str, str]:
    tuning = str(exp_cfg.get("tuning_dataset") or "").strip()
    test = str(exp_cfg.get("test_dataset") or "").strip()
    legacy = str(exp_cfg.get("dataset") or "").strip()
    if not tuning:
        tuning = legacy or test
    if not test:
        test = legacy or tuning
    if not tuning and test:
        tuning = test
    if not test and tuning:
        test = tuning
    return tuning, test


def _auto_split_dataset(
    *,
    runner_id: str,
    source_dataset: str,
    split_ratio: float = 0.8,
    seed: int = 42,
) -> dict:
    source_dataset = _normalize_dataset_name(source_dataset)
    if not source_dataset.lower().endswith(".csv"):
        raise ValueError("auto split currently supports CSV source datasets only")
    fields, rows = TestLoader.load_by_id_file(runner_id, source_dataset)
    if not rows:
        raise ValueError(f"source dataset has no rows: {source_dataset}")
    ratio = min(0.95, max(0.05, float(split_ratio)))
    rng = random.Random(int(seed))
    row_list = [dict(r) for r in rows]
    rng.shuffle(row_list)
    split_idx = max(1, min(len(row_list) - 1, int(round(len(row_list) * ratio))))
    tuning_rows = row_list[:split_idx]
    test_rows = row_list[split_idx:]
    src_stem = Path(source_dataset).stem
    suffix = datetime.now().strftime("%Y%m%d%H%M%S")
    tuning_name = f"{src_stem}__tune_r{int(ratio*100)}_s{int(seed)}_{suffix}.csv"
    test_name = f"{src_stem}__test_r{int((1-ratio)*100)}_s{int(seed)}_{suffix}.csv"
    TestLoader.save_csv_rows(runner_id, tuning_name, fields, tuning_rows)
    TestLoader.save_csv_rows(runner_id, test_name, fields, test_rows)
    return {
        "tuning_dataset": tuning_name,
        "test_dataset": test_name,
        "dataset_split": {
            "mode": "auto",
            "source_dataset": source_dataset,
            "split_ratio": ratio,
            "seed": int(seed),
            "tuning_count": len(tuning_rows),
            "test_count": len(test_rows),
        },
    }


def _build_report_chart_payload(exp_id: str) -> dict:
    states = ResultLoader.load(exp_id) or {}
    sample_ids = iter_sample_indices(states)
    per_sample = []
    fp_by_sample = []
    fn_by_sample = []
    tp_by_sample = []
    p_sum = 0.0
    r_sum = 0.0
    f1_sum = 0.0
    rel_tp_sum = 0
    rel_fp_sum = 0
    rel_fn_sum = 0
    count = 0
    for sid in sample_ids:
        item = states.get(sid) or {}
        metrics = item.get("metrics") if isinstance(item, dict) else {}
        p = _safe_float((metrics or {}).get("precision"), 0.0)
        r = _safe_float((metrics or {}).get("recall"), 0.0)
        f1 = _safe_float((metrics or {}).get("f1"), 0.0)
        rel_tp = int(_safe_float((metrics or {}).get("rel_tp"), 0.0))
        rel_fp = int(_safe_float((metrics or {}).get("rel_fp"), 0.0))
        rel_fn = int(_safe_float((metrics or {}).get("rel_fn"), 0.0))
        p_sum += p
        r_sum += r
        f1_sum += f1
        rel_tp_sum += rel_tp
        rel_fp_sum += rel_fp
        rel_fn_sum += rel_fn
        count += 1
        per_sample.append(
            {
                "sample_id": int(sid),
                "precision": p,
                "recall": r,
                "f1": f1,
            }
        )
        fp_by_sample.append({"sample_id": int(sid), "value": rel_fp})
        fn_by_sample.append({"sample_id": int(sid), "value": rel_fn})
        tp_by_sample.append({"sample_id": int(sid), "value": rel_tp})

    if count == 0:
        overall = {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    else:
        overall = {
            "precision": p_sum / count,
            "recall": r_sum / count,
            "f1": f1_sum / count,
        }

    return {
        "exp_id": exp_id,
        "sample_count": count,
        "overall": overall,
        "per_sample": per_sample,
        "error_buckets": {
            "rel_tp": rel_tp_sum,
            "rel_fp": rel_fp_sum,
            "rel_fn": rel_fn_sum,
        },
        "error_by_sample": {
            "rel_tp": tp_by_sample,
            "rel_fp": fp_by_sample,
            "rel_fn": fn_by_sample,
        },
        "agent_version_impact": _load_agent_version_impact(),
    }


def _load_agent_version_impact() -> list[dict]:
    """
    Build best-effort agent impact stats from optimize summaries.
    Source: result/opt_compare_*.json
    """
    result_dir = _ROOT / "result"
    if not result_dir.exists():
        return []
    items = sorted(result_dir.glob("opt_compare_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    agg: dict[str, dict] = {}
    for path in items[:20]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rounds = data.get("rounds") or []
        if not isinstance(rounds, list):
            continue
        for r in rounds:
            if not isinstance(r, dict):
                continue
            agent_id = str(r.get("target_agent_id") or "").strip()
            if not agent_id:
                continue
            metrics_delta = r.get("metrics_delta") or {}
            f1_delta = _safe_float((metrics_delta or {}).get("f1"), 0.0)
            accepted = bool(r.get("accepted"))
            slot = agg.setdefault(
                agent_id,
                {
                    "agent_id": agent_id,
                    "attempts": 0,
                    "accepted_rounds": 0,
                    "best_f1_delta": -999.0,
                    "latest_f1_delta": 0.0,
                },
            )
            slot["attempts"] += 1
            if accepted:
                slot["accepted_rounds"] += 1
            if f1_delta > slot["best_f1_delta"]:
                slot["best_f1_delta"] = f1_delta
            slot["latest_f1_delta"] = f1_delta
    out = list(agg.values())
    out.sort(key=lambda x: (x.get("best_f1_delta", -999.0), x.get("accepted_rounds", 0)), reverse=True)
    return out[:10]

def render_list(search='',page=1,per_page=20):
    all_history = MetaLoader.loads("exps")  # 你的函数，返回 list of dict
    all_history.sort(key=lambda d: d.get("created_at") or "1970-01-01T00:00:00", reverse=True)
    # 搜索：runner 或 dataset
    if search:
        search_lower = search.lower()
        all_history = [e for e in all_history
                       if search_lower in e.get('config', {}).get('runner', '').lower()
                       or search_lower in e.get('config', {}).get('dataset', '').lower()
                       or search_lower in e.get('config', {}).get('tuning_dataset', '').lower()
                       or search_lower in e.get('config', {}).get('test_dataset', '').lower()]

    total = len(all_history)
    start = (page - 1) * per_page
    end = start + per_page
    page_history = all_history[start:end]

    # 预处理显示字段
    processed = []
    for e in page_history:
        tuning, test = _resolve_exp_datasets(e)
        item = {
            'name': f'<a href="/exp/{e["exp_id"]}" class="text-decoration-none fw-bold">{e["name"] or "Untitled"}</a>',
            'runner': f'<code class="small text-muted">{e.get("runner_id", "N/A")}</code>',
            'type': f'<span class="badge text-bg-secondary">{e["runner_type"].upper()}</span>',
            'dataset_file': (
                f'<div class="small"><span class="text-muted">test:</span> '
                f'<span class="text-monospace">{test}</span></div>'
                f'<div class="small"><span class="text-muted">tuning:</span> '
                f'<span class="text-monospace">{tuning}</span></div>'
            ),
            'samples': f'<strong>{e["samples"]:,}</strong>',  # 千分位分隔，数字好看
            'created_at': f'<span class="text-muted small">{e["created_at"][:19].replace("T", " ")}</span>',
            'status': {
                'completed': '<span class="badge text-bg-success">Completed</span>',
                'running': '<span class="badge text-bg-primary">Running</span>',
                'pending': '<span class="badge text-bg-warning">Pending</span>',
                'failed': '<span class="badge text-bg-danger">Failed</span>',
            }.get(e.get('status', 'unknown').lower(), '<span class="badge text-bg-secondary">Unknown</span>'),
            'actions': f'''
                <a href="/exp/delete/{e["exp_id"]}" class="btn btn-outline-danger" title="Delete" 
                       onclick="return confirm('Please confirm to delete.')">
                        <i class="fas fa-trash"></i>
                </a>
            '''
        }
        processed.append(item)

    return render_template(
        'experiment_list.html',
        history=processed,
        page=page,
        per_page=per_page,
        total=total,
        search=search,
        active_page='exp'
    )

def render_html(
    template,
    runner_id,
    test_file,
    runner_type,
    runner_display,
    progress,
    exp_id,
    tuning_file="",
    **extra_context,
):
    graphs = MetaLoader.loads("graphs")  # 或你原来的加载方式，返回 dict
    agents = MetaLoader.loads("agents")

    preview_page = 1
    preview_per_page = 10
    preview_total = 0
    fields=[]
    preview_items=[]
    tests=[]
    snapshots={}

    selected_dataset = test_file or tuning_file
    if runner_id:
        tests = TestLoader.get_by_agent(runner_id)
    if runner_id and selected_dataset:
        fields, raw_data = TestLoader.load_by_id_file(runner_id, selected_dataset)

        # 分页
        page_items, preview_page, preview_per_page, preview_total, _ = get_paginated_data(
                raw_data,
                per_page=preview_per_page,
                search_fields=fields
            )
        results=ResultLoader.load(exp_id)
        for idx, item in enumerate(page_items, start=(preview_page - 1) * preview_per_page + 1):
            if is_dataclass(item):
                # 如果是 dataclass，使用 asdict() 转换为字典
                item_dict = asdict(item)
            else:
                item_dict = dict(item)  # 转 dict 方便加字段
            item_dict['#'] = idx  # 第一列序号
            idx_str=str(idx)
            if results and idx_str in results:
                item_dict['status'] = '<span class="badge text-bg-success">Completed</span>'
                item_dict['actions'] = f'''<a class="btn btn-outline-info btn-replay" title="Replay" data-index='{idx}'>
                                                                                              <i class="fas fa-play"></i></a>'''
                # Keep inline JSON small (full state can be MB for long CID articles).
                row_result = results[idx_str]
                if isinstance(row_result, dict) and "metrics" in row_result:
                    snapshots[idx] = {"metrics": row_result["metrics"]}
                else:
                    snapshots[idx] = row_result
            else:
                item_dict['status'] = '<span class="badge text-bg-warning">Pending</span>'
                item_dict['actions'] = ''
            preview_items.append(item_dict)

    display_fields=['#']+fields+['status','actions']
    # 构建extra_params字典
    extra_params = {}
    if runner_id:
        extra_params['runner_id'] = runner_id
    if runner_type:
        extra_params['runner_type'] = runner_type
    if runner_display:
        extra_params['runner_display'] = runner_display
    if test_file:
        extra_params['filename'] = test_file
    if tuning_file:
        extra_params['tuning_filename'] = tuning_file


    flow_steps = init_optimization_flow_steps()
    if exp_id:
        try:
            flow_steps = optimization_preflight(exp_id).get("flow_steps") or flow_steps
        except Exception:
            pass

    # Client JS only needs filenames + counts (full row payloads break inline JSON / bloat DOM).
    dataset_options = [{"name": t["name"], "count": t["count"]} for t in tests]
    base_context = {
        'datasets': dataset_options,
        'active_page': 'exp',
        'runner_type': runner_type,
        'runner_id': runner_id,
        'runner_display': runner_display,
        'filename': test_file,
        'tuning_filename': tuning_file,
        'dataset_split': {},
        'preview_tests': preview_items,
        'preview_page': preview_page,
        'preview_per_page': preview_per_page,
        'preview_total': preview_total,
        'preview_fields': display_fields,
        'extra_params': extra_params,
        'graphs' : graphs,
        'agents' : agents,
        'progress' : progress,
        'exp_id': exp_id,
        'snapshots':snapshots,
        'optimization_flow_steps': flow_steps,
        'selected_file': selected_dataset,
        'runner_agent_roster': _resolve_runner_agent_roster(runner_id),
    }
    # 合并额外传进来的参数（比如 exp_id, exp_name 等）
    base_context.update(extra_context)
    return render_template(template,**base_context)


@exp_bp.route('/new')
def experiment_new():
    runner_id = request.args.get('runner_id', '').strip()
    runner_type=request.args.get('runner_type','').strip()
    runner_display=request.args.get('runner_display','').strip()
    test_file = request.args.get('filename', '').strip()
    tuning_file = request.args.get('tuning_filename', '').strip()

    return render_html(
        'experiment.html',
        runner_id=runner_id,
        test_file=test_file,
        runner_type=runner_type,
        runner_display=runner_display,
        progress=0,
        exp_id='',
        tuning_file=tuning_file,
    )

@exp_bp.route('/delete/<exp_id>',methods=["GET"])
def experiment_delete(exp_id):
    MetaLoader.delete("exps",exp_id)
    return render_list()


@exp_bp.route('/')
def experiment_list():
    page = int(request.args.get('page', 1))
    per_page = 20
    search = request.args.get('search', '').strip()
    return render_list(search,page,per_page)

@exp_bp.route('/api/list')
def api_list_experiments():
    all_history = MetaLoader.loads("exps")
    all_history.sort(key=lambda d: d.get("created_at") or "1970-01-01T00:00:00", reverse=True)
    result = []
    for e in all_history:
        tuning_dataset, test_dataset = _resolve_exp_datasets(e)
        result.append({
            'id': e.get('exp_id', ''),
            'name': e.get('name', 'Untitled'),
            'status': e.get('status', 'unknown'),
            'progress': e.get('progress', 0),
            'runner_id': e.get('runner_id', ''),
            'runner_type': e.get('runner_type', ''),
            'dataset': e.get('dataset', ''),
            'tuning_dataset': tuning_dataset,
            'test_dataset': test_dataset,
            'samples': e.get('samples', 0),
            'created_at': e.get('created_at', '')
        })
    return jsonify(result)

@exp_bp.route('/<exp_id>')
def experiment_detail(exp_id):
    exp_cfg=MetaLoader.load("exps",exp_id)
    runner_id=exp_cfg['runner_id']
    runner_type=exp_cfg['runner_type']
    runner_display=exp_cfg['runner_display']
    tuning_dataset, test_dataset = _resolve_exp_datasets(exp_cfg)
    return render_html(
        'experiment.html',
        runner_id=runner_id,
        test_file=test_dataset,
        runner_type=runner_type,
        runner_display=runner_display,
        exp_id=exp_cfg['exp_id'],
        progress=exp_cfg['progress'],
        tuning_file=tuning_dataset,
        dataset_split=exp_cfg.get('dataset_split') or {},
    )

@exp_bp.route('/api/<exp_id>')
def api_experiment_detail(exp_id):
    """Return experiment details as JSON."""
    try:
        exp_cfg = MetaLoader.load("exps", exp_id)
        tuning_dataset, test_dataset = _resolve_exp_datasets(exp_cfg)
        return jsonify({
            'id': exp_cfg.get('exp_id', exp_id),
            'name': exp_cfg.get('name', 'Untitled'),
            'status': exp_cfg.get('status', 'unknown'),
            'progress': exp_cfg.get('progress', 0),
            'runner_id': exp_cfg.get('runner_id', ''),
            'runner_type': exp_cfg.get('runner_type', ''),
            'runner_display': exp_cfg.get('runner_display', ''),
            'dataset': exp_cfg.get('dataset', ''),
            'tuning_dataset': tuning_dataset,
            'test_dataset': test_dataset,
            'dataset_split': exp_cfg.get('dataset_split', {}),
            'samples': exp_cfg.get('samples', 0),
            'model': exp_cfg.get('model', ''),
            'prompt_template': exp_cfg.get('prompt_template', {}),
            'created_at': exp_cfg.get('created_at', ''),
            'updated_at': exp_cfg.get('updated_at', ''),
            'history': exp_cfg.get('history', [])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 404


@exp_bp.route('/api/<exp_id>/report-charts')
def api_experiment_report_charts(exp_id):
    """Return chart-friendly metrics payload for experiment report."""
    exp_cfg = MetaLoader.load("exps", exp_id)
    if not exp_cfg:
        return jsonify({"error": f"experiment not found: {exp_id}"}), 404
    try:
        payload = _build_report_chart_payload(exp_id)
        return jsonify(payload)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@exp_bp.route('/api/save', methods=['POST'])
def experiment_save():
    try:
        data = request.get_json(force=True)  # force=True 防止 Content-Type 不对时报错

        if not data:
            return jsonify({"success": False, "error": "No JSON data received"}), 400

        # 必要字段校验
        required = ['runner_type', 'runner_id']
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({"success": False, "error": f"Missing fields: {', '.join(missing)}"}), 400

        runner_id = str(data.get("runner_id") or "").strip()
        split_mode = str(data.get("split_mode") or "").strip().lower()
        split_info = None
        if split_mode == "auto":
            source_dataset = _normalize_dataset_name(data.get("split_source_dataset") or data.get("dataset") or "")
            if not source_dataset:
                return jsonify({"success": False, "error": "split_source_dataset is required for auto split"}), 400
            split_ratio = data.get("split_ratio", 0.8)
            split_seed = data.get("split_seed", 42)
            split_info = _auto_split_dataset(
                runner_id=runner_id,
                source_dataset=source_dataset,
                split_ratio=split_ratio,
                seed=split_seed,
            )
            data["tuning_dataset"] = split_info["tuning_dataset"]
            data["test_dataset"] = split_info["test_dataset"]
            data["dataset_split"] = split_info["dataset_split"]

        tuning_dataset = _normalize_dataset_name(data.get("tuning_dataset") or "")
        test_dataset = _normalize_dataset_name(data.get("test_dataset") or data.get("dataset") or "")
        if not tuning_dataset:
            tuning_dataset = test_dataset
        if not test_dataset:
            test_dataset = tuning_dataset
        if not tuning_dataset or not test_dataset:
            return jsonify({"success": False, "error": "Missing tuning_dataset/test_dataset (or legacy dataset)"}), 400

        data["tuning_dataset"] = tuning_dataset
        data["test_dataset"] = test_dataset
        # Keep legacy key for old consumers; treat dataset as test dataset.
        data["dataset"] = test_dataset
        try:
            _fields, rows = TestLoader.load_by_id_file(runner_id, test_dataset)
            data["samples"] = len(rows or [])
        except Exception:
            data["samples"] = int(data.get("samples") or 0)

        if not 'exp_id' in data or not data['exp_id']:
            data['exp_id'] = str(uuid.uuid4())
            data["name"]= f"{data['runner_id']}_{data['test_dataset']}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            data['status']="pending"  # 后续可以改成 running/completed/failed
            data["progress"]=0
            MetaLoader.dump("exps", data['exp_id'], data)
        else:
            exp_id=data['exp_id']
            exp_cfg = MetaLoader.load("exps", exp_id)
            exp_cfg.update(data)
            MetaLoader.dump("exps", data['exp_id'], exp_cfg)
        # 持久化存储（你自己选方式）


        return jsonify({
            "success": True,
            "exp_id": data["exp_id"],
            "tuning_dataset": tuning_dataset,
            "test_dataset": test_dataset,
            "dataset_split": split_info["dataset_split"] if split_info else data.get("dataset_split"),
            "message": "Experiment config saved successfully"
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


async def _run_with_saver( exp_id, exp_cfg, dataset):
    runner_id=exp_cfg['runner_id']
    runner=RunnerLoader.aload(runner_id)
    #runner= load_graph(runner_id, saver) if exp_cfg['runner_type']=='graph' else get_agent(runner_id,saver)
    fields, data= TestLoader.load_by_id_file(runner_id,dataset)
    for idx, row in enumerate(data):
        input_dict = dict(zip(fields, row))
        config: RunnableConfig = {"configurable": {"thread_id": f'{exp_id}_{idx}'} }
        await runner.ainvoke(input_dict,config=config)


async def run_experiment_background(exp_id, exp_cfg, dataset):
        await _run_with_saver(exp_id, exp_cfg, dataset)

# 启动端点
@exp_bp.route('/api/update', methods=['POST'])
def update_exp():
    data = request.get_json(force=True)  # force=True 防止 Content-Type 不对时报错
    exp_id=data['exp_id']
    exp_cfg = MetaLoader.load("exps",exp_id)

    MetaLoader.update("exps",exp_id,data)
    if data['status']=='completed':
        #perststence state
        exp_cfg = MetaLoader.load("exps", exp_id)
        RunnerLoader.persistence(exp_cfg)
    # 立即启动后台任务
    #asyncio.create_task(run_experiment_background(exp_id, exp_cfg, dataset))

    return jsonify({
        'success': True,
        'exp_id': exp_id,
        'message': 'Experiment started in background',
    })


@exp_bp.route('/api/optimize-loop', methods=['POST'])
def optimize_loop():
    data = request.get_json(force=True) or {}
    exp_id = (data.get("exp_id") or "").strip()
    if not exp_id:
        return jsonify({"success": False, "error": "exp_id is required"}), 400
    candidate_graph_id = (data.get("candidate_graph_id") or "").strip()
    tuning_dataset = _normalize_dataset_name(data.get("tuning_dataset") or "")
    test_dataset = _normalize_dataset_name(data.get("test_dataset") or "")
    try:
        summary = run_optimize_loop_by_exp(
            exp_id,
            candidate_graph_id=candidate_graph_id,
            tuning_dataset=tuning_dataset,
            test_dataset=test_dataset,
        )
        return jsonify({"success": True, "summary": summary})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@exp_bp.route('/api/optimize-loop/start', methods=['POST'])
def optimize_loop_start():
    data = request.get_json(force=True) or {}
    exp_id = (data.get("exp_id") or "").strip()
    if not exp_id:
        return jsonify({"success": False, "error": "exp_id is required"}), 400
    candidate_graph_id = (data.get("candidate_graph_id") or "").strip()
    tuning_dataset = _normalize_dataset_name(data.get("tuning_dataset") or "")
    test_dataset = _normalize_dataset_name(data.get("test_dataset") or "")
    if exp_id:
        try:
            exp_cfg = MetaLoader.load("exps", exp_id) or {}
            if tuning_dataset:
                exp_cfg["tuning_dataset"] = tuning_dataset
            if test_dataset:
                exp_cfg["test_dataset"] = test_dataset
                exp_cfg["dataset"] = test_dataset
            if tuning_dataset or test_dataset:
                MetaLoader.dump("exps", exp_id, exp_cfg)
        except Exception:
            pass
    task_id = f"opt_{uuid.uuid4().hex}"
    task = {
        "task_id": task_id,
        "exp_id": exp_id,
        "status": "running",
        "progress": 0,
        "stage": "queued",
        "message": "Queued",
        "error": "",
        "summary": None,
        "updated_at": time.time(),
    }
    with _optimize_lock:
        _optimize_tasks[task_id] = task

    def _runner():
        def _on_progress(evt: dict):
            with _optimize_lock:
                t = _optimize_tasks.get(task_id)
                if not t:
                    return
                t["progress"] = int(evt.get("progress") or t["progress"])
                t["stage"] = evt.get("stage") or t["stage"]
                t["message"] = evt.get("message") or t["message"]
                if evt.get("flow_steps"):
                    t["flow_steps"] = evt["flow_steps"]
                if evt.get("flow_step"):
                    t["flow_step"] = evt["flow_step"]
                t["updated_at"] = time.time()

        try:
            summary = run_optimize_loop_by_exp_with_progress(
                exp_id,
                candidate_graph_id=candidate_graph_id,
                tuning_dataset=tuning_dataset,
                test_dataset=test_dataset,
                progress_cb=_on_progress,
            )
            with _optimize_lock:
                t = _optimize_tasks.get(task_id)
                if t:
                    t["status"] = "completed"
                    t["progress"] = 100
                    t["stage"] = "done"
                    t["message"] = "Optimize loop completed"
                    t["summary"] = summary
                    t["updated_at"] = time.time()
        except Exception as ex:
            with _optimize_lock:
                t = _optimize_tasks.get(task_id)
                if t:
                    t["status"] = "failed"
                    t["message"] = "Optimize loop failed"
                    t["error"] = str(ex)
                    t["updated_at"] = time.time()

    threading.Thread(target=_runner, daemon=True).start()
    return jsonify({"success": True, "task_id": task_id})


@exp_bp.route('/stream/optimize-loop/<task_id>', methods=['GET'])
def optimize_loop_stream(task_id):
    def generate():
        last_payload = None
        while True:
            with _optimize_lock:
                task = dict(_optimize_tasks.get(task_id) or {})
            if not task:
                payload = {"status": "failed", "error": f"task not found: {task_id}"}
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return
            payload = {
                "task_id": task_id,
                "status": task.get("status"),
                "progress": task.get("progress", 0),
                "stage": task.get("stage", ""),
                "message": task.get("message", ""),
                "error": task.get("error", ""),
                "flow_step": task.get("flow_step", ""),
                "flow_steps": task.get("flow_steps"),
            }
            if task.get("summary") is not None:
                payload["summary"] = task["summary"]
            if task.get("result") is not None:
                payload["result"] = task["result"]

            if payload != last_payload:
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                last_payload = payload

            if task.get("status") in ("completed", "failed"):
                yield "data: [DONE]\n\n"
                return
            time.sleep(0.8)

    return Response(generate(), mimetype='text/event-stream')


@exp_bp.route('/api/<exp_id>/report-file/<path:filename>', methods=['GET'])
def api_experiment_report_file(exp_id, filename):
    """Serve saved markdown report from result/<exp_id>/."""
    safe_name = Path(filename).name
    if safe_name != filename or not safe_name.endswith('.md'):
        return jsonify({"success": False, "error": "invalid report filename"}), 400
    path = _ROOT / "result" / exp_id / safe_name
    if not path.is_file():
        return jsonify({"success": False, "error": "report not found"}), 404
    return Response(path.read_text(encoding='utf-8'), mimetype='text/markdown; charset=utf-8')


@exp_bp.route('/api/<exp_id>/baseline-test-report', methods=['POST'])
def baseline_test_report_api(exp_id):
    try:
        data = generate_baseline_test_report(exp_id)
        return jsonify({"success": True, **data})
    except Exception as ex:
        return jsonify({"success": False, "error": str(ex)}), 400


@exp_bp.route('/api/runner-agents/<runner_id>', methods=['GET'])
def runner_agents_api(runner_id):
    roster = _resolve_runner_agent_roster(runner_id)
    return jsonify({"success": True, "runner_id": runner_id, "agents": roster})


@exp_bp.route('/api/<exp_id>/optimization-preflight', methods=['GET'])
def optimization_preflight_api(exp_id):
    try:
        data = optimization_flow_state(exp_id)
        return jsonify({"success": True, **data})
    except Exception as ex:
        return jsonify({"success": False, "error": str(ex)}), 400


@exp_bp.route('/api/<exp_id>/optimization-step/<step_id>', methods=['POST'])
def optimization_step_api(exp_id, step_id):
    data = request.get_json(force=True) or {}
    tuning_dataset = _normalize_dataset_name(data.get("tuning_dataset") or "")
    test_dataset = _normalize_dataset_name(data.get("test_dataset") or "")
    force = bool(data.get("force"))
    try:
        result = run_optimization_step(
            exp_id,
            step_id,
            tuning_dataset=tuning_dataset,
            test_dataset=test_dataset,
            force=force,
        )
        return jsonify({"success": True, **result})
    except Exception as ex:
        return jsonify({"success": False, "error": str(ex)}), 400


@exp_bp.route('/api/<exp_id>/optimization-step/<step_id>/start', methods=['POST'])
def optimization_step_start_api(exp_id, step_id):
    """Async step runner for long steps (3–7); step 1 uses stream separately."""
    data = request.get_json(force=True) or {}
    tuning_dataset = _normalize_dataset_name(data.get("tuning_dataset") or "")
    test_dataset = _normalize_dataset_name(data.get("test_dataset") or "")
    force = bool(data.get("force"))
    task_id = f"optstep_{uuid.uuid4().hex}"
    task = {
        "task_id": task_id,
        "exp_id": exp_id,
        "step_id": step_id,
        "status": "running",
        "progress": 0,
        "stage": "queued",
        "message": "Queued",
        "error": "",
        "result": None,
        "updated_at": time.time(),
    }
    with _optimize_lock:
        _optimize_tasks[task_id] = task

    def _runner():
        def _on_progress(evt: dict):
            with _optimize_lock:
                t = _optimize_tasks.get(task_id)
                if not t:
                    return
                t["progress"] = int(evt.get("progress") or t["progress"])
                t["stage"] = evt.get("stage") or t["stage"]
                t["message"] = evt.get("message") or t["message"]
                if evt.get("flow_steps"):
                    t["flow_steps"] = evt["flow_steps"]
                t["updated_at"] = time.time()

        try:
            result = run_optimization_step(
                exp_id,
                step_id,
                tuning_dataset=tuning_dataset,
                test_dataset=test_dataset,
                force=force,
                progress_cb=_on_progress,
            )
            with _optimize_lock:
                t = _optimize_tasks.get(task_id)
                if t:
                    t["status"] = "completed"
                    t["progress"] = 100
                    t["stage"] = "done"
                    t["message"] = f"Step {step_id} completed"
                    t["result"] = result
                    if result.get("flow_steps"):
                        t["flow_steps"] = result["flow_steps"]
                    t["updated_at"] = time.time()
        except Exception as ex:
            with _optimize_lock:
                t = _optimize_tasks.get(task_id)
                if t:
                    t["status"] = "failed"
                    t["message"] = f"Step {step_id} failed"
                    t["error"] = str(ex)
                    t["updated_at"] = time.time()

    threading.Thread(target=_runner, daemon=True).start()
    return jsonify({"success": True, "task_id": task_id})


@exp_bp.route('/api/<exp_id>/optimization-run', methods=['POST'])
def optimization_run_api(exp_id):
    data = request.get_json(force=True) or {}
    from_step = str(data.get("from_step") or "baseline_test").strip()
    to_step = str(data.get("to_step") or "final_test_report").strip()
    tuning_dataset = _normalize_dataset_name(data.get("tuning_dataset") or "")
    test_dataset = _normalize_dataset_name(data.get("test_dataset") or "")
    force = bool(data.get("force"))
    task_id = f"optrun_{uuid.uuid4().hex}"
    task = {
        "task_id": task_id,
        "exp_id": exp_id,
        "status": "running",
        "progress": 0,
        "stage": "queued",
        "message": "Queued",
        "error": "",
        "result": None,
        "updated_at": time.time(),
    }
    with _optimize_lock:
        _optimize_tasks[task_id] = task

    def _runner():
        def _on_progress(evt: dict):
            with _optimize_lock:
                t = _optimize_tasks.get(task_id)
                if not t:
                    return
                t["progress"] = int(evt.get("progress") or t["progress"])
                t["stage"] = evt.get("stage") or t["stage"]
                t["message"] = evt.get("message") or t["message"]
                if evt.get("flow_steps"):
                    t["flow_steps"] = evt["flow_steps"]
                t["updated_at"] = time.time()

        try:
            result = run_optimization_pipeline(
                exp_id,
                from_step=from_step,
                to_step=to_step,
                tuning_dataset=tuning_dataset,
                test_dataset=test_dataset,
                force=force,
                progress_cb=_on_progress,
            )
            with _optimize_lock:
                t = _optimize_tasks.get(task_id)
                if t:
                    t["status"] = "completed" if not result.get("needs_stream") else "awaiting_stream"
                    t["progress"] = 0 if result.get("needs_stream") else 100
                    t["stage"] = "awaiting_stream" if result.get("needs_stream") else "done"
                    t["message"] = "Run baseline test via stream" if result.get("needs_stream") else "Pipeline completed"
                    t["result"] = result
                    if result.get("flow_steps"):
                        t["flow_steps"] = result["flow_steps"]
                    t["updated_at"] = time.time()
        except Exception as ex:
            with _optimize_lock:
                t = _optimize_tasks.get(task_id)
                if t:
                    t["status"] = "failed"
                    t["message"] = "Pipeline failed"
                    t["error"] = str(ex)
                    t["updated_at"] = time.time()

    threading.Thread(target=_runner, daemon=True).start()
    return jsonify({"success": True, "task_id": task_id})

