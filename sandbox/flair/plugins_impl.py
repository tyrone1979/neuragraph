"""Flair + PGM plugins (runs inside sandbox/flair/venv only)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class Plugin:
    def load(self) -> dict[str, Any]:
        return {}


class FlairTagger(Plugin):
    def load(self) -> dict[str, Any]:
        try:
            from flair.models import SequenceTagger

            model_dir = (
                Path(__file__).resolve().parent.parent.parent
                / "models"
                / "hunflair2-ner"
                / "pytorch_model.bin"
            )
            if model_dir.exists():
                flair_tagger = SequenceTagger.load(str(model_dir))
                return {"tag": flair_tagger}
        except ImportError:
            pass
        print("[sandbox:flair] FlairTagger: Flair not available or no local model.")
        return {}


class PGMExecutor(Plugin):
    def load(self) -> dict[str, Any]:
        safe_builtins = {
            "range": range,
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "set": set,
            "tuple": tuple,
            "enumerate": enumerate,
            "zip": zip,
            "max": max,
            "min": min,
            "sum": sum,
            "abs": abs,
            "round": round,
            "sorted": sorted,
            "isinstance": isinstance,
        }

        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            allowed = {"flair", "flair.data", "re"}
            if name not in allowed:
                raise ImportError(f"Import {name} not allowed")
            return __import__(name, globals, locals, fromlist, level)

        safe_builtins["__import__"] = safe_import
        return {
            "exec_globals": {
                "__builtins__": safe_builtins,
                "__result__": None,
                "re": re,
            }
        }
