#!/usr/bin/env python3
"""
NeuraGraph AutoGen - LLM-powered workflow generator.

Usage:
    # Interactive mode
    python autogen.py

    # One-shot mode
    python autogen.py --requirement "Extract chemical and disease entities from biomedical text"

    # With specific LLM
    python autogen.py --llm kimi-k2.5 --requirement "Summarize research papers"

    # Dry run (generate configs without executing)
    python autogen.py --requirement "..." --dry-run

    # Execute after generation
    python autogen.py --requirement "..." --input '{"text":"Aspirin treats headache"}'
"""

import argparse
import json
import os
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# ── Configuration ──
META_DIR = Path(__file__).parent / "meta"
SKILL_MD = Path(__file__).parent / "SKILL.md"

# ── LLM Client ──
class LLMClient:
    """Simple LLM client for autogen."""

    def __init__(self, llm_config: Dict):
        self.cfg = llm_config
        self.type = llm_config.get("type", "openai")
        self.base_url = llm_config.get("base_url", "http://localhost:11434")
        self.model = llm_config["model"]
        self.api_key = llm_config.get("api_key", "")
        self.temperature = llm_config.get("temperature", 0.7)
        self.max_tokens = llm_config.get("max_tokens", 4000)
        self.timeout = llm_config.get("timeout", 60)

    def chat(self, system: str, user: str) -> str:
        if self.type == "ollama":
            return self._call_ollama(system, user)
        else:
            return self._call_openai(system, user)

    def _call_ollama(self, system: str, user: str) -> str:
        resp = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")

    def _call_openai(self, system: str, user: str) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


# ── Config Manager ──
class ConfigManager:
    """Read/write meta JSON configs."""

    def __init__(self, meta_dir: Path = META_DIR):
        self.meta = meta_dir
        for sub in ("agents", "graphs", "llms", "tools", "datasets"):
            (self.meta / sub).mkdir(parents=True, exist_ok=True)

    def load_all(self, subdir: str) -> Dict[str, Dict]:
        result = {}
        d = self.meta / subdir
        if d.exists():
            for f in d.glob("*.json"):
                cfg = json.loads(f.read_text())
                cfg["id"] = f.stem
                result[f.stem] = cfg
        return result

    def save(self, subdir: str, cfg: Dict) -> Path:
        cid = cfg["id"]
        fpath = self.meta / subdir / f"{cid}.json"
        fpath.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
        return fpath

    def exists(self, subdir: str, cid: str) -> bool:
        return (self.meta / subdir / f"{cid}.json").exists()


