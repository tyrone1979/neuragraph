"""Load meta/plugins_sandbox.json and resolve which sandbox runs given code/agent meta."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "meta" / "plugins_sandbox.json"


@dataclass(frozen=True)
class SandboxSpec:
    id: str
    port: int
    venv: Path
    entry: Path
    markers: tuple[str, ...]
    engines: tuple[str, ...]
    enabled: bool
    description: str

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def venv_python(self) -> Path:
        if sys_platform_win():
            return self.venv / "Scripts" / "python.exe"
        return self.venv / "bin" / "python"


def sys_platform_win() -> bool:
    import sys

    return sys.platform == "win32"


@lru_cache(maxsize=1)
def load_manifest() -> dict[str, SandboxSpec]:
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    out: dict[str, SandboxSpec] = {}
    for sid, cfg in (raw.get("sandboxes") or {}).items():
        out[sid] = SandboxSpec(
            id=sid,
            port=int(cfg["port"]),
            venv=(ROOT / cfg["venv"]).resolve(),
            entry=(ROOT / cfg["entry"]).resolve(),
            markers=tuple(cfg.get("markers") or []),
            engines=tuple(cfg.get("engines") or []),
            enabled=bool(cfg.get("enabled", True)),
            description=str(cfg.get("description") or ""),
        )
    return out


def list_sandboxes(*, enabled_only: bool = True) -> list[SandboxSpec]:
    specs = list(load_manifest().values())
    if enabled_only:
        specs = [s for s in specs if s.enabled]
    return sorted(specs, key=lambda s: s.port)


def get_sandbox(sandbox_id: str) -> SandboxSpec | None:
    return load_manifest().get(sandbox_id)


def code_matches_sandbox(code: str, spec: SandboxSpec) -> bool:
    if not code:
        return False
    return any(m in code for m in spec.markers)


def resolve_sandbox(
    code: str = "",
    *,
    meta: dict[str, Any] | None = None,
    engine: str | None = None,
    explicit: str | None = None,
) -> str | None:
    """
    Pick sandbox id for this execution, or None if main process should handle it.

    Priority: explicit arg > meta['sandbox'] > meta engine > code markers (first enabled match).
    """
    meta = meta or {}
    explicit = explicit or meta.get("sandbox")
    if explicit:
        spec = get_sandbox(str(explicit))
        if spec and spec.enabled:
            return spec.id
        raise ValueError(f"Unknown or disabled sandbox: {explicit}")

    eng = (engine or meta.get("engine") or "").strip().lower()
    if eng:
        for spec in list_sandboxes():
            if eng in {e.lower() for e in spec.engines}:
                return spec.id

    if code:
        for spec in list_sandboxes():
            if code_matches_sandbox(code, spec):
                return spec.id

    return None


def needs_sandbox(
    code: str = "",
    *,
    meta: dict[str, Any] | None = None,
    engine: str | None = None,
) -> bool:
    return resolve_sandbox(code, meta=meta, engine=engine) is not None
