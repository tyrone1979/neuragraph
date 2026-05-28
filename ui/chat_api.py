import json
import re
import textwrap
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple
from datetime import datetime

import autogen
from flask import Blueprint, jsonify, request

from service.api.terminal import TerminalRunner
from service.meta.loader import MetaLoader
from service.entity.test import TestLoader
from service.experiment_optimize import run_optimize_loop_by_exp
from chat import LLMCommandParser


chat_bp = Blueprint("chat", __name__, url_prefix="/chat")
META_DIR = Path(__file__).resolve().parent.parent / "meta"
DEFAULT_LLM_ID = "deepseek"


def _load_llm_config(llm_id: str | None) -> Tuple[str, Dict[str, Any]]:
    cm = autogen.ConfigManager(META_DIR)
    llms = cm.load_all("llms")
    if not llms:
        raise ValueError("No LLM config found in meta/llms")
    chosen = llm_id or DEFAULT_LLM_ID
    if chosen not in llms:
        chosen = next(iter(llms.keys()))
    return chosen, llms[chosen]


def _list_meta(subdir: str, title: str) -> str:
    cfgs = MetaLoader.loads(subdir) or []
    if not cfgs:
        return f"{title}\n- (empty)"
    lines = [title]
    for cfg in sorted(cfgs, key=lambda x: x.get("id", "")):
        cid = cfg.get("id", "")
        name = cfg.get("name", "")
        ctype = cfg.get("type", "")
        extra = f" [{ctype}]" if ctype else ""
        lines.append(f"- `{cid}`{extra} {name}".rstrip())
    return "\n".join(lines)


def _show_meta(subdir: str, cid: str, label: str) -> str:
    cfg = MetaLoader.load(subdir, cid)
    if not cfg:
        return f"{label} `{cid}` not found."
    pretty = json.dumps(cfg, ensure_ascii=False, indent=2)
    return f"{label} `{cid}`:\n```json\n{pretty}\n```"


def _try_parse_json_tail(text: str) -> Dict[str, Any]:
    # Accept inline JSON tail: /run workflow xxx {"text":"..."}
    m = re.search(r"(\{.*\})\s*$", text.strip())
    if not m:
        return {}
    try:
        val = json.loads(m.group(1))
        return val if isinstance(val, dict) else {}
    except Exception:
        return {}


def _run_workflow_or_agent(kind: str, target_id: str, inputs: Dict[str, Any]) -> str:
    runner = TerminalRunner(verbose=False)
    if not inputs:
        return (
            f"`{kind}` `{target_id}` requires input JSON.\n"
            f"Example: `/run {kind} {target_id} {{\"text\":\"...\"}}`"
        )
    result = runner.run_graph(target_id, inputs) if kind == "workflow" else runner.run_agent(target_id, inputs)
    if result.get("status") != "success":
        return f"Run failed: {result.get('message', 'unknown error')}"
    payload = json.dumps(result.get("result", {}), ensure_ascii=False, indent=2)
    return f"Run succeeded for `{kind}` `{target_id}`:\n```json\n{payload}\n```"


def _run_experiment(exp_id: str) -> str:
    runner = TerminalRunner(verbose=False)
    result = runner.run_experiment(exp_id)
    summary = {
        "status": result.get("status"),
        "exp_id": result.get("exp_id"),
        "total": result.get("total"),
        "success": result.get("success"),
        "failed": result.get("failed"),
        "elapsed": round(float(result.get("elapsed", 0.0)), 2),
        "message": result.get("message"),
    }
    return f"Experiment execution result:\n```json\n{json.dumps(summary, ensure_ascii=False, indent=2)}\n```"