# ── AutoGen Engine ──
class AutoGen:
    def __init__(self, llm_config: Dict, verbose: bool = False):
        self.llm = LLMClient(llm_config)
        self.cm = ConfigManager()
        self.verbose = verbose
        self._load_skill()

    def _load_skill(self):
        """Load SKILL.md as system context."""
        self.skill_context = ""
        if SKILL_MD.exists():
            self.skill_context = SKILL_MD.read_text()
        else:
            self.skill_context = self._default_skill()

    def _default_skill(self) -> str:
        return textwrap.dedent("""
        You are a NeuraGraph workflow designer. You generate JSON configs for:
        - agents (LLM/PGM/SUB types)
        - graphs (workflows: nodes + edges)
        - llms (provider configs)
        - tools (Python code functions)

        Rules:
        1. Graph edges must form a DAG from START to END
        2. Agent inputs must match upstream agent outputs or initial input
        3. SUB agents iterate over a list through a subgraph
        4. Use {field} placeholders in prompts matching input names
        5. PGM agents use `state` dict and set `__result__`

        Agent types:
        - LLM: has model, prompt_template (system, human), tools (optional)
        - PGM: has process (Python code using state dict)
        - SUB: has idx (loop vars), iterates over subgraph

        Output format: Always respond with valid JSON only. No markdown.
        """)

    # ── Phase 1: Analyze Requirement ──
    def analyze(self, requirement: str) -> Dict[str, Any]:
        """Analyze requirement and determine what components are needed."""
        system = textwrap.dedent(f"""\
        You are a workflow architect. Analyze the user's requirement and determine what components are needed.

        {self.skill_context}

        Existing LLM configs (reuse if possible):
        {json.dumps(list(self.cm.load_all("llms").keys()), indent=2)}

        Existing tools (reuse if possible):
        {json.dumps({k: v.get("description", "") for k, v in self.cm.load_all("tools").items()}, indent=2)}

        Respond with JSON only (no markdown):
        {{
          "analysis": "brief analysis of what needs to be built",
          "needs_new_llm": true/false,
          "llm_config": {{ "id": "...", "type": "openai|ollama", "model": "...", "base_url": "..." }} or null,
          "needs_new_tools": [{{ "id": "...", "description": "what it does", "parameters": {{...}} }}] or [],
          "agent_plan": [
            {{
              "id": "agent_id",
              "type": "LLM|PGM|SUB",
              "purpose": "what this agent does",
              "inputs": ["field1", "field2"],
              "outputs": {{ "name": "output_field", "type": "str|list|dict" }}
            }}
          ],
          "graph_plan": {{
            "id": "graph_id",
            "name": "human readable name",
            "nodes": ["START", "agent1", "agent2", "END"],
            "edges": [["START", "agent1"], ["agent1", "agent2"], ["agent2", "END"]]
          }}
        }}
        """)

        print("\n[Phase 1] Analyzing requirement...")
        response = self.llm.chat(system, f"Requirement: {requirement}")

        try:
            plan = json.loads(response)
        except json.JSONDecodeError:
            # Try extracting JSON from markdown
            import re
            m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
            if m:
                plan = json.loads(m.group(1))
            else:
                raise ValueError(f"Cannot parse analysis response: {response[:200]}")

        if self.verbose:
            print(f"  Analysis: {plan.get('analysis', 'N/A')}")
            print(f"  Agents: {[a['id'] for a in plan.get('agent_plan', [])]}")
            print(f"  Graph: {plan.get('graph_plan', {}).get('id', 'N/A')}")

        return plan

    # ── Phase 2: Generate Components ──
    def generate(self, plan: Dict) -> List[Path]:
        """Generate all configuration files from the plan."""
        generated = []

        # 2a. Generate LLM config if needed
        if plan.get("needs_new_llm") and plan.get("llm_config"):
            llm_cfg = plan["llm_config"]
            llm_cfg.setdefault("temperature", 0.7)
            llm_cfg.setdefault("max_tokens", 1000)
            llm_cfg.setdefault("api_key", "")
            fpath = self.cm.save("llms", llm_cfg)
            generated.append(fpath)
            print(f"  Generated LLM: {llm_cfg['id']} -> {fpath}")

        # 2b. Generate tools if needed
        for tool_plan in plan.get("needs_new_tools", []):
            tool_cfg = self._generate_tool(tool_plan)
            fpath = self.cm.save("tools", tool_cfg)
            generated.append(fpath)
            print(f"  Generated Tool: {tool_cfg['id']} -> {fpath}")

        # 2c. Generate agents
        llm_id = (plan.get("llm_config") or {}).get("id", self._pick_default_llm())
        for agent_plan in plan.get("agent_plan", []):
            agent_cfg = self._generate_agent(agent_plan, llm_id)
            fpath = self.cm.save("agents", agent_cfg)
            generated.append(fpath)
            print(f"  Generated Agent: {agent_cfg['id']} -> {fpath}")

        # 2d. Generate graph
        graph_cfg = plan.get("graph_plan", {})
        if graph_cfg:
            graph_cfg.setdefault("description", f"Workflow for {graph_cfg.get('name', graph_cfg['id'])}")
            fpath = self.cm.save("graphs", graph_cfg)
            generated.append(fpath)
            print(f"  Generated Graph: {graph_cfg['id']} -> {fpath}")

        return generated

    def _pick_default_llm(self) -> str:
        llms = self.cm.load_all("llms")
        if llms:
            return list(llms.keys())[0]
        return "kimi-k2.5"

    def _generate_agent(self, plan: Dict, llm_id: str) -> Dict:
        """Use LLM to generate detailed agent config."""
        agent_type = plan["type"]

        system = textwrap.dedent(f"""\
        Generate a NeuraGraph agent configuration as JSON.

        Agent plan:
        {json.dumps(plan, indent=2)}

        LLM to use: {llm_id}

        For LLM agents, generate a complete prompt_template with system and human prompts.
        Use {{field}} placeholders matching the input names.
        The human prompt should clearly instruct the LLM what to do.

        For PGM agents, generate Python code that:
        - Reads from `state` dict
        - Sets `__result__` for output
        - Is self-contained

        For SUB agents, the idx field should match the iteration variable.

        Respond with valid JSON only (no markdown).
        """)

        response = self.llm.chat(system, f"Generate agent config for: {plan['id']}")

        try:
            cfg = json.loads(response)
        except json.JSONDecodeError:
            import re
            m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
            if m:
                cfg = json.loads(m.group(1))
            else:
                # Build minimal config from plan
                cfg = {
                    "id": plan["id"],
                    "name": plan.get("purpose", plan["id"]),
                    "type": agent_type,
                    "inputs": plan.get("inputs", []),
                    "outputs": plan.get("outputs", {"name": "result", "type": "str"}),
                }
                if agent_type == "LLM":
                    cfg["model"] = llm_id
                    cfg["prompt_template"] = {
                        "description": plan.get("purpose", ""),
                        "system": f"You are a helpful assistant for {plan['id']}.",
                        "human": "Process the following:\n" + "\n".join(f"{inp}: {{{inp}}}" for inp in plan.get("inputs", [])),
                    }
                elif agent_type == "PGM":
                    cfg["process"] = f"# {plan.get('purpose', '')}\n__result__ = state.get('{plan.get('inputs', ['input'])[0]}', '')"

        # Ensure required fields
        cfg.setdefault("id", plan["id"])
        cfg.setdefault("name", plan.get("purpose", plan["id"]))
        cfg.setdefault("inputs", plan.get("inputs", []))
        cfg.setdefault("outputs", plan.get("outputs", {"name": "result", "type": "str"}))

        if agent_type == "LLM" and "model" not in cfg:
            cfg["model"] = llm_id

        return cfg

    def _generate_tool(self, plan: Dict) -> Dict:
        """Use LLM to generate tool code."""
        system = textwrap.dedent(f"""\
        Generate a NeuraGraph tool configuration with Python code.

        Tool plan:
        {json.dumps(plan, indent=2)}

        The code must define a `func` function with the specified parameters.
        Set `__result__` to the return value.

        Respond with valid JSON only:
        {{
          "id": "tool_id",
          "name": "Tool Name",
          "description": "...",
          "parameters": {{ "type": "object", "properties": {{...}}, "required": [...] }},
          "code": "def func(param1: str, param2: str) -> dict:\n    result = ...\n    __result__ = result"
        }}
        """)

        response = self.llm.chat(system, f"Generate tool: {plan['id']}")

        try:
            cfg = json.loads(response)
        except json.JSONDecodeError:
            import re
            m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
            if m:
                cfg = json.loads(m.group(1))
            else:
                cfg = {
                    "id": plan["id"],
                    "name": plan["id"].replace("_", " ").title(),
                    "description": plan.get("description", ""),
                    "parameters": plan.get("parameters", {"type": "object", "properties": {}, "required": []}),
                    "code": f"def func(**kwargs):\n    __result__ = kwargs",
                }

        cfg.setdefault("id", plan["id"])
        return cfg

    # ── Phase 3: Validate ──
    def validate(self, plan: Dict) -> List[str]:
        """Validate generated configs. Returns list of errors (empty if valid)."""
        errors = []

        # Check graph connectivity
        graph = plan.get("graph_plan", {})
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        if "START" not in nodes:
            errors.append("Graph missing START node")
        if "END" not in nodes:
            errors.append("Graph missing END node")

        # Check all edges reference valid nodes
        node_set = set(nodes)
        for i, edge in enumerate(edges):
            if len(edge) < 2:
                errors.append(f"Edge {i} is malformed: {edge}")
                continue
            if edge[0] not in node_set:
                errors.append(f"Edge {i}: source '{edge[0]}' not in nodes")
            if edge[1] not in node_set:
                errors.append(f"Edge {i}: target '{edge[1]}' not in nodes")

        # Check for disconnected nodes
        sources = set(e[0] for e in edges if len(e) >= 2)
        targets = set(e[1] for e in edges if len(e) >= 2)
        for node in nodes:
            if node in ("START", "END"):
                continue
            if node not in sources and node not in targets:
                errors.append(f"Node '{node}' is disconnected")

        # Check agent configs exist
        for agent_plan in plan.get("agent_plan", []):
            aid = agent_plan["id"]
            if not self.cm.exists("agents", aid):
                errors.append(f"Agent config '{aid}' not saved to meta/agents/")

        # Check LLM config exists
        llm_id = (plan.get("llm_config") or {}).get("id", "")
        if llm_id and not self.cm.exists("llms", llm_id):
            # Check if it's an existing LLM
            existing = self.cm.load_all("llms")
            if llm_id not in existing:
                errors.append(f"LLM config '{llm_id}' not found")

        if errors:
            print(f"  Validation: {len(errors)} error(s)")
            for e in errors:
                print(f"    - {e}")
        else:
            print("  Validation: OK")

        return errors

    # ── Phase 4: Execute ──
    def execute(self, graph_id: str, inputs: Dict) -> Any:
        """Execute the workflow."""
        from run_workflow import STORE, GraphRunner

        # Reload configs
        STORE.load(META_DIR)

        runner = GraphRunner(graph_id, verbose=self.verbose)
        return runner.run(inputs)

    # ── Full Pipeline ──
    def run(self, requirement: str, inputs: Optional[Dict] = None, dry_run: bool = False) -> Dict:
        """Full pipeline: analyze -> generate -> validate -> execute."""
        print(f"\n{'='*60}")
        print(f" NeuraGraph AutoGen")
        print(f"{'='*60}")
        print(f" Requirement: {requirement}")

        # Phase 1: Analyze
        plan = self.analyze(requirement)

        # Phase 2: Generate
        print("\n[Phase 2] Generating configurations...")
        generated = self.generate(plan)

        if not generated:
            print("  Nothing to generate")
            return {"status": "no_changes"}

        # Phase 3: Validate
        print("\n[Phase 3] Validating...")
        errors = self.validate(plan)
        if errors:
            print(f"\n  Found {len(errors)} validation errors. Fix and retry.")
            return {"status": "validation_failed", "errors": errors}

        # Phase 4: Execute (unless dry-run)
        graph_id = plan.get("graph_plan", {}).get("id", "")
        if not dry_run and inputs is not None:
            print(f"\n[Phase 4] Executing workflow '{graph_id}'...")
            result = self.execute(graph_id, inputs)
            return {"status": "success", "plan": plan, "generated": [str(p) for p in generated], "result": result}

        print(f"\n  Configs generated. To execute:")
        print(f"  python run_workflow.py --graph {graph_id} --input '{{...}}'")
        return {"status": "generated", "plan": plan, "generated": [str(p) for p in generated]}


