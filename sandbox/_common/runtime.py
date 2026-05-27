"""Shared PGM/tool execution helpers for all sandbox sidecars."""
from __future__ import annotations

import importlib
import inspect
from typing import Any, Callable


def import_plugins_impl(sandbox_id: str):
    return importlib.import_module(f"sandbox.{sandbox_id}.plugins_impl")


def load_all_plugins(sandbox_id: str) -> dict[str, Any]:
    mod = import_plugins_impl(sandbox_id)
    plugin_cls = mod.Plugin
    classes = [c for c in _all_subclasses(plugin_cls) if not inspect.isabstract(c)]
    loaded: dict[str, Any] = {}
    for cls in classes:
        inst = cls()
        bundle = inst.load() or {}
        loaded.update(bundle)
    return loaded


def _all_subclasses(cls: type) -> set[type]:
    out = set(cls.__subclasses__())
    for c in cls.__subclasses__():
        out |= _all_subclasses(c)
    return out


def make_get_plugin(loaded: dict[str, Any]) -> Callable[[str], Any]:
    def get_plugin(name: str) -> Any:
        return loaded.get(name)

    return get_plugin


def normalize_indent(code: str) -> str:
    lines = code.split("\n")
    if not lines:
        return code
    first_line = lines[0]
    initial_indent = len(first_line) - len(first_line.lstrip())
    cleaned = []
    for line in lines:
        if line.startswith(" " * initial_indent):
            line = line[initial_indent:]
        cleaned.append(line)
    return "\n".join(cleaned)


def run_pgm(code: str, state: dict[str, Any], loaded: dict[str, Any]) -> tuple[Any, str | None]:
    exec_globals = loaded.get("exec_globals")
    if not exec_globals:
        return state, "exec_globals not loaded in sandbox"
    exec_globals = dict(exec_globals)
    exec_globals["__result__"] = None
    exec_globals["state"] = state
    exec_globals["get_plugin"] = make_get_plugin(loaded)
    try:
        exec(normalize_indent(code), exec_globals)
        if exec_globals.get("__result__") is not None:
            return exec_globals["__result__"], None
        return state, None
    except Exception as ex:
        return state, str(ex)


def run_tool(code: str, kwargs: dict[str, Any], loaded: dict[str, Any]) -> tuple[Any, str | None]:
    local_ns: dict[str, Any] = {"get_plugin": make_get_plugin(loaded)}
    try:
        exec(code, local_ns)
        func = local_ns.get("func")
        if not callable(func):
            return None, "Code must define callable func(...)"
        return func(**kwargs), None
    except Exception as ex:
        return None, str(ex)
