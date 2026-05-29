"""HTTP clients for plugin sidecars (multi-sandbox via manifest)."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from plugin.plugin_config import sandbox_enabled, url_for_sandbox
from plugin.sandbox_manifest import get_sandbox, needs_sandbox, resolve_sandbox

logger = logging.getLogger(__name__)

_availability: dict[str, bool | None] = {}


def is_available(sandbox_id: str, *, force_check: bool = False) -> bool:
    if not sandbox_enabled():
        return False
    if not force_check and sandbox_id in _availability and _availability[sandbox_id] is not None:
        return bool(_availability[sandbox_id])
    url = f"{url_for_sandbox(sandbox_id)}/health"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            ok = bool(data.get("ok")) and data.get("sandbox_id", sandbox_id) == sandbox_id
    except Exception as ex:
        logger.debug("Sandbox %s not reachable: %s", sandbox_id, ex)
        ok = False
    _availability[sandbox_id] = ok
    return ok


def _post(sandbox_id: str, path: str, payload: dict[str, Any], timeout: int = 300) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    base = url_for_sandbox(sandbox_id)
    req = urllib.request.Request(
        f"{base}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as ex:
        reason = getattr(ex, "reason", ex)
        raise RuntimeError(f"Sandbox connection failed at {base}{path}: {reason}") from ex


def run_pgm(code: str, state: dict[str, Any], sandbox_id: str) -> Any:
    spec = get_sandbox(sandbox_id)
    if not spec:
        raise ValueError(f"Unknown sandbox: {sandbox_id}")
    if not is_available(sandbox_id):
        raise RuntimeError(
            f"Sandbox '{sandbox_id}' is not running at {url_for_sandbox(sandbox_id)}. "
            f"Run: .\\sandbox\\setup_venv.ps1 -Name {sandbox_id} then .\\start.ps1"
        )
    data = _post(sandbox_id, "/pgm/run", {"code": code, "state": state})
    if not data.get("success"):
        err = data.get("error") or "sandbox PGM failed"
        state = dict(state)
        state["error"] = err
        return state
    return data.get("result", state)


def run_tool(code: str, sandbox_id: str, **kwargs: Any) -> Any:
    if not is_available(sandbox_id):
        raise RuntimeError(
            f"Sandbox '{sandbox_id}' is not running at {url_for_sandbox(sandbox_id)}."
        )
    data = _post(sandbox_id, "/tool/run", {"code": code, "kwargs": kwargs})
    if not data.get("success"):
        raise RuntimeError(data.get("error") or "sandbox tool failed")
    return data.get("result")


def run_pgm_resolved(
    code: str,
    state: dict[str, Any],
    *,
    meta: dict | None = None,
    engine: str | None = None,
) -> Any:
    sid = resolve_sandbox(code, meta=meta, engine=engine)
    if not sid:
        raise RuntimeError("No sandbox resolved for PGM code")
    return run_pgm(code, state, sid)


def run_tool_resolved(
    code: str,
    *,
    meta: dict | None = None,
    engine: str | None = None,
    **kwargs: Any,
) -> Any:
    sid = resolve_sandbox(code, meta=meta, engine=engine)
    if not sid:
        raise RuntimeError("No sandbox resolved for tool code")
    return run_tool(code, sid, **kwargs)


# Backward-compatible helpers
def code_needs_sandbox(code: str, meta: dict | None = None, engine: str | None = None) -> bool:
    return needs_sandbox(code, meta=meta, engine=engine)
