#service/result/loader.py
from pathlib import Path
from typing import Dict, Any
import json
from logging import getLogger
logger = getLogger(__name__)


def _get_path(name):
    path = Path(__file__).resolve().parent.parent.parent / "result" / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def iter_sample_indices(results: Dict[str, Any]) -> list[str]:
    """Numeric sample keys in states.json ('1', '2', ...)."""
    return sorted((k for k in results if str(k).isdigit()), key=lambda k: int(k))


def compact_sample_for_report(state: Any) -> Any:
    """Shrink a persisted workflow state for LLM report input."""
    if not isinstance(state, dict):
        return state
    compact: Dict[str, Any] = {}
    for key in ("metrics", "relations", "pairs", "text", "entities", "route", "result", "head", "tail", "head_id", "tail_id", "filtered_entities", "error"):
        if key not in state or state[key] is None:
            continue
        val = state[key]
        if key == "entities" and isinstance(val, str) and len(val) > 2000:
            compact[key] = val[:2000] + "…"
        elif key == "filtered_entities" and isinstance(val, list) and len(val) > 8:
            compact[key] = val[:8] + ["…"]
        elif key == "text":
            if isinstance(val, str):
                compact[key] = val[:1500] + ("…" if len(val) > 1500 else "")
            elif isinstance(val, list) and val:
                t = str(val[0])
                compact[key] = t[:1500] + ("…" if len(t) > 1500 else "")
            else:
                compact[key] = val
        elif key == "relations":
            if isinstance(val, list):
                compact[key] = val[:40] if len(val) > 40 else val
            elif isinstance(val, dict):
                nested = val.get("relations")
                if isinstance(nested, list):
                    compact[key] = nested[:40]
                elif isinstance(nested, dict):
                    compact[key] = {
                        "_note": "nested relations truncated for report",
                        "preview": list(nested.keys())[:12],
                    }
                else:
                    slim = {
                        k: v
                        for k, v in val.items()
                        if k in ("result", "error", "head", "tail", "head_id", "tail_id")
                    }
                    compact[key] = slim or {"_note": "relations dict truncated"}
            else:
                compact[key] = val
        elif key == "pairs" and isinstance(val, list) and len(val) > 20:
            compact[key] = val[:20] + [{"_note": f"+{len(val) - 20} more pairs"}]
        else:
            compact[key] = val
    return compact if compact else state


def compact_states_for_report(states: Dict[str, Any]) -> Dict[str, Any]:
    """Compact all sample states for report LLM payload."""
    if not states:
        return {}
    out: Dict[str, Any] = {}
    for idx in iter_sample_indices(states):
        out[idx] = compact_sample_for_report(states[idx])
    return out


class ResultLoader:
    @staticmethod
    def load(id: str) -> Dict[str, Any] | None:
        try:
            path = _get_path(id)
            cfg_path = path / "states.json"
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            cfg["id"] = id
            return cfg
        except FileNotFoundError:
            # states.json can be legitimately absent before first successful sample.
            # Keep this silent to avoid noisy "[Errno 2]" masking the real failure.
            return None

    @staticmethod
    def load_samples(id: str) -> Dict[str, Any]:
        data = ResultLoader.load(id)
        if not data:
            return {}
        return {k: data[k] for k in iter_sample_indices(data)}

    @staticmethod
    def save(id: str, idx: str | int, result: Dict[str, Any]) -> None:
        path = _get_path(id)
        path.mkdir(parents=True, exist_ok=True)
        cfg_path = path / "states.json"
        store: Dict[str, Any] = {}
        if cfg_path.exists():
            store = json.loads(cfg_path.read_text(encoding="utf-8"))
        store[str(idx)] = result
        cfg_path.write_text(
            json.dumps(store, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
