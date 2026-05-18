#!/usr/bin/env python3
"""
NeuraGraph Terminal Runner - Execute workflows via LangGraph.

Usage:
    python run_workflow.py --graph bio_ner_graph --input '{"text":"Your text here","labels":"Chemical,Disease"}'
    python run_workflow.py --graph bio_ner_graph --dataset /path/to/dataset.json
    python run_workflow.py --graph sub_ner --input '{"sentences":["s1","s2"],"labels":"Chemical"}' --verbose
"""

import argparse
import json
import os
import sys
import re
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

# LangGraph - optional, we use our own DAG executor
try:
    from langgraph.graph import StateGraph, START, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

# DAG executor - works with or without LangGraph
from collections import deque

try:
    import requests
except ImportError:
    print("[ERROR] requests not installed. Run: pip install requests")
    sys.exit(1)

# ── Configuration ──
DEFAULT_META_DIR = Path(__file__).parent / "meta"
RESULT_DIR = Path(__file__).parent / "result"

class ConfigStore:
    """Holds all loaded configurations."""
    def __init__(self):
        self.llms: Dict[str, Dict] = {}
        self.agents: Dict[str, Dict] = {}
        self.graphs: Dict[str, Dict] = {}
        self.tools: Dict[str, Dict] = {}

    def load(self, meta_dir: Path):
        """Load all JSON configs from meta directory."""
        # Load LLMs
        llm_dir = meta_dir / "llms"
        if llm_dir.exists():
            for f in llm_dir.glob("*.json"):
                cfg = json.loads(f.read_text(encoding='utf-8'))
                cfg["id"] = f.stem
                self.llms[f.stem] = cfg
        print(f"  Loaded {len(self.llms)} LLM configs")

        # Load Agents
        agent_dir = meta_dir / "agents"
        if agent_dir.exists():
            for f in agent_dir.glob("*.json"):
                cfg = json.loads(f.read_text(encoding='utf-8'))
                cfg["id"] = f.stem
                self.agents[f.stem] = cfg
        print(f"  Loaded {len(self.agents)} agents")

        # Load Graphs
        graph_dir = meta_dir / "graphs"
        if graph_dir.exists():
            for f in graph_dir.glob("*.json"):
                cfg = json.loads(f.read_text(encoding='utf-8'))
                cfg["id"] = f.stem
                self.graphs[f.stem] = cfg
        print(f"  Loaded {len(self.graphs)} graphs")

        # Load Tools
        tool_dir = meta_dir / "tools"
        if tool_dir.exists():
            for f in tool_dir.glob("*.json"):
                cfg = json.loads(f.read_text(encoding='utf-8'))
                cfg["id"] = f.stem
                self.tools[f.stem] = cfg
        print(f"  Loaded {len(self.tools)} tools")


# Global config store
STORE = ConfigStore()

# Also update reference at module level for autogen
META_DIR_FOR_RUN = DEFAULT_META_DIR