def main():
    parser = argparse.ArgumentParser(description="NeuraGraph AutoGen - Generate workflows from natural language")
    parser.add_argument("--requirement", "-r", help="Natural language requirement")
    parser.add_argument("--llm", default="kimi-k2.5", help="LLM config ID to use for generation")
    parser.add_argument("--input", "-i", help="JSON input for workflow execution")
    parser.add_argument("--dry-run", action="store_true", help="Generate configs without executing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--meta-dir", default=str(META_DIR), help="Meta directory path")

    args = parser.parse_args()

    # Set meta dir
    meta_dir = Path(args.meta_dir)

    # Load LLM config
    cm = ConfigManager(META_DIR)
    llms = cm.load_all("llms")

    if not llms:
        print("[ERROR] No LLM configs found. Create one first:")
        print(f"  echo '{{\"id\":\"kimi-k2.5\",\"type\":\"openai\",\"model\":\"kimi-k2.5\",\"base_url\":\"https://api.moonshot.cn/v1\",\"api_key\":\"YOUR_KEY\",\"temperature\":0.7}}' > {META_DIR}/llms/kimi-k2.5.json")
        sys.exit(1)

    llm_config = llms.get(args.llm)
    if not llm_config:
        print(f"[ERROR] LLM '{args.llm}' not found. Available: {list(llms.keys())}")
        sys.exit(1)

    # Interactive or one-shot
    if args.requirement:
        requirement = args.requirement
    else:
        print("\nNeuraGraph AutoGen - Describe what you want to build:")
        print("Examples:")
        print('  "Extract chemical and disease entities from biomedical text"')
        print('  "Summarize a research paper given its text"')
        print('  "Classify sentiment of product reviews"')
        print('  "Translate English text to Chinese"')
        requirement = input("\n> ").strip()

    if not requirement:
        print("[ERROR] No requirement provided")
        sys.exit(1)

    # Parse input if provided
    inputs = None
    if args.input:
        try:
            inputs = json.loads(args.input)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Invalid input JSON: {e}")
            sys.exit(1)

    # Run
    autogen = AutoGen(llm_config, verbose=args.verbose)
    autogen.cm = ConfigManager(meta_dir)
    result = autogen.run(requirement, inputs=inputs, dry_run=args.dry_run)

    # Print result
    if result.get("status") == "success":
        print(f"\n{'='*60}")
        print(" RESULT:")
        print(f"{'='*60}")
        final_state = result.get("result", {})
        for k, v in final_state.items():
            print(f"\n  {k}:")
            if isinstance(v, (dict, list)):
                print(f"  {json.dumps(v, indent=4, ensure_ascii=False)[:2000]}")
            else:
                print(f"  {str(v)[:2000]}")


if __name__ == "__main__":
    main()
