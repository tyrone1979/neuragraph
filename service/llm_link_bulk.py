"""Bulk-update the `model` field on all LLM-type agents."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from service.meta.agent_version import AgentVersionStore
from service.meta.loader import MetaLoader

_version_store = AgentVersionStore()


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "y", "on"):
        return True
    if text in ("0", "false", "no", "n", "off", ""):
        return False
    return default


def _parse_agent_ids(raw: Any) -> list[str] | None:
    if raw is None:
        return None
    if isinstance(raw, list):
        ids = [str(x).strip() for x in raw if str(x).strip()]
        return ids or None
    text = str(raw).strip()
    if not text:
        return None
    return [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]


def bulk_update_llm_links(
    target_model: str,
    *,
    source_model: str | None = None,
    agent_ids: list[str] | None = None,
    dry_run: bool = False,
    change_note: str = "",
) -> dict[str, Any]:
    """
    Point every matching LLM agent's `model` field at `target_model`.

    Args:
        target_model: LLM connector id under meta/llms/ (filename stem).
        source_model: When set, only agents currently using this model are updated.
        agent_ids: Optional allow-list of agent ids; defaults to all LLM agents.
        dry_run: Preview changes without writing files.
        change_note: Version snapshot note when persisting updates.
    """
    target = (target_model or "").strip()
    if not target:
        return {"error": "Missing target_model", "updated": [], "skipped": [], "dry_run": dry_run}

    if not MetaLoader.load("llms", target):
        return {
            "error": f"LLM connector '{target}' not found under meta/llms/",
            "updated": [],
            "skipped": [],
            "dry_run": dry_run,
        }

    source = (source_model or "").strip() or None
    allow = {aid.strip() for aid in (agent_ids or []) if str(aid).strip()} or None
    note = (change_note or "").strip() or f"Bulk LLM link -> {target}"

    agents = MetaLoader.loads("agents") or []
    updated: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for agent in agents:
        agent_id = str(agent.get("id") or "").strip()
        if not agent_id:
            continue
        if (agent.get("type") or "").strip().upper() != "LLM":
            skipped.append({"agent_id": agent_id, "reason": "not LLM"})
            continue
        if allow is not None and agent_id not in allow:
            skipped.append({"agent_id": agent_id, "reason": "not in agent_ids filter"})
            continue

        old_model = (agent.get("model") or "").strip()
        if source and old_model != source:
            skipped.append(
                {
                    "agent_id": agent_id,
                    "reason": "source_model mismatch",
                    "model": old_model or None,
                }
            )
            continue
        if old_model == target:
            skipped.append(
                {"agent_id": agent_id, "reason": "already on target_model", "model": old_model}
            )
            continue

        row = {
            "agent_id": agent_id,
            "name": agent.get("name"),
            "old_model": old_model or None,
            "new_model": target,
        }
        if dry_run:
            updated.append({**row, "written": False})
            continue

        payload = dict(agent)
        payload["model"] = target
        payload["updated_at"] = datetime.now().isoformat()
        if not MetaLoader.dump("agents", agent_id, payload):
            skipped.append({"agent_id": agent_id, "reason": "save failed", "model": old_model})
            continue

        saved = MetaLoader.load("agents", agent_id) or payload
        snapshot = _version_store.save_snapshot(
            agent_id,
            saved,
            change_note=note,
            source="llm_link_bulk_update",
            created_by="agent",
        )
        updated.append(
            {
                **row,
                "written": True,
                "version": snapshot.get("version"),
                "version_created": snapshot.get("created", False),
            }
        )

    return {
        "target_model": target,
        "source_model": source,
        "dry_run": dry_run,
        "updated_count": len(updated),
        "skipped_count": len(skipped),
        "updated": updated,
        "skipped": skipped,
    }
