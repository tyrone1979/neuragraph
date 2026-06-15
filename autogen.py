#!/usr/bin/env python3
"""
NeuraGraph AutoGen - LLM-powered workflow generator.

Usage:
    # Interactive mode
    python autogen.py

    # One-shot mode
    python autogen.py --requirement "Extract chemical and disease entities from biomedical text"

    # With specific LLM
    python autogen.py --llm deepseek --requirement "Summarize research papers"

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

import re

import requests

# ── Configuration ──
META_DIR = Path(__file__).parent / "meta"
SKILL_MD = Path(__file__).parent / "doc" / "AUTOGEN_SKILL.md"

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
        self.max_retries = llm_config.get("max_retries", 1)

    def chat(self, system: str, user: str) -> str:
        last_error = None
        for attempt in range(self.max_retries):
            try:
                if self.type == "ollama":
                    return self._call_ollama(system, user)
                else:
                    return self._call_openai(system, user)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait = 2 ** attempt
                    print(f"  LLM call failed (attempt {attempt + 1}/{self.max_retries}), retrying in {wait}s...")
                    import time
                    time.sleep(wait)
        raise last_error

    def chat_stream(self, system: str, user: str):
        """Yield text chunks as they arrive from the LLM."""
        if self.type == "ollama":
            yield from self._call_ollama_stream(system, user)
        else:
            yield from self._call_openai_stream(system, user)

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

    def _call_ollama_stream(self, system: str, user: str):
        resp = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": True,
                "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
            },
            timeout=self.timeout,
            stream=True,
        )
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line.decode("utf-8"))
                if chunk.get("done"):
                    break
                delta = chunk.get("message", {}).get("content", "")
                if delta:
                    yield delta
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

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

    def _call_openai_stream(self, system: str, user: str):
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
                "stream": True,
            },
            timeout=self.timeout,
            stream=True,
        )
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            line = line.decode("utf-8")
            if line.startswith("data: "):
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue


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
                cfg = json.loads(f.read_text(encoding='utf-8'))
                cfg["id"] = f.stem
                if subdir == "llms":
                    from service.meta.llm_secrets import resolve_llm_api_key

                    cfg = resolve_llm_api_key(cfg, f.stem)
                result[f.stem] = cfg
        return result

    def save(self, subdir: str, cfg: Dict) -> Path:
        cid = cfg["id"]
        fpath = self.meta / subdir / f"{cid}.json"
        fpath.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
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
            self.skill_context = SKILL_MD.read_text(encoding='utf-8')
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
        # Load existing agents for reuse
        existing_agents = self.cm.load_all("agents")
        existing_agent_info = {k: {"type": v.get("type"), "name": v.get("name"), "inputs": v.get("inputs"), "outputs": v.get("outputs")} 
                               for k, v in existing_agents.items()}

        system = textwrap.dedent(f"""\
        You are a workflow architect. Analyze the user's requirement and determine what components are needed.

        {self.skill_context}

        Existing LLM configs (reuse if possible):
        {json.dumps(list(self.cm.load_all("llms").keys()), indent=2)}

        Existing agents (REUSE if matches user's need - DO NOT recreate):
        {json.dumps(existing_agent_info, indent=2, ensure_ascii=False)}

        Existing tools (reuse if possible):
        {json.dumps({k: v.get("description", "") for k, v in self.cm.load_all("tools").items()}, indent=2)}

        Agent type rules:
        - LLM: Uses AI to process text, has prompt_template. Use for single text processing tasks.
        - PGM: Runs Python code, has "process" field with code. Use for data transformation/aggregation.
        - SUB: CRITICAL - Use ONLY for iterating over a LIST input. The SUB agent itself does NO processing;
          it calls an inner agent (usually LLM) for EACH item in the list.
          When using SUB: set "inner_agent" to the agent ID that handles one item.
          Example: input is a list of texts, inner_agent is "gene_protein_ner" which handles one text.

        Workflow structure for batch processing:
        1. SUB agent (type=SUB) with inner_agent=existing_agent_id -> iterates over list
        2. PGM agent -> aggregates SUB results into final JSON
        Graph: START -> sub_agent -> pgm_agent -> END

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
              "outputs": {{ "name": "output_field", "type": "str|list|dict" }},
              "inner_agent": "agent_to_call_per_item (only for SUB type)"
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
            agent_id = agent_plan["id"]
            
            # Skip if agent already exists (reuse existing agent)
            if self.cm.exists("agents", agent_id):
                print(f"  Reusing existing agent: {agent_id}")
                # For SUB agents using existing inner agents, just load and continue
                if agent_plan.get("type") == "SUB":
                    # Load existing to check if it's suitable
                    existing = self.cm.load_all("agents").get(agent_id, {})
                    if existing.get("type") == "SUB":
                        inner_agent = agent_plan.get("inner_agent", existing.get("inner_agent", "item"))
                        if not self.cm.exists("graphs", agent_id):
                            subgraph_cfg = {
                                "id": agent_id,
                                "name": f"Subgraph for {agent_id}",
                                "nodes": ["START", inner_agent, "END"],
                                "edges": [["START", inner_agent], [inner_agent, "END"]],
                                "description": f"Auto-generated subgraph for {agent_id}"
                            }
                            sg_path = self.cm.save("graphs", subgraph_cfg)
                            generated.append(sg_path)
                            print(f"  Generated Subgraph: {agent_id} -> {sg_path}")
                continue
            
            agent_cfg = self._generate_agent(agent_plan, llm_id)
            fpath = self.cm.save("agents", agent_cfg)
            generated.append(fpath)
            print(f"  Generated Agent: {agent_cfg['id']} -> {fpath}")

            # If agent is SUB type, auto-create its subgraph
            if agent_cfg.get("type") == "SUB":
                subgraph_id = agent_cfg["id"]
                inner_agent = agent_cfg.get("inner_agent", agent_cfg.get("inputs", ["item"])[0])
                subgraph_cfg = {
                    "id": subgraph_id,
                    "name": f"Subgraph for {subgraph_id}",
                    "nodes": ["START", inner_agent, "END"],
                    "edges": [["START", inner_agent], [inner_agent, "END"]],
                    "description": f"Auto-generated subgraph for {subgraph_id}"
                }
                sg_path = self.cm.save("graphs", subgraph_cfg)
                generated.append(sg_path)
                print(f"  Generated Subgraph: {subgraph_id} -> {sg_path}")

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
        for preferred in ("deepseek", "gpt-oss_120b"):
            if preferred in llms:
                return preferred
        if llms:
            return list(llms.keys())[0]
        return "deepseek"

    def generate_single_agent(self, requirement: str, llm_id: str) -> Optional[Dict]:
        """Generate a single agent config from a natural language requirement in ONE LLM call."""
        system = textwrap.dedent(f"""\
        You are a NeuraGraph agent designer. Generate a complete agent configuration from the user's requirement.

        {self.skill_context}

        Requirements:
        - Agent configs are saved as JSON files in meta/agents/ directory
        - The filename (without .json) is the agent ID, so DO NOT include an "id" field in the JSON
        - LLM agents need: name, type="LLM", model, inputs, outputs, prompt_template, tools, persistence
        - PGM agents need: name, type="PGM", inputs, outputs, process, persistence
        - SUB agents need: name, type="SUB", inputs, outputs, idx, persistence
        - prompt_template MUST have: description, system, human fields
        - Use {{field}} placeholders in prompts matching input names
        - name should be a short English descriptive name (e.g., "Gene Protein NER", "Coreference Resolution")
        - persistence should be an empty object {{}} if not needed, or specify columns/file_path/file_type
        - tools should be an empty array [] for LLM agents if no tools needed
        - created_at should be included with ISO format timestamp
        - model field should use "{llm_id}" for LLM agents
        - outputs format: {{"name": "output_field_name", "type": "str|dict|list"}}

        Return the COMPLETE agent configuration as valid JSON only (no markdown).
        """)

        print("\n[Generating agent config...]")
        response = self.llm.chat(system, f"Generate an agent for: {requirement}")

        try:
            agent_cfg = json.loads(response.strip())
        except json.JSONDecodeError:
            m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
            if m:
                agent_cfg = json.loads(m.group(1).strip())
            else:
                raise ValueError(f"Cannot parse agent response: {response[:200]}")

        # Remove id field if present (filename is the ID)
        if "id" in agent_cfg:
            agent_id = agent_cfg.pop("id")
        else:
            # Generate id from name
            agent_id = agent_cfg.get("name", "agent").lower().replace(" ", "_").replace("-", "_")
            agent_id = re.sub(r'[^a-z0-9_]', '', agent_id)
            if not agent_id:
                agent_id = "agent_" + str(abs(hash(requirement)) % 10000)

        # Ensure required fields
        agent_cfg.setdefault("name", agent_cfg.get("purpose", requirement)[:50])
        agent_cfg.setdefault("type", "LLM")
        agent_cfg.setdefault("inputs", ["text"])
        agent_cfg.setdefault("outputs", {"name": "result", "type": "str"})
        agent_cfg.setdefault("persistence", {})

        # Remove purpose field if present (use name instead)
        if "purpose" in agent_cfg:
            if not agent_cfg.get("name"):
                agent_cfg["name"] = agent_cfg.pop("purpose")
            else:
                del agent_cfg["purpose"]

        # Remove llm field if present (use model instead)
        if "llm" in agent_cfg:
            if not agent_cfg.get("model"):
                agent_cfg["model"] = agent_cfg.pop("llm")
            else:
                del agent_cfg["llm"]

        if agent_cfg.get("type") == "LLM":
            agent_cfg.setdefault("model", llm_id)
            agent_cfg.setdefault("tools", [])
            # Ensure prompt_template has description
            pt = agent_cfg.get("prompt_template", {})
            if "description" not in pt:
                pt["description"] = agent_cfg.get("name", "")
            agent_cfg["prompt_template"] = pt
        elif agent_cfg.get("type") == "PGM":
            agent_cfg.setdefault("process", "# Generated process\n__result__ = state.get('input', '')")

        # Add created_at
        from datetime import datetime
        agent_cfg.setdefault("created_at", datetime.now().isoformat())

        # Save with agent_id as filename
        agent_cfg["id"] = agent_id  # Temporarily add for save
        fpath = self.cm.save("agents", agent_cfg)
        del agent_cfg["id"]  # Remove id from the config (filename is ID)
        print(f"  Generated Agent: {agent_id} -> {fpath}")

        return {
            "status": "success",
            "agent_id": agent_id,
            "agent_config": agent_cfg,
            "generated": [str(fpath)],
        }


    def _generate_agent(self, plan: Dict, llm_id: str) -> Dict:
        """Use LLM to generate detailed agent config following standard format."""
        agent_type = plan["type"]

        system = textwrap.dedent(f"""\
        Generate a NeuraGraph agent configuration as JSON following the standard format.

        Standard LLM Agent Format:
        {{
          "name": "Short English name",
          "type": "LLM",
          "inputs": ["text"],
          "outputs": {{"name": "result", "type": "str"}},
          "persistence": {{}},
          "model": "{llm_id}",
          "prompt_template": {{
            "description": "What this agent does",
            "system": "System prompt...",
            "human": "Human prompt with {{field}} placeholders..."
          }},
          "tools": [],
          "created_at": "2026-01-01T00:00:00"
        }}

        Standard PGM Agent Format:
        {{
          "name": "Short English name",
          "type": "PGM",
          "inputs": ["text"],
          "outputs": {{"name": "result", "type": "str"}},
          "persistence": {{}},
          "process": "Python code using state dict and __result__",
          "created_at": "2026-01-01T00:00:00"
        }}

        Agent plan:
        {json.dumps(plan, indent=2)}

        LLM to use: {llm_id}

        Rules:
        1. DO NOT include "id" field (filename is the ID)
        2. DO NOT include "purpose" field (use "name" instead)
        3. DO NOT include "llm" field (use "model" instead)
        4. prompt_template MUST have: description, system, human
        5. Use {{field}} placeholders matching input names
        6. persistence must be an object {{}} even if empty
        7. LLM agents must have "tools": []
        8. Include "created_at" with current ISO timestamp
        9. name should be short English descriptive name

        Respond with valid JSON only (no markdown).
        """)

        response = self.llm.chat(system, f"Generate agent config for: {plan['id']}")

        try:
            cfg = json.loads(response)
        except json.JSONDecodeError:
            m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
            if m:
                cfg = json.loads(m.group(1))
            else:
                # Build minimal config from plan following standard format
                from datetime import datetime
                cfg = {
                    "name": plan.get("purpose", plan["id"]),
                    "type": agent_type,
                    "inputs": plan.get("inputs", []),
                    "outputs": plan.get("outputs", {"name": "result", "type": "str"}),
                    "persistence": {},
                    "created_at": datetime.now().isoformat(),
                }
                if agent_type == "LLM":
                    cfg["model"] = llm_id
                    cfg["tools"] = []
                    cfg["prompt_template"] = {
                        "description": plan.get("purpose", ""),
                        "system": f"You are a helpful assistant for {plan['id']}.",
                        "human": "Process the following:\n" + "\n".join(f"{inp}: {{{inp}}}" for inp in plan.get("inputs", [])),
                    }
                elif agent_type == "PGM":
                    cfg["process"] = f"# {plan.get('purpose', '')}\n__result__ = state.get('{plan.get('inputs', ['input'])[0]}', '')"

        # Clean up fields
        if "id" in cfg:
            del cfg["id"]
        if "purpose" in cfg:
            if not cfg.get("name"):
                cfg["name"] = cfg.pop("purpose")
            else:
                del cfg["purpose"]
        if "llm" in cfg:
            if not cfg.get("model"):
                cfg["model"] = cfg.pop("llm")
            else:
                del cfg["llm"]

        # Ensure required fields
        cfg.setdefault("name", plan.get("purpose", plan["id"]))
        cfg.setdefault("inputs", plan.get("inputs", []))
        cfg.setdefault("outputs", plan.get("outputs", {"name": "result", "type": "str"}))
        cfg.setdefault("persistence", {})
        from datetime import datetime
        cfg.setdefault("created_at", datetime.now().isoformat())

        if agent_type == "LLM":
            cfg.setdefault("model", llm_id)
            cfg.setdefault("tools", [])
            pt = cfg.get("prompt_template", {})
            if "description" not in pt:
                pt["description"] = cfg.get("name", "")
            cfg["prompt_template"] = pt
        elif agent_type == "PGM":
            cfg.setdefault("process", f"# {cfg.get('name', '')}\n__result__ = state.get('{cfg.get('inputs', ['input'])[0]}', '')")
        elif agent_type == "SUB":
            # SUB agent needs idx (loop variables) and a subgraph
            cfg.setdefault("idx", plan.get("idx", plan.get("inputs", ["item"])))
            # Store inner_agent for subgraph creation
            cfg.setdefault("inner_agent", plan.get("inner_agent", cfg["idx"][0] if cfg.get("idx") else "item"))

        # CRITICAL: save() needs cfg["id"], so re-add it before returning
        cfg["id"] = plan["id"]

        return cfg


    def _generate_tool(self, plan: Dict) -> Dict:
        """Use LLM to generate tool code."""
        system = textwrap.dedent(f"""\
        Generate a NeuraGraph tool configuration with Python code.

        Tool plan:
        {json.dumps(plan, indent=2)}

        Rules:
        - The code must define a `func` function with the specified parameters
        - Set `__result__` to the return value
        - CRITICAL: Do NOT use ANY import statements (json, re, etc. are pre-imported)
        - CRITICAL: Do NOT use __import__()
        - Use only basic Python operations

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

        # Sanitize code: remove all import statements (PGM env doesn't allow them)
        code = cfg.get("code", "")
        if code:
            # Remove 'import X' and 'from X import Y' lines
            import re
            code = re.sub(r'^(\s*import\s+\w+|\s*from\s+\w+\s+import\s+.*)$', '', code, flags=re.MULTILINE)
            # Remove empty lines created by removal
            code = '\n'.join(line for line in code.split('\n') if line.strip())
            cfg["code"] = code

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
    parser.add_argument("--llm", default="deepseek", help="LLM config ID to use for generation")
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
        print(f"  echo '{{\"id\":\"deepseek\",\"type\":\"openai\",\"model\":\"deepseek-chat\",\"base_url\":\"https://api.deepseek.com/v1\",\"api_key\":\"YOUR_KEY\",\"temperature\":0.7}}' > {META_DIR}/llms/deepseek.json")
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