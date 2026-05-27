"""Flask sidecar app factory (one process per sandbox id)."""
from __future__ import annotations

import json
import os

from flask import Flask, jsonify, request

from sandbox._common.runtime import load_all_plugins, run_pgm, run_tool

_loaded: dict[str, dict] = {}


def _sandbox_id() -> str:
    sid = os.environ.get("SANDBOX_ID", "").strip()
    if not sid:
        raise RuntimeError("SANDBOX_ID environment variable is required")
    return sid


def _ensure_loaded(sandbox_id: str) -> dict:
    if sandbox_id not in _loaded:
        print(f"[sandbox:{sandbox_id}] Loading plugins...")
        _loaded[sandbox_id] = load_all_plugins(sandbox_id)
        keys = sorted(k for k in _loaded[sandbox_id] if k != "exec_globals")
        print(f"[sandbox:{sandbox_id}] Ready keys: {keys}")
    return _loaded[sandbox_id]


def create_app(sandbox_id: str | None = None) -> Flask:
    sid = sandbox_id or _sandbox_id()
    app = Flask(__name__)

    @app.route("/health", methods=["GET"])
    def health():
        loaded = _ensure_loaded(sid)
        return jsonify(
            ok=True,
            sandbox_id=sid,
            flair_loaded=loaded.get("tag") is not None,
            keys=sorted(k for k in loaded.keys() if k != "exec_globals"),
        )

    @app.route("/pgm/run", methods=["POST"])
    def pgm_run():
        data = request.get_json(force=True, silent=True) or {}
        code = data.get("code") or ""
        state = data.get("state") or {}
        if not code:
            return jsonify(success=False, error="missing code"), 400
        loaded = _ensure_loaded(sid)
        result, err = run_pgm(code, state, loaded)
        if err:
            return jsonify(success=False, error=err, state=state), 200
        return jsonify(success=True, result=_jsonable(result), error=None)

    @app.route("/tool/run", methods=["POST"])
    def tool_run():
        data = request.get_json(force=True, silent=True) or {}
        code = data.get("code") or ""
        kwargs = data.get("kwargs") or {}
        if not code:
            return jsonify(success=False, error="missing code"), 400
        loaded = _ensure_loaded(sid)
        result, err = run_tool(code, kwargs, loaded)
        if err:
            return jsonify(success=False, error=err), 200
        return jsonify(success=True, result=_jsonable(result), error=None)

    return app


def _jsonable(obj):
    try:
        json.dumps(obj, ensure_ascii=False)
        return obj
    except (TypeError, ValueError):
        return str(obj)


def main(sandbox_id: str | None = None):
    sid = sandbox_id or _sandbox_id()
    port = int(os.environ.get("PLUGIN_SERVER_PORT", "5002"))
    app = create_app(sid)
    _ensure_loaded(sid)
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True, use_reloader=False)