# ── LLM Client ──
class LLMClient:
    """Call LLM APIs (Ollama, OpenAI-compatible)."""

    def __init__(self, llm_config: Dict):
        self.cfg = llm_config
        self.type = llm_config.get("type", "ollama")
        self.base_url = llm_config.get("base_url", "http://localhost:11434")
        self.model = llm_config["model"]
        self.api_key = llm_config.get("api_key", "")
        self.temperature = llm_config.get("temperature", 0.7)
        self.max_tokens = llm_config.get("max_tokens", 1000)
        self.timeout = llm_config.get("timeout", 30)
        self.max_retries = llm_config.get("max_retries", 3)

    def chat(self, system: str, human: str) -> str:
        """Send chat completion request."""
        if self.type == "ollama":
            return self._call_ollama(system, human)
        else:
            return self._call_openai_compatible(system, human)

    def _call_ollama(self, system: str, human: str) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": human},
            ],
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }
        for attempt in range(self.max_retries):
            try:
                resp = requests.post(url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                return data.get("message", {}).get("content", "")
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(f"Ollama call failed after {self.max_retries} retries: {e}")
        return ""

    def _call_openai_compatible(self, system: str, human: str) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": human},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        for attempt in range(self.max_retries):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(f"LLM call failed after {self.max_retries} retries: {e}")
        return ""


# ── Tool Executor ──
class ToolExecutor:
    """Execute tool code."""

    def __init__(self, tool_registry: Dict[str, Dict]):
        self.tools = tool_registry

    def run(self, tool_id: str, **kwargs) -> Any:
        tool = self.tools.get(tool_id)
        if not tool:
            raise ValueError(f"Tool '{tool_id}' not found")
        code = tool.get("code", "")
        if not code:
            raise ValueError(f"Tool '{tool_id}' has no code")

        # Build execution namespace
        namespace = {
            "__result__": None,
            "get_plugin": lambda name: None,  # Placeholder
            **kwargs,
        }
        exec(code, namespace)
        return namespace.get("__result__") or namespace.get("func", lambda **_: None)(**kwargs)


# ── Agent Executor ──
class AgentRunner:
    """Execute individual agents."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.tool_executor = ToolExecutor(STORE.tools)
        self._llm_clients: Dict[str, LLMClient] = {}

    def _get_llm_client(self, llm_id: str) -> LLMClient:
        if llm_id not in self._llm_clients:
            cfg = STORE.llms.get(llm_id)
            if not cfg:
                raise ValueError(f"LLM config '{llm_id}' not found. Available: {list(STORE.llms.keys())}")
            self._llm_clients[llm_id] = LLMClient(cfg)
        return self._llm_clients[llm_id]

    def run(self, agent_id: str, state: Dict[str, Any]) -> Any:
        """Execute a single agent with given state."""
        agent = STORE.agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent '{agent_id}' not found")

        agent_type = agent.get("type", "LLM")
        name = agent.get("name", agent_id)

        print(f"    ┌─ [{agent_type}] {name} ({agent_id})")

        if agent_type == "LLM":
            return self._run_llm(agent, state)
        elif agent_type == "PGM":
            return self._run_pgm(agent, state)
        elif agent_type == "SUB":
            return self._run_sub(agent, state)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")

    def _run_llm(self, agent: Dict, state: Dict) -> Any:
        """Execute LLM agent."""
        # Build prompt
        pt = agent.get("prompt_template", {})
        system = pt.get("system", "")
        human_template = pt.get("human", "")

        # Format human prompt with state variables
        try:
            human = human_template.format(**state)
        except KeyError as e:
            # Try with missing keys as empty strings
            human = human_template
            for key in agent.get("inputs", []):
                val = state.get(key, "")
                human = human.replace(f"{{{key}}}", str(val))

        if self.verbose:
            print(f"    │  System: {system[:100]}...")
            print(f"    │  Human: {human[:200]}...")

        # Call LLM
        llm_id = agent.get("model", "")
        client = self._get_llm_client(llm_id)
        response = client.chat(system, human)

        if self.verbose:
            print(f"    │  Response: {response[:300]}...")

        # Try parse as JSON if output type is dict/list
        output_type = agent.get("outputs", {}).get("type", "str")
        if output_type in ("dict", "list"):
            return self._parse_json_response(response)
        return response

    def _parse_json_response(self, text: str) -> Any:
        """Parse JSON from LLM response, handling various formats."""
        import ast

        # 1. Extract from markdown code blocks
        for pattern in [r'```json\s*\n?(.*?)\n?```', r'```\s*\n?(.*?)\n?```']:
            m = re.search(pattern, text, re.DOTALL)
            if m:
                text = m.group(1)
                break

        # 2. Try standard JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 3. Try Python literal eval (handles single quotes)
        try:
            return ast.literal_eval(text.strip())
        except (SyntaxError, ValueError):
            pass

        # 4. Try extracting JSON object from surrounding text
        m = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                try:
                    return ast.literal_eval(m.group(0))
                except:
                    pass

        # 5. Return raw
        if self.verbose:
            print(f"    │  WARN: Could not parse JSON, returning raw")
        return text

    def _run_pgm(self, agent: Dict, state: Dict) -> Any:
        """Execute PGM (programmatic) agent."""
        process_code = agent.get("process", "")
        if not process_code:
            raise ValueError(f"PGM agent '{agent['id']}' has no process code")

        # Build safe execution environment with plugins
        def _utf8_open(file, mode='r', *args, **kwargs):
            """Open file with UTF-8 encoding by default."""
            if 'b' not in mode and 'encoding' not in kwargs:
                kwargs['encoding'] = 'utf-8'
            return open(file, mode, *args, **kwargs)

        safe_builtins = {
            'range': range, 'len': len, 'str': str, 'int': int,
            'float': float, 'bool': bool, 'list': list, 'dict': dict,
            'set': set, 'tuple': tuple, 'enumerate': enumerate,
            'zip': zip, 'max': max, 'min': min, 'sum': sum,
            'abs': abs, 'round': round, 'sorted': sorted,
            'isinstance': isinstance, 'hasattr': hasattr, 'getattr': getattr,
            'type': type, 'print': print, 'json': json, 're': re,
            'open': _utf8_open, 'Path': Path,
        }

        # Plugin loader
        _plugins_cache = {}
        def get_plugin(name: str):
            if name not in _plugins_cache:
                if name == "tag":
                    # Flair skipped - network not available
                    print("    │  [WARN] Flair NER plugin skipped (network unavailable)")
                    _plugins_cache[name] = None
                elif name == "exec_globals":
                    _plugins_cache[name] = {"__builtins__": safe_builtins}
                elif name == "InMemorySaver":
                    try:
                        from langgraph.checkpoint.memory import InMemorySaver
                        _plugins_cache[name] = InMemorySaver()
                    except:
                        _plugins_cache[name] = None
                else:
                    _plugins_cache[name] = None
            return _plugins_cache[name]

        # Use a mutable container so exec can modify __result__
        result_container = {"value": None}
        namespace = {
            "__builtins__": safe_builtins,
            "state": state,
            "__result__": None,
            "get_plugin": get_plugin,
            "json": json,
            "re": re,
        }

        # Execute in namespace; assignments update locals which exec returns
        locals_dict = {}
        exec(process_code, namespace, locals_dict)
        # Check both locals and namespace for __result__
        result = locals_dict.get("__result__") or namespace.get("__result__")

        if self.verbose:
            print(f"    │  Result: {str(result)[:200]}")

        return result

    def _run_sub(self, agent: Dict, state: Dict) -> Any:
        """Execute SUB (subgraph iteration) agent."""
        agent_id = agent["id"]
        inputs = agent.get("inputs", [])
        idx_names = agent.get("idx", [])
        subgraph_id = agent_id  # sub_xxx references graph sub_xxx

        if not inputs:
            raise ValueError(f"SUB agent '{agent_id}' has no inputs")

        iter_input = inputs[0]  # First input is the iterable
        iterable = state.get(iter_input, [])
        if not isinstance(iterable, list):
            raise ValueError(f"SUB agent '{agent_id}' input '{iter_input}' must be a list, got {type(iterable)}")

        print(f"    │  Iterating {len(iterable)} items over subgraph '{subgraph_id}'")

        # Load subgraph
        subgraph = STORE.graphs.get(subgraph_id)
        if not subgraph:
            raise ValueError(f"Subgraph '{subgraph_id}' not found. Available: {list(STORE.graphs.keys())}")

        # Build and execute subgraph for each item
        all_results = []
        for i, item in enumerate(iterable):
            print(f"    │  ┌─ Iteration {i+1}/{len(iterable)}")

            # Create iteration state
            iter_state = dict(state)
            if idx_names:
                iter_state[idx_names[0]] = item
            else:
                iter_state[iter_input] = item

            # Execute subgraph nodes directly (avoid double printing)
            result = self._execute_subgraph(subgraph, iter_state)
            all_results.append(result)
            print(f"    │  └─ Result: {str(result)[:150]}")

        # Merge results
        output_type = agent.get("outputs", {}).get("type", "list")
        if output_type == "dict":
            merged = {}
            for r in all_results:
                if isinstance(r, dict):
                    for k, v in r.items():
                        if k not in merged: merged[k] = []
                        merged[k].append(v)
            return merged
        return all_results

    def _execute_subgraph(self, subgraph_def: Dict, state: Dict) -> Any:
        """Execute a subgraph definition directly without GraphRunner overhead."""
        nodes = [n for n in subgraph_def.get("nodes", []) if n not in ("START", "END")]
        edges = subgraph_def.get("edges", [])

        # Build edge map
        node_order = []
        current = "START"
        visited = set()
        while current != "END" and current not in visited:
            visited.add(current)
            for edge in edges:
                if len(edge) >= 2 and edge[0] == current:
                    next_node = edge[1]
                    if next_node != "END":
                        node_order.append(next_node)
                    current = next_node
                    break
            else:
                break

        # Deduplicate while preserving order
        seen = set()
        ordered = []
        for n in node_order:
            if n not in seen:
                seen.add(n)
                ordered.append(n)

        # Execute nodes in order
        current_state = dict(state)
        for node_id in ordered:
            result = self.run(node_id, current_state)
            agent = STORE.agents.get(node_id, {})
            out_name = agent.get("outputs", {}).get("name")
            if out_name and result is not None:
                current_state[out_name] = result

        return current_state


# ── Graph Runner ──
class GraphRunner:
    """Compile and execute a LangGraph workflow."""

    def __init__(self, graph_id: str, verbose: bool = False):
        self.graph_id = graph_id
        self.verbose = verbose
        self.graph_def = STORE.graphs.get(graph_id)
        if not self.graph_def:
            raise ValueError(f"Graph '{graph_id}' not found. Available: {list(STORE.graphs.keys())}")
        self.agent_runner = AgentRunner(verbose=verbose)

    def compile(self) -> Callable:
        """Compile graph into a DAG executor function."""
        nodes = self.graph_def.get("nodes", [])
        edges = self.graph_def.get("edges", [])

        # Build adjacency list and execution order (topological sort)
        adj: Dict[str, List[str]] = {}
        in_degree: Dict[str, int] = {}

        for n in nodes:
            if n not in ("START", "END"):
                adj[n] = []
                in_degree[n] = 0

        for edge in edges:
            if len(edge) >= 2:
                src, tgt = edge[0], edge[1]
                if src == "START" or tgt == "END":
                    continue
                adj.setdefault(src, []).append(tgt)
                in_degree[tgt] = in_degree.get(tgt, 0) + 1

        # Topological sort
        from collections import deque
        queue = deque([n for n in in_degree if in_degree[n] == 0])
        execution_order = []
        while queue:
            node = queue.popleft()
            execution_order.append(node)
            for neighbor in adj.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(execution_order) != len([n for n in nodes if n not in ("START", "END")]):
            unexecuted = [n for n in nodes if n not in ("START", "END") and n not in execution_order]
            raise ValueError(f"Cycle detected or disconnected nodes: {unexecuted}")

        # Build executor
        def executor(state: Dict) -> Dict:
            current_state = dict(state)
            for node_id in execution_order:
                result = self.agent_runner.run(node_id, current_state)
                agent = STORE.agents.get(node_id, {})
                output_name = agent.get("outputs", {}).get("name")
                if output_name and result is not None:
                    current_state[output_name] = result
            return current_state

        return executor

    def run(self, inputs: Dict[str, Any]) -> Any:
        """Execute the workflow with given inputs."""
        print(f"\n{'='*60}")
        print(f" Executing: {self.graph_def.get('name', self.graph_id)} ({self.graph_id})")
        print(f"{'='*60}")

        initial_state = dict(inputs)
        executor = self.compile()

        if self.verbose:
            print(f"  Initial state: {json.dumps({k: str(v)[:100] for k, v in initial_state.items()}, indent=4)}")

        print(f"  Running {len([n for n in self.graph_def.get('nodes',[]) if n not in ('START','END')])} agents...")
        final_state = executor(initial_state)
        print(f"  Done.")

        return final_state


# ── CLI ──
def main():
    parser = argparse.ArgumentParser(
        description="NeuraGraph Terminal Runner - Execute workflows via LangGraph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Examples:
          # List all available graphs
          python run_workflow.py --list

          # Execute a graph with inline input
          python run_workflow.py --graph bio_ner_graph --input '{"text":"Aspirin treats headache.","labels":"Chemical,Disease"}'

          # Execute with dataset file
          python run_workflow.py --graph bio_ner_graph --dataset dataset.json

          # Verbose mode
          python run_workflow.py --graph bio_ner_graph --input '{...}' --verbose

          # Save result
          python run_workflow.py --graph bio_ner_graph --input '{...}' --output result.json
        """),
    )
    parser.add_argument("--graph", "-g", help="Graph ID to execute")
    parser.add_argument("--input", "-i", help="JSON input string")
    parser.add_argument("--dataset", "-d", help="Path to dataset JSON file")
    parser.add_argument("--output", "-o", help="Save result to file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--list", "-l", action="store_true", help="List available graphs")
    parser.add_argument("--list-agents", action="store_true", help="List available agents")
    parser.add_argument("--list-llms", action="store_true", help="List available LLM configs")
    parser.add_argument("--meta-dir", default=str(DEFAULT_META_DIR), help="Path to meta directory")

    args = parser.parse_args()

    # Set meta dir
    meta_dir = Path(args.meta_dir)

    # Load configs
    print("Loading configurations...")
    STORE.load(meta_dir)

    # List mode
    if args.list:
        print("\nAvailable Graphs:")
        for gid, g in sorted(STORE.graphs.items()):
            nodes = ", ".join(n for n in g.get("nodes", []) if n not in ("START", "END"))
            print(f"  {gid:30s} {g.get('name', ''):20s} nodes: [{nodes}]")
        return

    if args.list_agents:
        print("\nAvailable Agents:")
        for aid, a in sorted(STORE.agents.items()):
            print(f"  {aid:30s} [{a.get('type', '?'):4s}] {a.get('name', '')}")
        return

    if args.list_llms:
        print("\nAvailable LLM Configs:")
        for lid, l in sorted(STORE.llms.items()):
            print(f"  {lid:30s} [{l.get('type', '?'):8s}] {l.get('model', '')} @ {l.get('base_url', 'N/A')}")
        return

    # Validate args
    if not args.graph:
        parser.print_help()
        sys.exit(1)

    # Build inputs
    inputs = {}
    if args.input:
        try:
            inputs = json.loads(args.input)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Invalid JSON input: {e}")
            sys.exit(1)
    elif args.dataset:
        try:
            inputs = json.loads(Path(args.dataset).read_text(encoding='utf-8'))
        except Exception as e:
            print(f"[ERROR] Cannot read dataset: {e}")
            sys.exit(1)
    else:
        print("[WARN] No input provided, running with empty state")

    # Execute
    try:
        runner = GraphRunner(args.graph, verbose=args.verbose)
        result = runner.run(inputs)

        # Print result
        print(f"\n{'='*60}")
        print(" RESULT:")
        print(f"{'='*60}")

        # Pretty print relevant outputs
        graph_def = STORE.graphs.get(args.graph, {})
        for node_id in graph_def.get("nodes", []):
            agent = STORE.agents.get(node_id, {})
            out_name = agent.get("outputs", {}).get("name")
            if out_name and out_name in result:
                val = result[out_name]
                print(f"\n  [{node_id}] -> {out_name}:")
                if isinstance(val, (dict, list)):
                    print(f"  {json.dumps(val, indent=4, ensure_ascii=False)[:2000]}")
                else:
                    print(f"  {str(val)[:2000]}")

        # Save if requested
        if args.output:
            RESULT_DIR.mkdir(parents=True, exist_ok=True)
            out_path = RESULT_DIR / args.output
            out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
            print(f"\n  Saved to: {out_path}")

    except Exception as e:
        print(f"\n[ERROR] Execution failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
