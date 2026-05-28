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
from service.chat import commands as shared_cmd
from chat import LLMCommandParser


chat_bp = Blueprint("chat", __name__, url_prefix="/chat")
META_DIR = Path(__file__).resolve().parent.parent / "meta"
DEFAULT_LLM_ID = "deepseek"
_CHAT_SESSIONS: Dict[str, Dict[str, Any]] = {}


def _get_chat_session(payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    sid = str(payload.get("session_id") or "").strip() or uuid.uuid4().hex
    session = _CHAT_SESSIONS.setdefault(sid, {"pins": {}, "last_preview": {}})
    if "pins" not in session:
        session["pins"] = {}
    if "last_preview" not in session:
        session["last_preview"] = {}
    return sid, session


def _md_card(title: str, items: List[Tuple[str, Any]], tips: List[str] | None = None) -> str:
    lines = [f"### {title}"]
    for k, v in items:
        lines.append(f"- **{k}**: {v}")
    if tips:
        lines.append("")
        lines.append("**Next**")
        for t in tips:
            lines.append(f"- {t}")
    return "\n".join(lines)


def _render_pins(session: Dict[str, Any]) -> str:
    pins = (session or {}).get("pins") or {}
    if not pins:
        return _md_card("Pinned Context", [("status", "empty")], ["Use `/pin graph <id>` or `/pin exp <id>`"])
    return _md_card(
        "Pinned Context",
        [(k, f"`{v}`") for k, v in pins.items()],
        ["Use `/pin clear` to clear all pins."],
    )


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
    exp_link = f"/exp/{summary.get('exp_id')}" if summary.get("exp_id") else "/exp"
    return _md_card(
        "Experiment Run Result",
        [
            ("exp_id", f"`{summary.get('exp_id', '')}`"),
            ("status", summary.get("status", "")),
            ("success", summary.get("success", 0)),
            ("failed", summary.get("failed", 0)),
            ("elapsed_s", summary.get("elapsed", 0.0)),
        ],
        [f"Open detail: [{summary.get('exp_id', 'experiment')}]({exp_link})"],
    )


def _generate_workflow(requirement: str, llm_id: str) -> str:
    reused = shared_cmd.find_suitable_workflow(requirement)
    if reused:
        gid = str(reused.get("graph_id") or "")
        return shared_cmd.md_card(
            "Workflow Reused",
            [
                ("graph_id", f"`{gid}`"),
                ("name", reused.get("name", "")),
                ("score", reused.get("score", 0)),
            ],
            [f"Use directly: `/run workflow {gid} {{\"text\":\"...\"}}`", f"Open details: `/show workflow {gid}`"],
        )
    chosen, llm_cfg = _load_llm_config(llm_id)
    engine = autogen.AutoGen(llm_cfg, verbose=False)
    engine.cm = autogen.ConfigManager(META_DIR)
    candidate_agents = shared_cmd.find_suitable_agents(requirement, limit=6)
    req = requirement
    if candidate_agents:
        ids = [str(x.get("id") or "").strip() for x in candidate_agents if str(x.get("id") or "").strip()]
        if ids:
            req += "\n\nReuse existing agents when applicable: " + ", ".join(ids)
    plan = engine.analyze(req)
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
    return _md_card(
        "Experiment Created",
        [
            ("exp_id", f"`{exp_id}`"),
            ("runner_id", f"`{runner_id}`"),
            ("dataset", f"`{dataset}`"),
            ("samples", sample_count),
        ],
        [
            f"Open detail: [{exp_id}](/exp/{exp_id})",
            f"Run now: `/run experiment {exp_id}`",
        ],
    )


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
    return _md_card(
        "Workflow Copied",
        [("source", f"`{source_id}`"), ("target", f"`{target_id}`")],
        [f"View copied workflow: `/show workflow {target_id}`"],
    )


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


def _preview_slash(cmd: str, session: Dict[str, Any]) -> str:
    raw = (cmd or "").strip()
    parts = raw.split()
    if not parts:
        return "Empty command."
    pins = (session or {}).setdefault("pins", {})
    c0 = parts[0].lower()
    action = "read"
    if c0 in ("/run", "/create", "/copy", "/optimize", "/delete"):
        action = "write"
    resolved: List[Tuple[str, Any]] = [
        ("command", f"`{raw}`"),
        ("mode", "`dry-run preview`"),
        ("risk", "`high`" if action == "write" else "`low`"),
    ]
    if c0 == "/create" and len(parts) >= 2 and parts[1].lower() in ("experiment", "exp"):
        runner = parts[2] if len(parts) >= 3 else (pins.get("graph") or pins.get("runner_id") or "")
        dataset = parts[3] if len(parts) >= 4 else (pins.get("dataset") or "")
        resolved.append(("resolved_runner", f"`{runner or '(missing)'}`"))
        resolved.append(("resolved_dataset", f"`{dataset or '(missing)'}`"))
    if c0 in ("/run", "/show") and len(parts) >= 3 and parts[1].lower() in ("experiment", "exp"):
        exp_id = parts[2] if len(parts) >= 3 else (pins.get("exp") or "")
        resolved.append(("resolved_exp", f"`{exp_id or '(missing)'}`"))
    if pins:
        resolved.extend((f"pin.{k}", f"`{v}`") for k, v in pins.items())
    return _md_card("Execution Preview", resolved, ["Run the command directly to execute."])


def _execute_slash(cmd: str, llm_id: str, session: Dict[str, Any] | None = None) -> str:
    reply = shared_cmd.execute_slash_command(cmd, session=session, llm_id=llm_id)
    return reply if isinstance(reply, str) else "Unsupported command. Type `/help`."


def _dispatch_intent(intent: Dict[str, Any], llm_id: str, session: Dict[str, Any] | None = None) -> str:
    action = intent.get("action", "chat")
    params = intent.get("parameters", {}) or {}
    response = intent.get("response", "") or ""

    if action == "chat":
        return response or "I can help with workflows, agents, tools, and experiments."
    if action == "command":
        cmd = params.get("cmd", "")
        if cmd:
            return _execute_slash(cmd, llm_id, session=session)
        return response or "Command is empty."

    if action == "list_agents":
        return shared_cmd.list_meta("agents", "Agents")
    if action in ("list_workflows", "list_graphs"):
        return shared_cmd.list_meta("graphs", "Workflows")
    if action == "list_tools":
        return shared_cmd.list_meta("tools", "Tools")
    if action == "list_datasets":
        return shared_cmd.list_datasets()
    if action == "list_llms":
        return shared_cmd.list_meta("llms", "LLMs")
    if action == "list_experiments":
        return shared_cmd.list_meta("exps", "Experiments")

    if action == "show_agent":
        return shared_cmd.show_meta("agents", params.get("id", ""), "Agent")
    if action in ("show_workflow", "show_graph"):
        return shared_cmd.show_meta("graphs", params.get("id", ""), "Workflow")
    if action == "show_tool":
        return shared_cmd.show_meta("tools", params.get("id", ""), "Tool")
    if action == "show_dataset":
        return shared_cmd.show_dataset(params.get("id", ""))
    if action == "show_llm":
        return shared_cmd.show_meta("llms", params.get("id", ""), "LLM")
    if action == "show_experiment":
        return shared_cmd.show_meta("exps", params.get("id", ""), "Experiment")

    if action == "run_agent":
        return shared_cmd.run_workflow_or_agent("agent", params.get("id", ""), params.get("inputs") or {})
    if action in ("run_workflow", "run_graph"):
        return shared_cmd.run_workflow_or_agent("workflow", params.get("id", ""), params.get("inputs") or {})
    if action == "run_experiment":
        return shared_cmd.run_experiment(params.get("id", ""))

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
        return shared_cmd.delete_meta("agents", params.get("id", ""))
    if action in ("delete_workflow", "delete_graph"):
        return shared_cmd.delete_meta("graphs", params.get("id", ""))
    if action == "delete_tool":
        return shared_cmd.delete_meta("tools", params.get("id", ""))
    if action == "delete_llm":
        return shared_cmd.delete_meta("llms", params.get("id", ""))
    if action == "delete_experiment":
        return shared_cmd.delete_meta("exps", params.get("id", ""))

    if action == "create_testset":
        return shared_cmd.create_testset(
            params.get("runner_id", ""),
            params.get("filename", ""),
            params.get("source_file", ""),
            _to_int(params.get("count", 5), 5),
        )
    if action == "create_experiment":
        return shared_cmd.create_experiment(
            params.get("runner_id", ""),
            params.get("dataset", ""),
            params.get("runner_type", "graph"),
        )
    if action in ("copy_workflow", "copy_graph"):
        return shared_cmd.copy_workflow(params.get("source_id", ""), params.get("target_id", ""))
    if action in ("start_optimize_loop", "optimize_loop"):
        return shared_cmd.start_optimize_loop(
            params.get("id", "") or params.get("exp_id", ""),
            _to_int(params.get("max_updates", 1), 1),
        )
    if action == "run_orchestration":
        return shared_cmd.run_orchestration(
            params.get("goal", ""),
            llm_id=llm_id,
            session=session or {"pins": {}},
        )

    return response or f"Unknown action: {action}"


@chat_bp.route("/api/message", methods=["POST"])
def chat_message():
    payload = request.get_json(silent=True) or {}
    session_id, session = _get_chat_session(payload)
    message = (payload.get("message") or "").strip()
    history = payload.get("history") or []
    llm_id = payload.get("llm_id") or DEFAULT_LLM_ID

    if not message:
        return jsonify({"ok": False, "error": "message is required"}), 400

    try:
        chosen_llm, llm_cfg = _load_llm_config(llm_id)
        if message.startswith("/"):
            reply = _execute_slash(message, chosen_llm, session=session)
            return jsonify(
                {
                    "ok": True,
                    "reply": reply,
                    "llm_id": chosen_llm,
                    "action": "command",
                    "session_id": session_id,
                    "pins": session.get("pins", {}),
                }
            )

        parser = LLMCommandParser(llm_cfg, META_DIR)
        safe_history = [
            {"role": str(item.get("role", "user")), "content": str(item.get("content", ""))}
            for item in history
            if isinstance(item, dict)
        ]
        intent = parser.parse(message, safe_history)
        reply = _dispatch_intent(intent, chosen_llm, session=session)
        return jsonify(
            {
                "ok": True,
                "reply": reply,
                "llm_id": chosen_llm,
                "action": intent.get("action", "chat"),
                "intent": intent,
                "session_id": session_id,
                "pins": session.get("pins", {}),
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@chat_bp.route("/api/command-catalog", methods=["GET"])
def chat_command_catalog():
    return jsonify({"ok": True, "items": shared_cmd.command_catalog()})