def _generate_workflow(requirement: str, llm_id: str) -> str:
    chosen, llm_cfg = _load_llm_config(llm_id)
    engine = autogen.AutoGen(llm_cfg, verbose=False)
    engine.cm = autogen.ConfigManager(META_DIR)
    plan = engine.analyze(requirement)
    generated = engine.generate(plan)
    errors = engine.validate(plan)
    if errors:
        return "Generation finished with validation errors:\n```json\n" + json.dumps(errors, ensure_ascii=False, indent=2) + "\n```"
    summary = {
        "status": "success",
        "llm": chosen,
        "graph_id": plan.get("graph_plan", {}).get("id", ""),
        "generated": [str(p) for p in generated],
    }
    return "Workflow generated successfully:\n```json\n" + json.dumps(summary, ensure_ascii=False, indent=2) + "\n```"


def _generate_agent(requirement: str, llm_id: str) -> str:
    chosen, llm_cfg = _load_llm_config(llm_id)
    engine = autogen.AutoGen(llm_cfg, verbose=False)
    engine.cm = autogen.ConfigManager(META_DIR)
    result = engine.generate_single_agent(requirement, chosen)
    return "Agent generation result:\n```json\n" + json.dumps(result, ensure_ascii=False, indent=2) + "\n```"


def _update_meta(subdir: str, cid: str, changes: str, llm_id: str) -> str:
    existing = MetaLoader.load(subdir, cid)
    if not existing:
        return f"`{cid}` not found in `{subdir}`."
    chosen, llm_cfg = _load_llm_config(llm_id)
    client = autogen.LLMClient(llm_cfg)
    system = textwrap.dedent(
        """\
        You are updating an existing NeuraGraph configuration.
        Return the complete updated config as valid JSON only.
        Preserve fields unless explicitly changed by user request.
        """
    )
    user_prompt = f"Current config:\n{json.dumps(existing, ensure_ascii=False, indent=2)}\n\nRequested changes:\n{changes}"
    response = client.chat(system, user_prompt)
    updated = None
    try:
        updated = json.loads(response.strip())
    except json.JSONDecodeError:
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response, re.DOTALL)
        if m:
            updated = json.loads(m.group(1).strip())
    if not isinstance(updated, dict):
        return "LLM returned invalid JSON for update."
    MetaLoader.dump(subdir, cid, updated)
    return f"Updated `{cid}` in `{subdir}` using `{chosen}`."


def _delete_meta(subdir: str, cid: str) -> str:
    if not MetaLoader.exists(subdir, cid):
        return f"`{cid}` not found in `{subdir}`."
    ok = MetaLoader.delete(subdir, cid)
    return f"Deleted `{cid}` from `{subdir}`." if ok else f"Failed to delete `{cid}`."


def _create_testset(
    runner_id: str,
    filename: str,
    source_file: str = "",
    count: int = 5,
) -> str:
    runner_id = (runner_id or "").strip()
    filename = (filename or "").strip()
    source_file = (source_file or "").strip()
    if not runner_id or not filename:
        return "Missing runner_id or filename."
    if not filename.lower().endswith(".csv"):
        filename = f"{filename}.csv"

    if source_file:
        try:
            fields, rows = TestLoader.load_by_id_file(runner_id, source_file)
        except Exception as e:
            return f"Failed to load source dataset `{source_file}`: {e}"
        if not rows:
            return f"Source dataset `{source_file}` has no rows."
        rows = [dict(r) for r in rows]
        picked = [dict(rows[i % len(rows)]) for i in range(max(1, int(count)))]
        TestLoader.save_csv_rows(runner_id, filename, fields, picked)
        return (
            f"Created testset `{filename}` for runner `{runner_id}` "
            f"from `{source_file}` with {len(picked)} rows."
        )

    # No source_file: create minimal template row
    fields = ["text", "entities", "gold_relations"]
    rows = [
        {
            "text": "Aspirin reduces fever in patients with influenza.",
            "entities": '[{"text":"Aspirin","id":"D001241","label":"Chemical"},{"text":"influenza","id":"D007251","label":"Disease"}]',
            "gold_relations": "D001241 | D007251",
        }
    ]
    TestLoader.save_csv_rows(runner_id, filename, fields, rows)
    return f"Created template testset `{filename}` for runner `{runner_id}`."


