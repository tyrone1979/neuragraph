# NeuraGraph AutoGen Skill

## Overview

This skill enables an LLM to autonomously generate NeuraGraph configurations (agents, workflows, LLMs, tools) from natural language requirements, and execute the resulting workflow.

## Architecture

```
User Requirement (natural language)
    |
    v
[Analyzer]  --LLM-->  Component Design (what agents/workflows/llms/tools needed)
    |
    v
[Generator] --LLM-->  JSON Config Files (meta/agents/*.json, meta/graphs/*.json, ...)
    |
    v
[Validator]           Schema validation + edge connectivity check
    |
    v
[Executor]            run_workflow.py --graph <graph_id> --input <data>
    |
    v
  Result
```

## Configuration Directories

```
meta/
  agents/    - Agent definitions (LLM/PGM/SUB types)
  graphs/    - Workflow definitions (nodes + edges)
  llms/      - LLM provider configurations
  tools/     - Tool code definitions
  datasets/  - Test datasets
```

## Agent Format Standards

### CRITICAL RULES

1. **Agent ID is the filename** (without `.json`). DO NOT include an `id` field inside the JSON.
2. **Use `name` not `purpose`** - `name` is a short English descriptive name.
3. **Use `model` not `llm`** - For LLM agents, the model field specifies which LLM to use.
4. **Always include `persistence`** - Empty object `{}` if not needed.
5. **Always include `created_at`** - ISO format timestamp.

### LLM Agent Format

```json
{
  "name": "Short English Name",
  "type": "LLM",
  "inputs": ["text"],
  "outputs": {"name": "result", "type": "str"},
  "persistence": {},
  "model": "kimi-2.6",
  "prompt_template": {
    "description": "What this agent does",
    "system": "System prompt...",
    "human": "Human prompt with {field} placeholders..."
  },
  "tools": [],
  "created_at": "2026-05-18T10:00:00"
}
```

### PGM Agent Format

```json
{
  "name": "Short English Name",
  "type": "PGM",
  "inputs": ["text"],
  "outputs": {"name": "result", "type": "str"},
  "persistence": {},
  "process": "Python code using state dict and __result__",
  "created_at": "2026-05-18T10:00:00"
}
```

### SUB Agent Format

```json
{
  "name": "Short English Name",
  "type": "SUB",
  "inputs": ["sentences"],
  "outputs": {"name": "results", "type": "list"},
  "persistence": {},
  "idx": ["sentence"],
  "created_at": "2026-05-18T10:00:00"
}
```

### Agent Type Details

| Type | Purpose | Key Fields |
|------|---------|------------|
| LLM | Call language model | `model`, `prompt_template` (description, system, human), `tools` |
| PGM | Python code execution | `process` (Python code using `state` dict and `__result__`) |
| SUB | Iterate subgraph over list | `idx` (loop variables), `inputs` (iterable) |

### Prompt Template Format

```json
{
  "description": "Brief description of what this agent does",
  "system": "System prompt defining the agent's role",
  "human": "User prompt with {field_name} placeholders"
}
```

Use `{field_name}` placeholders that are replaced from state:
- `{text}` - replaced with `state["text"]`
- `{labels}` - replaced with `state["labels"]`

## Workflow Graph Format

```json
{
  "id": "my_graph",
  "name": "My Pipeline",
  "description": "What it does",
  "nodes": ["START", "agent1", "agent2", "sub_graph", "END"],
  "edges": [
    ["START", "agent1"],
    ["agent1", "agent2"],
    ["agent2", "sub_graph"],
    ["sub_graph", "END"]
  ]
}
```

Subgraphs are graphs whose id starts with `sub_`. They are automatically expanded.

## LLM Config Format

```json
{
  "id": "my_llm",
  "type": "openai|ollama|moonshot|...",
  "model": "gpt-4o",
  "base_url": "https://api.openai.com/v1",
  "api_key": "",
  "temperature": 0.7,
  "max_tokens": 1000
}
```

## Tool Format

```json
{
  "id": "my_tool",
  "name": "My Tool",
  "description": "...",
  "parameters": { "type": "object", "properties": {...}, "required": [...] },
  "code": "def func(query: str) -> dict:
    ...
    return result"
}
```

## State Flow

- Each agent reads from `state` dict (keys = input field names)
- Each agent writes to `state` under its `outputs.name` key
- PGM agents use `state['field']` to read and `__result__ = ...` to write
- SUB agents iterate: `inputs[0]` = list to iterate, `idx[0]` = loop variable name

## Execution Command

```bash
python run_workflow.py --graph <graph_id> --input '{"key":"value"}' --verbose
```

## Design Rules

1. **Graph edges must form a valid DAG** from START to END
2. **Agent inputs must be produced by upstream agents** (or provided as initial input)
3. **SUB agents** must reference a subgraph with matching `sub_` prefix
4. **Prompt templates** use `{field}` placeholders matching input names
5. **LLM agent outputs** should request JSON format for structured data
6. **PGM agents** use `state` dict for read/write, set `__result__` for output
7. **Agent JSON must NOT contain `id` field** - filename is the ID
8. **Agent JSON must contain `persistence`** - even if empty `{}`
9. **Agent JSON must contain `created_at`** - ISO format timestamp
10. **LLM agents must contain `tools`** - empty array `[]` if no tools
