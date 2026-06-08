import asyncio
import inspect
import importlib.util
from pathlib import Path

from plugin.plugin_config import sandbox_enabled

# ---------- 模块私有变量 ----------
_sync_plugins = {}          # 同步资源
_async_plugins = {}         # 异步资源
_lock = asyncio.Lock()      # 保证异步加载只跑一次

# ---------- 工具 ----------
def _import_plugins_module():
    here = Path(__file__).parent
    spec = importlib.util.spec_from_file_location("plugins", here / "plugins.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _all_subclasses(cls):
    return set(cls.__subclasses__()).union(
        [s for c in cls.__subclasses__() for s in _all_subclasses(c)]
    )


def _load_sync():
    mod = _import_plugins_module()
    classes = [c for c in _all_subclasses(mod.Plugin) if not inspect.isabstract(c)]
    loaded = {}
    for Cls in classes:
        if sandbox_enabled() and Cls.__name__ == "PGMExecutorInProcess":
            continue
        if not sandbox_enabled() and Cls.__name__ == "PGMExecutorLite":
            continue
        inst = Cls()
        bundle = inst.load() or {}
        loaded.update(bundle)
    if sandbox_enabled():
        print("[plugin] Heavy plugins (Flair/PGM) run in sandbox sidecar; main process stays lightweight.")
    return loaded


# ---------- 异步加载（懒加载，只一次） ----------
async def _load_async():
    global _async_plugins
    mod = _import_plugins_module()
    classes = [c for c in _all_subclasses(mod.Plugin) if not inspect.isabstract(c)]
    async_loaded = {}
    for Cls in classes:
        if sandbox_enabled() and Cls.__name__ == "PGMExecutorInProcess":
            continue
        if not sandbox_enabled() and Cls.__name__ == "PGMExecutorLite":
            continue
        inst = Cls()
        if hasattr(inst, "aload"):
            bundle = await inst.aload() or {}
            async_loaded.update(bundle)
    _async_plugins.update(async_loaded)


# ---------- 对外接口 ----------
def get_plugin(name: str):
    """取同步资源（立即返回）"""
    if name in _sync_plugins:
        return _sync_plugins[name]
    return None


async def aget_plugin(name: str):
    """取异步资源（自动保证只初始化一次）"""
    if name in _async_plugins and not _async_plugins:
        async with _lock:
            if not _async_plugins:
                await _load_async()
        return _async_plugins[name]
    return None


# ---------- 模块初始化：同步资源立即就绪 ----------
_sync_plugins = _load_sync()


async def _aclose_plugins():
    """统一关闭所有异步资源"""
    global _async_plugins
    for name, res in list(_async_plugins.items()):
        if hasattr(res, "__aexit__"):
            try:
                await res.__aexit__(None, None, None)
            except Exception as e:
                print("Failed to close async resource %s: %s", name, e)
    _async_plugins.clear()
