"""One-off helper to build regression_test.py from legacy runner."""
from pathlib import Path

src = Path(__file__).parent.parent / "tests" / "_test_runner_standalone.py"
lines = src.read_text(encoding="utf-8").splitlines()
body = lines[81:410]
header = '''"""Stable regression UI tests (sections 1-14)."""
import time
from playwright.sync_api import Page
from ui_tests.common import canvas_center, fail, goto, ok, paper_scale, shot, wf_nodes


def run(page: Page, base: str, screenshots_dir: str) -> None:
'''
indented = []
for line in body:
    indented.append(("    " + line) if line.strip() else "")
text = header + "\n".join(indented) + "\n"
text = text.replace("shot(page, ", "shot(page, screenshots_dir, ")
text = text.replace("goto(page, ", "goto(page, base, ")
Path(__file__).parent.joinpath("regression_test.py").write_text(text, encoding="utf-8")
print("wrote regression_test.py", len(indented), "lines")
