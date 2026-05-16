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

## Agent Types

| Type | Purpose | Key Fields |
|------|---------|------------|
| LLM | Call language model | model, prompt_template (system, human), tools |
| PGM | Python code execution | process (Python code using `state` dict) |
| SUB | Iterate subgraph over list | idx (loop variables), inputs (iterable) |

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
  "code": "def func(query: str) -> dict:\n    ...\n    return result"
}
```

## Prompt Template Format

Use `{field_name}` placeholders that are replaced from state:
```json
{
  "description": "Extract entities",
  "system": "You are an NER expert.",
  "human": "Text: {text}\nLabels: {labels}\nExtract entities as JSON."
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
