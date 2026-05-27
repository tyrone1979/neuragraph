"""Plugin sandbox configuration (main process)."""
import os

from plugin.sandbox_manifest import get_sandbox, list_sandboxes

# Legacy single-URL override (applies to default sandbox only)
PLUGIN_SERVER_URL = os.environ.get("PLUGIN_SERVER_URL", "").rstrip("/")
PLUGIN_SERVER_PORT = int(os.environ.get("PLUGIN_SERVER_PORT", "0") or "0")


def sandbox_enabled() -> bool:
    return os.environ.get("PLUGIN_SANDBOX", "1").lower() not in ("0", "false", "no")


def default_sandbox_id() -> str:
    enabled = list_sandboxes()
    if not enabled:
        return "flair"
    return enabled[0].id


def url_for_sandbox(sandbox_id: str) -> str:
    if PLUGIN_SERVER_URL and sandbox_id == default_sandbox_id():
        return PLUGIN_SERVER_URL
    spec = get_sandbox(sandbox_id)
    if not spec:
        raise KeyError(f"Unknown sandbox: {sandbox_id}")
    if PLUGIN_SERVER_PORT and sandbox_id == default_sandbox_id():
        return f"http://127.0.0.1:{PLUGIN_SERVER_PORT}"
    return spec.url
