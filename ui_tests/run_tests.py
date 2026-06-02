"""
Run UI Playwright suites and optional unit tests.

  python ui_tests/run_tests.py --suite current       # flaky / new UI tests (default)
  python ui_tests/run_tests.py --suite regression    # stable UI tests 1-14
  python ui_tests/run_tests.py --suite experiment    # batch experiment UI
  python ui_tests/run_tests.py --suite cid-experiment
  python ui_tests/run_tests.py --suite graphs        # all meta/graphs (full suite)
  python ui_tests/run_tests.py --suite agents        # agent suite (mock LLM default)
  python ui_tests/run_tests.py --suite agents-live   # agent suite with real deepseek/gpt-oss
  python ui_tests/run_tests.py --suite unit          # ui_tests/unit/test_*.py
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
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from plugin.sandbox_process import start_all_sandboxes

    return start_all_sandboxes()


def start_server():
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
    import urllib.request

    for _ in range(40):
        time.sleep(0.5)
        if proc.poll() is not None:
            out = proc.stdout.read().decode("utf-8", errors="replace") if proc.stdout else ""
            err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
            raise RuntimeError(
                f"Server exited early (code={proc.returncode}).\nstderr:\n{err[-2000:]}\nstdout:\n{out[-500:]}"
            )
        try:
            urllib.request.urlopen(f"{BASE}/", timeout=2)
            print("[OK] Server started")
            return proc
        except Exception:
            pass
    try:
        urllib.request.urlopen(f"{BASE}/graph/new", timeout=30)
    except Exception:
        pass
    err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
    proc.terminate()
    raise RuntimeError(f"Server did not start within 20s.\nstderr:\n{err[-2000:]}")


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
        choices=[
            "current",
            "regression",
            "experiment",
            "cid-experiment",
            "graphs",
            "agents",
            "agents-live",
            "unit",
            "all",
        ],
        default="current",
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
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)

    print(f"Python: {PYTHON}")

    if args.suite in ("agents", "agents-live"):
        os.environ["PYTHONPATH"] = str(ROOT)
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from ui_tests.suites.agent_invoke_mock_llm_suite import main as run_agent_suite

        live_argv = ["--live-llm", "--llm", "auto"] if args.suite == "agents-live" else []
        sys.exit(run_agent_suite(live_argv))

    if args.suite == "unit":
        sys.exit(run_unit_tests())

    ensure_playwright()

    from playwright.sync_api import sync_playwright

    from ui_tests.suites import (
        playwright_cid_experiment_suite as cid_experiment,
        playwright_current_suite as current,
        playwright_experiment_suite as experiment,
        playwright_graph_full_suite as graph,
        playwright_regression_suite as regression,
    )
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

            reg_code = cur_code = exp_code = graph_code = 0

            if args.suite in ("regression", "all"):
                common.reset_results()
                regression.run(page, base_url, str(SCREENSHOTS))
                reg_code = common.write_results(str(SCREENSHOTS))

            if args.suite in ("current", "all"):
                if args.suite == "all":
                    common.reset_results()
                current.run(page, base_url, str(SCREENSHOTS), TESTS_DATA)
                cur_code = common.write_results(str(SCREENSHOTS))

            if args.suite in ("experiment", "all"):
                if args.suite == "all":
                    common.reset_results()
                experiment.run(page, base_url, str(SCREENSHOTS), TESTS_DATA)
                exp_code = common.write_results(str(SCREENSHOTS))

            if args.suite in ("cid-experiment", "all"):
                common.reset_results()
                cid_experiment.run(page, base_url, str(SCREENSHOTS), TESTS_DATA)
                exp_code = max(exp_code, common.write_results(str(SCREENSHOTS)))

            if args.suite in ("graphs", "all"):
                common.reset_results()
                graph.run(page, base_url, str(SCREENSHOTS), TESTS_DATA)
                graph_code = common.write_results(str(SCREENSHOTS))

            browser.close()
            exit_code = max(reg_code, cur_code, exp_code, graph_code)
            if args.suite == "all":
                exit_code = max(exit_code, run_unit_tests())
    finally:
        stop_server(server)
        from plugin.sandbox_process import stop_processes

        stop_processes(plugin_procs)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