def _create_experiment(runner_id: str, dataset: str, runner_type: str = "graph") -> str:
    runner_id = (runner_id or "").strip()
    dataset = (dataset or "").strip()
    runner_type = (runner_type or "graph").strip()
    if not runner_id or not dataset:
        return "Missing runner_id or dataset."
    if not dataset.lower().endswith(".csv") and not dataset.lower().endswith(".txt"):
        dataset = f"{dataset}.csv"
    try:
        _fields, rows = TestLoader.load_by_id_file(runner_id, dataset)
        sample_count = len(rows or [])
    except Exception:
        sample_count = 0

    exp_id = str(uuid.uuid4())
    data = {
        "dataset": dataset,
        "runner_type": runner_type,
        "runner_id": runner_id,
        "runner_display": runner_id,
        "samples": sample_count,
        "exp_id": exp_id,
        "name": f"{runner_id}_{dataset}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "status": "pending",
        "progress": 0,
    }
    MetaLoader.dump("exps", exp_id, data)
    return f"Created experiment `{exp_id}` for runner `{runner_id}` with dataset `{dataset}`."


def _copy_workflow(source_id: str, target_id: str) -> str:
    source_id = (source_id or "").strip()
    target_id = (target_id or "").strip()
    if not source_id or not target_id:
        return "Missing source workflow id or target workflow id."
    source = MetaLoader.load("graphs", source_id)
    if not source:
        return f"Workflow `{source_id}` not found."
    if MetaLoader.exists("graphs", target_id):
        return f"Workflow `{target_id}` already exists."
    copied = dict(source)
    copied["name"] = f"{source.get('name', source_id)} (copy)"
    MetaLoader.dump("graphs", target_id, copied)
    return f"Copied workflow `{source_id}` -> `{target_id}`."


def _start_optimize_loop(exp_id: str, max_updates: int = 1) -> str:
    exp_id = (exp_id or "").strip()
    if not exp_id:
        return "Missing exp_id."
    try:
        summary = run_optimize_loop_by_exp(exp_id, max_agent_updates=max_updates)
    except Exception as e:
        return f"Optimize loop failed: {e}"
    brief = {
        "baseline_exp_id": summary.get("baseline_exp_id"),
        "candidate_exp_id": summary.get("candidate_exp_id"),
        "metrics_delta": summary.get("metrics_delta", {}),
        "keep_modified_agents": summary.get("keep_modified_agents"),
        "restored_agents": summary.get("restored_agents", []),
    }
    return "Optimize loop finished:\n```json\n" + json.dumps(brief, ensure_ascii=False, indent=2) + "\n```"


def _to_int(val: Any, default: int) -> int:
    try:
        return int(val)
    except Exception:
        return default


