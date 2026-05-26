"""
Run Playwright UI tests.

  python ui_tests/run_tests.py --suite current     # flaky / new tests (default)
  python ui_tests/run_tests.py --suite regression  # stable tests 1-14
  python ui_tests/run_tests.py --suite experiment # batch experiment UI
  python ui_tests/run_tests.py --suite all
"""
import argparse
import os
import subprocess
import sys
import time
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
        try:
            urllib.request.urlopen(f"{BASE}/", timeout=2)
            print("[OK] Server started")
            return proc
        except Exception:
            pass
    proc.terminate()
    raise RuntimeError("Server did not start")


def stop_server(proc):
    if proc:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--suite",
        choices=["current", "regression", "experiment", "all"],
        default="current",
    )
    args = parser.parse_args()

    os.chdir(str(ROOT))
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)

    print(f"Python: {PYTHON}")
    ensure_playwright()

    from playwright.sync_api import sync_playwright

    from ui_tests import common
    from ui_tests import current_test
    from ui_tests import experiment_test
    from ui_tests import regression_test

    server = start_server()
    exit_code = 1
    suite_timeout = 900 if args.suite in ("experiment", "all") else None
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.on("pageerror", lambda e: common.page_errors.append(str(e)))

            reg_code = cur_code = exp_code = 0

            if args.suite in ("regression", "all"):
                common.reset_results()
                regression_test.run(page, BASE, str(SCREENSHOTS))
                reg_code = common.write_results(str(SCREENSHOTS))

            if args.suite in ("current", "all"):
                if args.suite == "all":
                    common.reset_results()
                current_test.run(page, BASE, str(SCREENSHOTS), TESTS_DATA)
                cur_code = common.write_results(str(SCREENSHOTS))

            if args.suite in ("experiment", "all"):
                if args.suite == "all":
                    common.reset_results()
                experiment_test.run(page, BASE, str(SCREENSHOTS), TESTS_DATA)
                exp_code = common.write_results(str(SCREENSHOTS))

            browser.close()
            exit_code = max(reg_code, cur_code, exp_code)
    finally:
        stop_server(server)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
