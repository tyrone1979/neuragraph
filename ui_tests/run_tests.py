"""
Run UI Playwright suites and optional unit tests.

  python ui_tests/run_tests.py --suite regression-exp     # representative exp runs (default 6)
  python ui_tests/run_tests.py --suite regression-graph   # all graphs (G2–G4)
  python ui_tests/run_tests.py --suite regression-tool    # all tools (UI + run_tool API)
  python ui_tests/run_tests.py --suite regression-agent   # all agents (UI + mock LLM invoke)
  python ui_tests/run_tests.py --suite agents             # agent batch only (mock LLM)
  python ui_tests/run_tests.py --suite agents-live        # agent batch with real LLM
  python ui_tests/run_tests.py --suite unit
  python ui_tests/run_tests.py --suite all
  python ui_tests/suites/agent_invoke_mock_llm_suite.py --live-llm
"""
import argparse
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI_TESTS = ROOT / "ui_tests"
SCREENSHOTS = UI_TESTS / "screenshots"
TESTS_DATA = ROOT / "tests"
BASE = "http://127.0.0.1:5001"

REGRESSION_SUITES = (
    "regression-exp",
    "regression-graph",
    "regression-tool",
    "regression-agent",
)


def ensure_root_on_path() -> None:
    """Project root must precede ui_tests/ so `utils` is not shadowed by ui_tests/utils."""
    root_str = str(ROOT)
    ui_tests_str = str(UI_TESTS)
    for path in (root_str, ui_tests_str):
        while path in sys.path:
            sys.path.remove(path)
    sys.path.insert(0, root_str)


def load_regression_suite(suite_name: str):
    if suite_name == "regression-exp":
        from ui_tests.suites import playwright_regression_exp as mod
    elif suite_name == "regression-graph":
        from ui_tests.suites import playwright_regression_graph as mod
    elif suite_name == "regression-tool":
        from ui_tests.suites import playwright_regression_tool as mod
    elif suite_name == "regression-agent":
        from ui_tests.suites import playwright_regression_agent as mod
    else:
        raise ValueError(f"unknown regression suite: {suite_name}")
    return mod


def resolve_python() -> Path:
    if sys.platform == "win32":
        candidates = [ROOT / "venv" / "Scripts" / "python.exe", ROOT / ".venv" / "Scripts" / "python.exe"]
    else:
        candidates = [ROOT / "venv" / "bin" / "python", ROOT / ".venv" / "bin" / "python"]
    for p in candidates:
        if p.is_file():
            return p.resolve()
    return Path(sys.executable).resolve()


PYTHON = resolve_python()


def ensure_playwright() -> None:
    try:
        subprocess.run([str(PYTHON), "-c", "import playwright"], check=True, capture_output=True, cwd=str(ROOT))
    except subprocess.CalledProcessError:
        print("[ERROR] Install Playwright:", PYTHON)
        sys.exit(1)


def start_plugin_servers():
    """Start all enabled sandboxes from manifest."""
    ensure_root_on_path()
    from plugin.sandbox_process import start_all_sandboxes

    return start_all_sandboxes()


def _server_healthy(base: str, timeout: int = 5) -> bool:
    import urllib.request

    for path in ("/", "/graph/", "/graph/new"):
        try:
            urllib.request.urlopen(f"{base.rstrip('/')}{path}", timeout=timeout)
            return True
        except Exception:
            pass
    return False


def start_server():
    if _server_healthy(BASE, timeout=3):
        print(f"[OK] Server already running at {BASE}")
        return None

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.Popen(
        [
            str(PYTHON),
            "-c",
            "from ui.app import create_app; create_app().run("
            "host='0.0.0.0', port=5001, debug=False, threaded=True, use_reloader=False)",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    max_wait = int(os.environ.get("NG_SERVER_START_TIMEOUT", "90"))
    interval = 0.5
    attempts = max(1, int(max_wait / interval))

    for _ in range(attempts):
        time.sleep(interval)
        if proc.poll() is not None:
            out = proc.stdout.read().decode("utf-8", errors="replace") if proc.stdout else ""
            err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
            raise RuntimeError(
                f"Server exited early (code={proc.returncode}).\nstderr:\n{err[-2000:]}\nstdout:\n{out[-2000:]}"
            )
        if _server_healthy(BASE, timeout=5):
            print("[OK] Server started")
            return proc

    err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
    proc.terminate()
    raise RuntimeError(
        f"Server did not respond within {max_wait}s.\nstderr:\n{err[-2000:]}"
    )


def stop_server(proc):
    if proc:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


_PYTEST_ONLY = frozenset({"test_dataset_cid_suite.py", "test_testset_sample.py"})


def run_unit_tests() -> int:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    unit_dir = UI_TESTS / "unit"
    for path in sorted(unit_dir.glob("test_*.py")):
        if path.name in _PYTEST_ONLY:
            continue
        mod_suite = loader.loadTestsFromName(f"ui_tests.unit.{path.stem}")
        suite.addTests(mod_suite)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--suite",
        choices=[*REGRESSION_SUITES, "agents", "agents-live", "unit", "all"],
        default="regression-exp",
    )
    parser.add_argument(
        "--external-server",
        action="store_true",
        help="Do not start Flask; assume server already running at --base",
    )
    parser.add_argument("--base", default=BASE, help="Base URL (default http://127.0.0.1:5001)")
    args = parser.parse_args()
    base_url = args.base.rstrip("/")

    os.chdir(str(ROOT))
    os.environ["PYTHONPATH"] = str(ROOT)
    ensure_root_on_path()
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)

    print(f"Python: {PYTHON}")

    if args.suite in ("agents", "agents-live"):
        from ui_tests.suites.agent_invoke_mock_llm_suite import main as run_agent_suite

        live_argv = ["--live-llm", "--llm", "auto"] if args.suite == "agents-live" else []
        sys.exit(run_agent_suite(live_argv))

    if args.suite == "unit":
        sys.exit(run_unit_tests())

    ensure_playwright()

    from playwright.sync_api import sync_playwright

    from ui_tests.utils import playwright_helpers as common

    os.environ.setdefault("PLUGIN_SANDBOX", "1")
    os.environ.setdefault("PLUGIN_SERVER_URL", "http://127.0.0.1:5002")

    plugin_procs = []
    server = None
    if not args.external_server:
        plugin_procs = start_plugin_servers() or []
        server = start_server()
    exit_code = 1
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.on("pageerror", lambda e: common.page_errors.append(str(e)))

            codes: list[int] = []

            def run_suite(_name: str, fn) -> None:
                common.reset_results()
                fn()
                codes.append(common.write_results(str(SCREENSHOTS)))

            suites_to_run = REGRESSION_SUITES if args.suite == "all" else (args.suite,)
            for suite_name in suites_to_run:
                mod = load_regression_suite(suite_name)
                run_suite(
                    suite_name,
                    lambda m=mod: m.run(page, base_url, str(SCREENSHOTS), TESTS_DATA),
                )

            browser.close()
            exit_code = max(codes) if codes else 1
            if args.suite == "all":
                exit_code = max(exit_code, run_unit_tests())
    finally:
        stop_server(server)
        from plugin.sandbox_process import stop_processes

        stop_processes(plugin_procs)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
