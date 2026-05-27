"""Example plugins for a new sandbox — copy and implement."""
from __future__ import annotations

from typing import Any


class Plugin:
    def load(self) -> dict[str, Any]:
        return {}


class ExamplePlugin(Plugin):
    def load(self) -> dict[str, Any]:
        return {"example": "replace with real resources"}
