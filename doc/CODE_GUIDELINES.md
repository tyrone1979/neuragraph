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
├── data                        # Dataset parser, currently supports CID and ChemDisGene dataset
│   ├── data_parser.py
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

### 4.2 Security Model for PGM Agents
The execution of programmatic (PGM‑type) agents is safeguarded by a configurable security layer implemented through the plugin system. Specifically, the PGMExecutor plugin (/plugin/plugins.py) defines a controlled environment via two mechanisms:
- safe_builtins: A whitelist of Python built‑in functions and types permitted for use within PGM agents (e.g., <code>len, str, dict, list</code>).
- safe_import: A function that restricts module imports to a predefined set of allowed libraries (e.g., <code>flair.data, json, re</code>), preventing arbitrary or harmful imports.
```python
class PGMExecutor(Plugin):
    def load(self):
        safe_builtins = {
                    'range': range, 'len': len, 'str': str, 'int': int,
                    'float': float, 'bool': bool, 'list': list, 'dict': dict,
                    'set': set, 'tuple': tuple, 'enumerate': enumerate,
                    'zip': zip, 'max': max, 'min': min, 'sum': sum,
                    'abs': abs, 'round': round, 'sorted': sorted,
                    'isinstance': isinstance
        }

        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
                allowed = {
                    'flair',
                    'flair.data'
                    # change here if needed.
                }
                if name not in allowed:
                        raise ImportError(f"Import {name} not allowed")
                return __import__(name, globals, locals, fromlist, level)

        safe_builtins['__import__'] = safe_import
        exec_globals = {
            '__builtins__': safe_builtins,
            '__result__': None
        }

        return {"exec_globals": exec_globals}
```

### 4.3 Data Parser Implementation
The NeuraGraph framework includes a modular domain-specific data‑parsing subsystem designed to handle various text formats in a unified manner. Located in /data/data_parser.py, the system provides a base class DataParser that defines a common interface, with concrete parsers implementing format‑specific extraction logic.
- Base Class Specification
All parsers inherit from the abstract superclass DataParser, which enforces the following interface:
```python
class DataParser:
    def __init__(self, text: str):
        """
        Initialize the parser with raw text.
        :param text: Raw dataset text in the specific format.
        """
        self.text = text
        self.article_map = {}  # Dictionary: {article_id: parsed_document_dict}
    
    def get_articles(self) -> list:
        """
        Return all parsed articles as a list of dictionaries.
        :return: List of article objects.
        """
        return list(self.article_map.values())
    
    def get(self, article_id: str) -> dict:
        """
        Retrieve a specific article by its identifier.
        :param article_id: Unique identifier of the article (e.g., PMID).
        :return: Dictionary containing the article data.
        """
        return self.article_map.get(article_id, {})
```
- Supported Dataset Parsers 
    - CIDParser – Chemical‑Induced‑Disease Dataset: Implements parsing for the BioCreative V Chemical‑Disease Relations (CDR) corpus[27], a benchmark dataset for chemical‑induced‑disease relation extraction. The parser extracts PubMed‑style documents, each containing:
      - PMID (PubMed identifier)
      - Title and abstract text 
      - Annotated chemical and disease entities with character‑level offsets 
      - Chemical‑disease relation annotations

    - ChemDisGeneParser – ChemDisGene Dataset: Processes the ChemDisGene[28] corpus, a biomedical multi‑label document‑level relation extraction dataset. This parser extracts:
      - Document identifiers and full text
      - Multi‑label annotations for chemical‑disease‑gene relations
      - Metadata including evidence levels and relation types

    This unified parsing architecture enables researchers to seamlessly switch between benchmark datasets while maintaining consistent data interfaces for training, testing, and evaluation of biomedical NLP models.

