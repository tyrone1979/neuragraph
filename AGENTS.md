# AGENTS.md

Guidance for AI coding agents working in this repository.

## Cursor Cloud specific instructions

### System prerequisites (one-time per VM image)

Ubuntu/Debian hosts need `python3.12-venv` before the main venv can be created:

```bash
sudo apt-get install -y python3.12-venv
```

### Python environment

- **Python 3.12+** required (LangChain 1.x).
- Main venv: `.venv` at repo root (`python3.12 -m venv .venv`).
- After `pip install -r requirements.txt`, **Linux/macOS must reinstall** `langgraph-prebuilt` last (see `README.md` Environment Setup).
- Always set `PYTHONPATH` to the repo root when running Python outside `./start.sh`:

```bash
export PYTHONPATH=/workspace   # or $(pwd) from repo root
```

### Services

| Service | Port | Start |
|---------|------|-------|
| NeuraGraph Flask UI | 5001 | `./start.sh` |
| Flair plugin sandbox | 5002 | Included in `./start.sh` (or `./scripts/start_plugin_sandbox.sh flair`) |

Lifecycle: `./status.sh`, `./stop.sh`. Logs under `logs/`.

First-time Flair sandbox (heavy; torch CPU ~180MB):

```bash
chmod +x sandbox/setup_venv.sh scripts/start_plugin_sandbox.sh start.sh stop.sh status.sh
./sandbox/setup_venv.sh flair
```

Without the Flair venv, `./start.sh` still runs Flask but logs a sandbox warning; PGM agents that need Flair will fail.

### Running tests

No dedicated linter in-repo. Use unit tests as the fast check:

```bash
PYTHONPATH=. .venv/bin/python -m ui_tests.run_tests --suite unit
```

**Important:** Run tests as a module (`python -m ui_tests.run_tests`), not `python ui_tests/run_tests.py`. The script path puts `ui_tests/` first on `sys.path`, which shadows the top-level `utils/` package and breaks imports.

Playwright UI suites need `pip install -r ui_tests/requirements-ui.txt` and `playwright install chromium`.

### LLM configuration

No `.env` file. API keys live in `meta/llms/*.json`. Live LLM/graph tests need configured connectors; mock suites (`--suite unit`, `--suite agents`) do not.

### Gotchas

- `langgraph` / `langgraph-prebuilt` namespace collision on Linux — always reinstall prebuilt after main deps.
- Flair model weights at `models/hunflair2-ner/pytorch_model.bin` are gitignored; sandbox health returns `flair_loaded: false` without them (graceful degradation).
- Some unit tests may fail on template string assertions (known drift vs current UI); 52/55 pass with `python -m ui_tests.run_tests --suite unit`.
