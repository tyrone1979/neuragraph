"""Resolve LLM api_key from env or meta/llms/.secrets (local only, gitignored)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_LLM_DIR = Path(__file__).resolve().parent.parent.parent / "meta" / "llms"
_SECRETS_DIR = _LLM_DIR / ".secrets"

_ENV_ALIASES: dict[str, list[str]] = {
    "deepseek": ["DEEPSEEK_API_KEY"],
    "kimi-2.6": ["KIMI_API_KEY", "KIMI_2_6_API_KEY", "MOONSHOT_API_KEY"],
    "moonshot-v1-8k": ["MOONSHOT_API_KEY", "KIMI_API_KEY"],
    "moonshot-v1-32k": ["MOONSHOT_API_KEY", "KIMI_API_KEY"],
}


def resolve_llm_api_key(cfg: dict[str, Any], llm_id: str) -> dict[str, Any]:
    out = dict(cfg)
    if str(out.get("api_key") or "").strip():
        return out

    for env_name in _ENV_ALIASES.get(llm_id, []):
        env_key = os.environ.get(env_name, "").strip()
        if env_key:
            out["api_key"] = env_key
            return out

    generic = os.environ.get(f"{llm_id.upper().replace('-', '_')}_API_KEY", "").strip()
    if generic:
        out["api_key"] = generic
        return out

    secret_path = _SECRETS_DIR / f"{llm_id}.json"
    if secret_path.is_file():
        try:
            secret = json.loads(secret_path.read_text(encoding="utf-8"))
            secret_key = str(secret.get("api_key") or "").strip()
            if secret_key:
                out["api_key"] = secret_key
        except (OSError, json.JSONDecodeError):
            pass
    return out