def _execute_slash(cmd: str, llm_id: str) -> str:
    raw = cmd.strip()
    parts = raw.split()
    if not parts:
        return "Empty command."
    c0 = parts[0].lower()

    if c0 in ("/help", "/h"):
        return (
            "Commands:\n"
            "- `/list workflows|agents|tools|llms|experiments`\n"
            "- `/show workflow|agent|tool|llm|experiment <id>`\n"
            "- `/run workflow|agent <id> {json_inputs}`\n"
            "- `/run experiment <exp_id>`\n"
            "- `/create testset <runner_id> <filename> [source_file] [count]`\n"
            "- `/create experiment <runner_id> <dataset> [runner_type]`\n"
            "- `/copy workflow <source_id> <target_id>`\n"
            "- `/optimize <exp_id> [max_updates]`\n"
            "- `/delete workflow|agent|tool|llm|experiment <id>`"
        )

    if c0 == "/list":
        sub = parts[1].lower() if len(parts) > 1 else "workflows"
        if sub in ("workflow", "workflows", "graph", "graphs"):
            return _list_meta("graphs", "Workflows")
        if sub in ("agent", "agents"):
            return _list_meta("agents", "Agents")
        if sub in ("tool", "tools"):
            return _list_meta("tools", "Tools")
        if sub in ("llm", "llms"):
            return _list_meta("llms", "LLMs")
        if sub in ("experiment", "experiments", "exp", "exps"):
            return _list_meta("exps", "Experiments")
        return f"Unsupported list type: `{sub}`"

    if c0 == "/show" and len(parts) >= 3:
        sub = parts[1].lower()
        cid = parts[2]
        if sub in ("workflow", "graph"):
            return _show_meta("graphs", cid, "Workflow")
        if sub == "agent":
            return _show_meta("agents", cid, "Agent")
        if sub == "tool":
            return _show_meta("tools", cid, "Tool")
        if sub == "llm":
            return _show_meta("llms", cid, "LLM")
        if sub in ("experiment", "exp"):
            return _show_meta("exps", cid, "Experiment")

    if c0 == "/run" and len(parts) >= 3:
        sub = parts[1].lower()
        cid = parts[2]
        inputs = _try_parse_json_tail(raw)
        if sub in ("workflow", "graph"):
            return _run_workflow_or_agent("workflow", cid, inputs)
        if sub == "agent":
            return _run_workflow_or_agent("agent", cid, inputs)
        if sub in ("experiment", "exp"):
            return _run_experiment(cid)

    if c0 == "/delete" and len(parts) >= 3:
        sub = parts[1].lower()
        cid = parts[2]
        if sub in ("workflow", "graph"):
            return _delete_meta("graphs", cid)
        if sub == "agent":
            return _delete_meta("agents", cid)
        if sub == "tool":
            return _delete_meta("tools", cid)
        if sub == "llm":
            return _delete_meta("llms", cid)
        if sub in ("experiment", "exp"):
            return _delete_meta("exps", cid)

    if c0 == "/create" and len(parts) >= 2:
        sub = parts[1].lower()
        if sub == "testset":
            if len(parts) < 4:
                return "Usage: /create testset <runner_id> <filename> [source_file] [count]"
            runner_id = parts[2]
            filename = parts[3]
            source_file = parts[4] if len(parts) >= 5 else ""
            try:
                count = int(parts[5]) if len(parts) >= 6 else 5
            except ValueError:
                count = 5
            return _create_testset(runner_id, filename, source_file, count)
        if sub in ("experiment", "exp"):
            if len(parts) < 4:
                return "Usage: /create experiment <runner_id> <dataset> [runner_type]"
            runner_id = parts[2]
            dataset = parts[3]
            runner_type = parts[4] if len(parts) >= 5 else "graph"
            return _create_experiment(runner_id, dataset, runner_type)

    if c0 == "/copy" and len(parts) >= 4:
        sub = parts[1].lower()
        if sub in ("workflow", "graph"):
            return _copy_workflow(parts[2], parts[3])

    if c0 == "/optimize" and len(parts) >= 2:
        exp_id = parts[1]
        try:
            max_updates = int(parts[2]) if len(parts) >= 3 else 1
        except ValueError:
            max_updates = 1
        return _start_optimize_loop(exp_id, max_updates=max_updates)

    return "Unsupported command. Type `/help`."


