# Code Guidelines – NeuraGraph

We keep things simple, explicit, and maintainable.  
This is **not** an enterprise monorepo with 100+ engineers — it's a focused BioNLP + LLM workflow prototype.

## 1. Language & Style

- Python 3.11+
- Follow **PEP 8** with **black** formatting (line-length=100)
- Use type hints **everywhere** reasonable (especially in the service/ layer)
- Prefer explicit over implicit (Zen of Python rule #1)
- No magic. If it's not obvious in 5 seconds what a function does → rename it or add a docstring.

## 2. Directory Layout (current & future intention)
```
.
├── data                        # Dataset parser, currently supports CID dataset
│   ├── ctd_parser.py
│   └── data_load.py
├── .gitignore
├── meta                        # Meta directory 
│   ├── agents                  # Agent meta data JSON files
│   │   └── ...                 # e.g., sentence_split.json, dependency_parse.json
│   ├── graphs                  # Graph meta data JSON files
│   │   └── ...                 # e.g., bt.json, ner_4_doc_llm.json
│   ├── llms                    # LLM configurations
│   ├── tools                   # Tool definitions (LLM or PGM based)
│   ├── exps                    # Experiment history and results
│   └── tests                   # Test datasets (uploaded or generated)
├── plugin/                     # Pluggable components
│   ├── plugin_loader.py        # Plugin loader
│   └── plugins.py              # Plugin definitions (e.g., Flair, Postgres)
├── service/                    # Core services
│   ├── entity/                 # Entity models (Agent, Graph, Runner, Test)
│   │   ├── agent.py
│   │   ├── graph.py
│   │   ├── runner.py
│   │   ├── test.py
│   │   └── ...                 # Other entities
│   └── meta/                   # Meta loaders
│       └── loader.py           # Generic loader for JSON meta files
├── ui/                         # UI layer (Flask blueprints and templates)
│   ├── components/             # Reusable UI components (e.g., paginated_table)
│   ├── templates/              # Jinja2 templates
│   │   ├── base.html           # Base layout
│   │   ├── graph.html          # Workflow editor
│   │   ├── experiment.html     # Experiment runner
│   │   └── ...                 # Other pages
│   ├── agent_api.py            # Agent API blueprint
│   ├── dataset_api.py          # Dataset API
│   ├── experiment_api.py       # Experiment API
│   ├── graph_api.py            # Graph API
│   ├── llm_api.py              # LLM API
│   ├── stream_api.py           # SSE streaming API
│   ├── testset_api.py          # Testset API
│   ├── tool_api.py             # Tool API
│   └── ...                     # Other blueprints
├── static/                     # Static assets (JS, CSS)
│   ├── css/                    # Styles (Bootstrap, custom)
│   ├── js/                     # Scripts (JointJS, ECharts, etc.)
│   └── img/                    # Images (e.g., logo)
├── tests/                      # Runtime test data (git ignored)
├── result/                     # Experiment outputs (CSV, etc., git ignored)
├── app.py                      # Flask app entry point
├── run.sh                      # Startup script
├── requirements.txt            # Dependencies
└── README.md                   # Project documentation
```

## 3. Persistence

- **Default**: In-memory (fast, but lost on restart)
- **Optional**: Persistence for agent/graph states in PostgreSQL
- Uncomment `./plugin/plugins.py` 'class PostgresCheckpointer(Plugin)' if you want to persist agent/graph states in PostgreSQL (assuming PostgreSQL is installed).

## 4. Enhancement
### 4.1 Plugin Development
Plugin objects are instantiated when the app launches. Anywhere in the code, use `plugin.plugins.get_plugin(object_name)` to retrieve it.

In `./plugin/plugins.py`:
- Extend `Plugin` to add a new plugin:
```python
class Plugin:
    def load(self):
        pass
    async def aload(self):
        pass
```
- Example: Define a plugin
```python
class MemoryCheckpointer(Plugin):
    def load(self):
        from langgraph.checkpoint.memory import InMemorySaver
        memory = InMemorySaver()
        return {"InMemorySaver": memory}
```
- Use it somewhere:
```python
from plugin.plugin_loader import get_plugin
saver = get_plugin("InMemorySaver")
```