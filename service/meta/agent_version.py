from __future__ import annotations

import difflib
import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class AgentVersionStore:
    """Filesystem-backed version history for agent configs."""

    def __init__(self) -> None:
        self._root = Path(__file__).resolve().parent.parent.parent / "meta" / "agent_versions"
        self._root.mkdir(parents=True, exist_ok=True)

    def _agent_dir(self, agent_id: str) -> Path:
        path = self._root / agent_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _index_path(self, agent_id: str) -> Path:
        return self._agent_dir(agent_id) / "index.json"

    @staticmethod
    def _normalize_content(content: Dict[str, Any]) -> Dict[str, Any]:
        data = deepcopy(content or {})
        data.pop("id", None)  # runtime-added id should not affect version hash
        return data

    @staticmethod
    def _content_hash(content: Dict[str, Any]) -> str:
        payload = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _load_index(self, agent_id: str) -> Dict[str, Any]:
        p = self._index_path(agent_id)
        if not p.exists():
            return {"agent_id": agent_id, "latest": None, "versions": []}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if "versions" not in data or not isinstance(data["versions"], list):
                data["versions"] = []
            if "latest" not in data:
                data["latest"] = data["versions"][-1]["version"] if data["versions"] else None
            if "agent_id" not in data:
                data["agent_id"] = agent_id
            return data
        except Exception:
            return {"agent_id": agent_id, "latest": None, "versions": []}

    def _save_index(self, agent_id: str, index: Dict[str, Any]) -> None:
        self._index_path(agent_id).write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_versions(self, agent_id: str) -> List[Dict[str, Any]]:
        index = self._load_index(agent_id)
        versions = list(index.get("versions", []))
        versions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return versions

    def content_hash(self, content: Dict[str, Any]) -> str:
        return self._content_hash(self._normalize_content(content))

    def find_version_by_content(self, agent_id: str, content: Dict[str, Any]) -> str:
        target = self.content_hash(content)
        for item in self.list_versions(agent_id):
            if item.get("content_hash") == target:
                return str(item.get("version") or "")
        return ""

    def version_at_time(self, agent_id: str, timestamp: str) -> str:
        ts = str(timestamp or "").strip()
        if not ts:
            index = self._load_index(agent_id)
            return str(index.get("latest") or "")
        eligible = [
            v for v in self.list_versions(agent_id)
            if str(v.get("created_at") or "") <= ts
        ]
        if not eligible:
            return ""
        eligible.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return str(eligible[0].get("version") or "")

    def load_version(self, agent_id: str, version: str) -> Optional[Dict[str, Any]]:
        p = self._agent_dir(agent_id) / f"{version}.json"
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _next_version_id(self, agent_id: str, index: Dict[str, Any]) -> str:
        num = len(index.get("versions", [])) + 1
        return f"v{num:04d}"

    def save_snapshot(
        self,
        agent_id: str,
        content: Dict[str, Any],
        *,
        change_note: str = "",
        created_by: str = "system",
        source: str = "save",
    ) -> Dict[str, Any]:
        normalized = self._normalize_content(content)
        c_hash = self._content_hash(normalized)
        index = self._load_index(agent_id)
        latest_id = index.get("latest")
        latest_meta = None
        for item in index.get("versions", []):
            if item.get("version") == latest_id:
                latest_meta = item
                break

        # avoid duplicate snapshots for same content hash
        if latest_meta and latest_meta.get("content_hash") == c_hash:
            return {"created": False, "version": latest_id, "meta": latest_meta}

        version = self._next_version_id(agent_id, index)
        parent = latest_id
        now = datetime.now().isoformat()
        item = {
            "version": version,
            "parent_version": parent,
            "created_at": now,
            "created_by": created_by,
            "change_note": (change_note or "").strip(),
            "source": source,
            "content_hash": c_hash,
        }

        payload = {
            "agent_id": agent_id,
            **item,
            "content": normalized,
        }
        (self._agent_dir(agent_id) / f"{version}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        index.setdefault("versions", []).append(item)
        index["latest"] = version
        self._save_index(agent_id, index)
        return {"created": True, "version": version, "meta": item}

    def rollback(
        self,
        agent_id: str,
        version: str,
        *,
        change_note: str = "",
        created_by: str = "system",
    ) -> Optional[Dict[str, Any]]:
        payload = self.load_version(agent_id, version)
        if not payload:
            return None
        content = payload.get("content", {})
        note = change_note or f"rollback to {version}"
        snap = self.save_snapshot(
            agent_id,
            content,
            change_note=note,
            created_by=created_by,
            source="rollback",
        )
        return {"content": content, "snapshot": snap}

    @staticmethod
    def _json_lines(content: Dict[str, Any]) -> List[str]:
        return json.dumps(content, ensure_ascii=False, indent=2, sort_keys=True).splitlines()

    def compare(self, agent_id: str, left_version: str, right_version: str) -> Optional[Dict[str, Any]]:
        left = self.load_version(agent_id, left_version)
        right = self.load_version(agent_id, right_version)
        if not left or not right:
            return None
        left_content = left.get("content", {})
        right_content = right.get("content", {})
        diff = difflib.unified_diff(
            self._json_lines(left_content),
            self._json_lines(right_content),
            fromfile=left_version,
            tofile=right_version,
            lineterm="",
        )
        return {
            "agent_id": agent_id,
            "left": left,
            "right": right,
            "diff": "\n".join(diff),
        }

    def delete_all(self, agent_id: str) -> None:
        d = self._root / agent_id
        if not d.exists():
            return
        for p in d.glob("*"):
            if p.is_file():
                p.unlink()
        d.rmdir()
