# NeuraGraph

A lightweight platform for building LLM-powered workflow agents for biomedical NLP and knowledge graph tasks.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Environment Setup

Requires **Python 3.12** (langchain 1.x+ dependency). Install the main app and plugin sandboxes separately.

### 1. System prerequisites

**Windows** — [Python 3.12](https://www.python.org/downloads/) (check "Add to PATH").

**Linux (Ubuntu/Debian)**

```bash
apt install python3.12 python3.12-venv
```

The `python3.12-venv` package provides `ensurepip` — without it, `python3.12 -m venv` fails with exit status 1.

### 2. Main application

**Windows**

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Linux / macOS**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# langgraph and langgraph-prebuilt share a namespace; reinstall prebuilt last
pip install --force-reinstall --no-deps langgraph-prebuilt==1.1.0
```

> **Why the extra line?** `langgraph` depends on `langgraph-prebuilt`, so pip installs prebuilt *before* langgraph. Since both write to `langgraph/prebuilt/__init__.py`, langsgraph's version (missing `ToolCallTransformer`) overwrites prebuilt's. Reinstalling `langgraph-prebuilt` last fixes this. This is not needed on Windows where pip may resolve in a different order.

Key version requirements (pinned in `requirements.txt`):

| Package | Version |
|---------|---------|
| langchain | 1.3.1 |
| langgraph | 1.2.1 |
| langchain-core | 1.4.0 |
| langchain-openai | 1.2.1 |
| langchain-ollama | 1.1.0 |
| langgraph-checkpoint | 4.1.0 |
| langgraph-prebuilt | 1.1.0 |
| langgraph-sdk | 0.3.14 |

> **Note:** `create_agent` was introduced in langchain 1.0. Older versions (e.g. 0.2.17) do **not** have this API and will fail at import.

### 3. Plugin sandboxes (Flair NER, port 5002)

Heavy PGM plugins run in isolated sidecar venvs defined in `meta/plugins_sandbox.json`. The setup script picks the system Python (preferring 3.12) and creates a dedicated venv under `sandbox/<id>/`.

**Windows**

```powershell
.\sandbox\setup_venv.ps1 -Name flair
```

**Linux / macOS**

```bash
chmod +x sandbox/setup_venv.sh
./sandbox/setup_venv.sh flair
```

Linux sandbox setup installs `torch==2.6.0+cpu` from the PyTorch CPU index for Flair.

To add a custom sandbox, copy `sandbox/_template` to `sandbox/<id>/`, set `enabled: true` in the manifest, then run setup with that id.

Start a single sandbox manually (foreground or background):

**Windows:** `.\scripts\start_plugin_sandbox.ps1 -Name flair`
**Linux / macOS:** `./scripts/start_plugin_sandbox.sh flair` (add `-b` for background)

## Quick Start

After setup above:

**Windows**

```powershell
.\start.bat          # Foreground (Ctrl+C to stop)
```

**Linux / macOS**

```bash
chmod +x start.sh stop.sh status.sh chat.sh sandbox/setup_venv.sh scripts/start_plugin_sandbox.sh

./start.sh           # Start in background (survives terminal close)
./stop.sh            # Stop all background processes
./status.sh          # Check running status
```

Open **http://127.0.0.1:5001**.

Terminal chat: `.\chat.bat` or `./chat.sh` (optional `--llm deepseek`).

> **Background mode** (Linux/macOS): `./start.sh` runs Flask and sandboxes under `nohup` with PIDs tracked in `.pids/` and output logged to `logs/`. Closing the terminal won't stop them. Use `./stop.sh` to shut down cleanly.

## Documentation

| Document | Description |
|----------|-------------|
| [doc/SUPPLEMENTARY.md](doc/SUPPLEMENTARY.md) | Supplementary Material — architecture, examples, component inventory |
| [doc/MANUAL.md](doc/MANUAL.md) | **User manual** — full UI walkthrough with 30+ screenshots |
| [doc/EXPERIMENT_GUIDE.md](doc/EXPERIMENT_GUIDE.md) | Startup, metadata schema, metrics, experiments, and optimization pipeline |
| [doc/CODE_WIKI.md](doc/CODE_WIKI.md) | Architecture and coding conventions |
| [doc/CHAT_COMMANDS.md](doc/CHAT_COMMANDS.md) | Floating assistant / terminal slash commands |
| [doc/AUTOGEN_SKILL.md](doc/AUTOGEN_SKILL.md) | LLM workflow generation reference |

### Refresh UI screenshots

```powershell
.\start.bat
py -3 scripts/refresh_manual_screenshots.py
py -3 scripts/capture_supplemental_screenshots.py
```

Screenshots are saved to `doc/images/` and embedded in `MANUAL.md`.

## Project Layout

```
meta/          agents, graphs, llms, tools, exps (+ version snapshots)
service/       runtime entities, optimization, PubTator, chat commands
ui/            Flask app, JointJS editor, experiment wizard, chat widget
plugin/        PGM sandbox, metrics, Flair
tests/         per-agent / per-workflow CSV datasets (no test scripts)
ui_tests/      run_tests.py; suites/; unit/; reports/ (see doc/TESTING.md)
result/        experiment states.json and reports
utils/         bindings, workflow metrics
scripts/       screenshot refresh, optimize CLI
doc/           documentation + images/; TESTING.md (suites, unit tests, report links)
```

## License

MIT — see [LICENSE](LICENSE) if present.