def _dispatch_intent(intent: Dict[str, Any], llm_id: str) -> str:
    action = intent.get("action", "chat")
    params = intent.get("parameters", {}) or {}
    response = intent.get("response", "") or ""

    if action == "chat":
        return response or "I can help with workflows, agents, tools, and experiments."
    if action == "command":
        cmd = params.get("cmd", "")
        if cmd:
            return _execute_slash(cmd, llm_id)
        return response or "Command is empty."

    if action == "list_agents":
        return _list_meta("agents", "Agents")
    if action in ("list_workflows", "list_graphs"):
        return _list_meta("graphs", "Workflows")
    if action == "list_tools":
        return _list_meta("tools", "Tools")
    if action == "list_llms":
        return _list_meta("llms", "LLMs")
    if action == "list_experiments":
        return _list_meta("exps", "Experiments")

    if action == "show_agent":
        return _show_meta("agents", params.get("id", ""), "Agent")
    if action in ("show_workflow", "show_graph"):
        return _show_meta("graphs", params.get("id", ""), "Workflow")
    if action == "show_tool":
        return _show_meta("tools", params.get("id", ""), "Tool")
    if action == "show_llm":
        return _show_meta("llms", params.get("id", ""), "LLM")
    if action == "show_experiment":
        return _show_meta("exps", params.get("id", ""), "Experiment")

    if action == "run_agent":
        return _run_workflow_or_agent("agent", params.get("id", ""), params.get("inputs") or {})
    if action in ("run_workflow", "run_graph"):
        return _run_workflow_or_agent("workflow", params.get("id", ""), params.get("inputs") or {})
    if action == "run_experiment":
        return _run_experiment(params.get("id", ""))

    if action == "generate_agent":
        return _generate_agent(params.get("requirement", ""), llm_id)
    if action in ("generate_workflow", "generate_graph"):
        return _generate_workflow(params.get("requirement", ""), llm_id)

    if action == "update_agent":
        return _update_meta("agents", params.get("id", ""), params.get("changes", ""), llm_id)
    if action in ("update_workflow", "update_graph"):
        return _update_meta("graphs", params.get("id", ""), params.get("changes", ""), llm_id)
    if action == "update_tool":
        return _update_meta("tools", params.get("id", ""), params.get("changes", ""), llm_id)
    if action == "update_llm":
        return _update_meta("llms", params.get("id", ""), params.get("changes", ""), llm_id)

    if action == "delete_agent":
        return _delete_meta("agents", params.get("id", ""))
    if action in ("delete_workflow", "delete_graph"):
        return _delete_meta("graphs", params.get("id", ""))
    if action == "delete_tool":
        return _delete_meta("tools", params.get("id", ""))
    if action == "delete_llm":
        return _delete_meta("llms", params.get("id", ""))
    if action == "delete_experiment":
        return _delete_meta("exps", params.get("id", ""))

    if action == "create_testset":
        return _create_testset(
            params.get("runner_id", ""),
            params.get("filename", ""),
            params.get("source_file", ""),
            _to_int(params.get("count", 5), 5),
        )
    if action == "create_experiment":
        return _create_experiment(
            params.get("runner_id", ""),
            params.get("dataset", ""),
            params.get("runner_type", "graph"),
        )
    if action in ("copy_workflow", "copy_graph"):
        return _copy_workflow(params.get("source_id", ""), params.get("target_id", ""))
    if action in ("start_optimize_loop", "optimize_loop"):
        return _start_optimize_loop(
            params.get("id", "") or params.get("exp_id", ""),
            _to_int(params.get("max_updates", 1), 1),
        )

    return response or f"Unknown action: {action}"


@chat_bp.route("/api/message", methods=["POST"])
def chat_message():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    history = payload.get("history") or []
    llm_id = payload.get("llm_id") or DEFAULT_LLM_ID

    if not message:
        return jsonify({"ok": False, "error": "message is required"}), 400

    try:
        chosen_llm, llm_cfg = _load_llm_config(llm_id)
        if message.startswith("/"):
            reply = _execute_slash(message, chosen_llm)
            return jsonify({"ok": True, "reply": reply, "llm_id": chosen_llm, "action": "command"})

        parser = LLMCommandParser(llm_cfg, META_DIR)
        safe_history = [
            {"role": str(item.get("role", "user")), "content": str(item.get("content", ""))}
            for item in history
            if isinstance(item, dict)
        ]
        intent = parser.parse(message, safe_history)
        reply = _dispatch_intent(intent, chosen_llm)
        return jsonify(
            {
                "ok": True,
                "reply": reply,
                "llm_id": chosen_llm,
                "action": intent.get("action", "chat"),
                "intent": intent,
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
