#!/usr/bin/env python3
"""
NeuraGraph Chat - Terminal workflow builder (like Kimi Code).

Usage:
    python chat.py                    # Interactive chat mode
    python chat.py --llm kimi-2.6     # Use specific LLM
"""

import json
import os
import re
import sys
import subprocess
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── ANSI Colors ──
C = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "bg_green": "\033[42m",
    "bg_blue": "\033[44m",
    "bg_magenta": "\033[45m",
}

META_DIR = Path(__file__).parent / "meta"

# ═══════════════════════════════════════════════════════════════
# UI Primitives
# ═══════════════════════════════════════════════════════════════

def box(title: str, content: str, width: int = 60, color: str = "cyan") -> str:
    """Draw a box with title."""
    cc = C[color]
    lines = content.strip().split("\n")
    result = [f"{cc}┌─{'─' * (width - 3)}┐{C['reset']}"]
    if title:
        result.append(f"{cc}│{C['bold']} {title:<{width-4}} {C['reset']}{cc}│{C['reset']}")
        result.append(f"{cc}├─{'─' * (width - 3)}┤{C['reset']}")
    for line in lines:
        result.append(f"{cc}│{C['reset']} {line:<{width-4}} {cc}│{C['reset']}")
    result.append(f"{cc}└─{'─' * (width - 3)}┘{C['reset']}")
    return "\n".join(result)


def bot(text: str) -> str:
    """Bot message."""
    return f"{C['bg_blue']}{C['bold']} 🤖 {C['reset']} {C['cyan']}{text}{C['reset']}"


def user(text: str) -> str:
    """User message."""
    return f"{C['bg_green']}{C['bold']} 👤 {C['reset']} {C['green']}{text}{C['reset']}"


def info(label: str, text: str = "") -> str:
    """Info line."""
    return f"{C['dim']}   {label}{C['reset']} {text}"


def success(text: str) -> str:
    return f"{C['green']}   ✓ {text}{C['reset']}"


def error(text: str) -> str:
    return f"{C['red']}   ✗ {text}{C['reset']}"


def warn(text: str) -> str:
    return f"{C['yellow']}   ! {text}{C['reset']}"


def step(num: int, text: str) -> str:
    return f"{C['bold']}{C['yellow']}   [{num}] {text}{C['reset']}"


def code_block(text: str, lang: str = "json") -> str:
    """Format code block."""
    lines = text.strip().split("\n")
    width = min(max(len(l) for l in lines) + 4, 80)
    result = [f"{C['dim']}   {'─' * width}{C['reset']}"]
    for line in lines[:50]:  # Limit lines
        result.append(f"{C['dim']}   │{C['reset']} {line}")
    result.append(f"{C['dim']}   {'─' * width}{C['reset']}")
    return "\n".join(result)


def header() -> str:
    return f"""
{C['bold']}{C['cyan']}╔══════════════════════════════════════════════════════════════╗
║  🧠 NeuraGraph Chat - Terminal Workflow Builder             ║
║  {C['dim']}Type commands: /help, /list, /run, /show, /exit{C['cyan']}          ║
╚══════════════════════════════════════════════════════════════╝{C['reset']}"""


def prompt() -> str:
    """Return plain-text prompt. Never put ANSI codes in input() prompt."""
    return "> "


# ═══════════════════════════════════════════════════════════════
# Workflow ASCII Visualizer
# ═══════════════════════════════════════════════════════════════

def draw_workflow(graph_id: str, meta_dir: Path = META_DIR) -> str:
    """Draw ASCII workflow diagram."""
    try:
        with open(meta_dir / "graphs" / f"{graph_id}.json") as f:
            graph = json.load(f)
    except:
        return f"{C['red']}   Workflow not found: {graph_id}{C['reset']}"

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    # Build node info
    node_info = {}
    for nid in nodes:
        if nid in ("START", "END"):
            continue
        try:
            with open(meta_dir / "agents" / f"{nid}.json") as f:
                agent = json.load(f)
            node_info[nid] = f"[{agent.get('type', '?')}] {agent.get('name', nid)}"
        except:
            node_info[nid] = nid

    # Build execution order from edges
    order = []
    visited = set()
    current = "START"
    while current != "END":
        visited.add(current)
        found = False
        for edge in edges:
            if len(edge) >= 2 and edge[0] == current:
                next_node = edge[1]
                if next_node not in ("END",):
                    order.append((current, next_node))
                current = next_node
                found = True
                break
        if not found or current in visited:
            break

    # Draw
    lines = []
    lines.append(f"{C['dim']}   Workflow: {C['bold']}{graph.get('name', graph_id)}{C['reset']}")
    lines.append(f"{C['dim']}   {'─' * 50}{C['reset']}")

    lines.append(f"   {C['green']} START {C['reset']}  {C['dim']}─┬─▶{C['reset']}")
    for i, (src, tgt) in enumerate(order):
        prefix = "   "
        if i == len(order) - 1:
            connector = f"{C['dim']}       └─▶{C['reset']}"
        else:
            connector = f"{C['dim']}       ├─▶{C['reset']}"

        agent_type = "?"
        name = tgt
        if tgt in node_info:
            match = re.match(r'\[(\w+)\] (.+)', node_info[tgt])
            if match:
                agent_type = match.group(1)
                name = match.group(2)

        type_color = {"LLM": C["blue"], "PGM": C["magenta"], "SUB": C["yellow"]}.get(agent_type, C["white"])
        lines.append(f"{connector} {type_color}[{agent_type}]{C['reset']} {name}")

    lines.append(f"   {C['dim']}       └─▶{C['reset']} {C['red']} END {C['reset']}")
    lines.append(f"{C['dim']}   {'─' * 50}{C['reset']}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# LLM Command Parser
# ═══════════════════════════════════════════════════════════════

class LLMCommandParser:
    """Use an LLM to parse natural language into structured intents."""

    def __init__(self, llm_config: Dict, meta_dir: Path = META_DIR):
        import autogen
        self.llm = autogen.LLMClient(llm_config)
        self.meta_dir = meta_dir
        self.skill_path = Path(__file__).parent / "SKILL.md"
        self.skill_context = self._load_skill()

    def _load_skill(self) -> str:
        if self.skill_path.exists():
            return self.skill_path.read_text()
        return textwrap.dedent("""\
        You are a NeuraGraph workflow designer. You generate JSON configs for:
        - agents (LLM/PGM/SUB types)
        - graphs (workflows: nodes + edges)
        - llms (provider configs)
        - tools (Python code functions)
        """)

    def _load_catalog(self) -> str:
        """Scan meta directories and return a catalog string."""
        lines = []
        for subdir, title in [
            ("agents", "Agents"),
            ("graphs", "Workflows"),
            ("tools", "Tools"),
            ("llms", "LLMs"),
            ("exps", "Experiments"),
        ]:
            d = self.meta_dir / subdir
            if not d.exists():
                continue
            items = []
            for f in sorted(d.glob("*.json")):
                try:
                    cfg = json.loads(f.read_text())
                    name = cfg.get("name", f.stem)
                    items.append(f"- {f.stem}: {name}")
                except Exception:
                    items.append(f"- {f.stem}")
            if items:
                lines.append(f"\n## {title}")
                lines.extend(items)
        return "\n".join(lines)

    def _build_system_prompt(self) -> str:
        catalog = self._load_catalog()
        return textwrap.dedent(f"""\
        You are the NeuraGraph Chat Controller. Your job is to understand the user's natural language input and return a JSON object describing what action to take.

        # Skill Context
        {self.skill_context}

        # Available Resources
        {catalog}

        # Response Format
        Return a JSON object with this structure:
        {{
          "thinking": "Your step-by-step reasoning about what the user wants (in the same language as the user)",
          "action": "ACTION_NAME",
          "parameters": {{...}},
          "response": "Natural language reply to the user (in the same language as their input)"
        }}

        Valid ACTION_NAME values:
        - "list_agents" / "list_workflows" / "list_graphs" / "list_tools" / "list_datasets" / "list_llms" / "list_experiments"
        - "show_agent" / "show_workflow" / "show_graph" / "show_tool" / "show_dataset" / "show_llm" / "show_experiment"
          parameters: {{"id": "entity_id"}}
        - "run_agent" / "run_workflow" / "run_graph" / "run_experiment"
          parameters: {{"id": "entity_id"}}
        - "generate_agent"
          parameters: {{"requirement": "natural language description of the agent to create"}}
        - "generate_workflow" / "generate_graph"
          parameters: {{"requirement": "natural language description of the workflow to create"}}
        - "update_agent" / "update_workflow" / "update_graph" / "update_tool" / "update_llm"
          parameters: {{"id": "entity_id", "changes": "natural language description of what to change"}}
        - "delete_agent" / "delete_workflow" / "delete_graph" / "delete_tool" / "delete_llm" / "delete_experiment"
          parameters: {{"id": "entity_id"}}
        - "chat"
          parameters: {{}}
        - "command"
          parameters: {{"cmd": "/slash command string"}}

        Rules:
        1. Always respond with valid JSON only. No markdown code blocks, no extra text.
        2. The "thinking" field should explain your reasoning briefly.
        3. The "response" field should be in the same language as the user's input.
        4. If the user wants to create/build/make/generate something:
           - Use "generate_agent" if they mention "agent", "智能体", or "代理" without mentioning "workflow", "工作流", "流程", or "graph".
           - Otherwise use "generate_workflow".
        5. If the user wants to modify/change/update something, use "update_*" actions.
        6. If the user wants to remove/delete something, use "delete_*" actions.
        7. If you are unsure about the entity ID, use "chat" and ask the user to clarify.
        8. Maintain context from previous messages in the conversation.
        """)

    def parse(self, message: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
        system = self._build_system_prompt()

        # Build conversation context from history
        context_msgs = []
        for h in history[-10:]:
            context_msgs.append(f"{h['role'].upper()}: {h['content']}")
        context = "\n".join(context_msgs)

        user_content = message
        if context:
            user_content = f"[Conversation context]\n{context}\n\n[Current message]\n{message}"

        try:
            # Show progress while streaming
            print(f"\n{C['dim']}💭 ", end="", flush=True)
            full_response = []

            for chunk in self.llm.chat_stream(system, user_content):
                full_response.append(chunk)

            print(C['reset'])
            buffer = "".join(full_response)
            intent = self._parse_intent_from_text(buffer)

            # Type out the thinking text character by character
            thinking = intent.get("thinking", "")
            if thinking:
                print(f"{C['dim']}💭 ", end="", flush=True)
                import time
                for char in thinking:
                    print(char, end="", flush=True)
                    time.sleep(0.015)
                print(C['reset'])

            return intent

        except Exception as e:
            print(C['reset'])
            return {
                "action": "chat",
                "parameters": {},
                "response": f"LLM 调用失败: {e}\n可以输入 /retry 重试。",
            }

    def _parse_intent_from_text(self, text: str) -> Dict[str, Any]:
        """Parse JSON intent from text, with markdown fallback."""
        text = text.strip()
        intent = None
        try:
            intent = json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
            if m:
                try:
                    intent = json.loads(m.group(1).strip())
                except json.JSONDecodeError:
                    pass

        if intent is None:
            return {
                "action": "chat",
                "parameters": {},
                "response": text[:500] if text else "抱歉，我没能正确解析你的意图。",
            }

        intent.setdefault("action", "chat")
        intent.setdefault("parameters", {})
        intent.setdefault("response", "")
        return intent


# ═══════════════════════════════════════════════════════════════
# Workflow Generation (via autogen)
# ═══════════════════════════════════════════════════════════════

def generate_workflow(requirement: str, llm_id: str = "kimi-2.6") -> Optional[Dict]:
    """Use autogen.py to generate workflow from requirement."""
    import autogen

    # Load LLM config
    cm = autogen.ConfigManager(META_DIR)
    llms = cm.load_all("llms")
    llm_config = llms.get(llm_id)
    if not llm_config:
        return None

    engine = autogen.AutoGen(llm_config)
    engine.cm = cm

    try:
        plan = engine.analyze(requirement)
        generated = engine.generate(plan)
        errors = engine.validate(plan)

        if errors:
            return {"status": "validation_failed", "errors": errors, "plan": plan}

        return {
            "status": "success",
            "plan": plan,
            "generated": [str(p) for p in generated],
            "graph_id": plan.get("graph_plan", {}).get("id", ""),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ═══════════════════════════════════════════════════════════════
# Workflow Execution (via run_workflow)
# ═══════════════════════════════════════════════════════════════

def execute_workflow(graph_id: str, inputs: Dict) -> Dict:
    """Execute workflow and return result."""
    import run_workflow as rw

    try:
        rw.STORE.load(META_DIR)
        runner = rw.GraphRunner(graph_id, verbose=True)
        result = runner.run(inputs)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def execute_agent(agent_id: str, inputs: Dict) -> Dict:
    """Execute a single agent and return result."""
    import run_workflow as rw

    try:
        rw.STORE.load(META_DIR)
        runner = rw.AgentRunner(verbose=True)
        state = dict(inputs)
        result = runner.run(agent_id, state)

        # Add output to state
        agent = rw.STORE.agents.get(agent_id, {})
        output_name = agent.get("outputs", {}).get("name")
        if output_name and result is not None:
            state[output_name] = result

        return {"status": "success", "result": state}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ═══════════════════════════════════════════════════════════════
# Chat Engine
# ═══════════════════════════════════════════════════════════════

class ChatEngine:
    def __init__(self, llm_id: str = "kimi-2.6", parser: Optional[Any] = None):
        self.llm_id = llm_id
        self.parser = parser
        self.history: List[Dict[str, str]] = []
        self.last_graph = ""
        self.last_input = ""  # Last user message for /retry

    def print_bot(self, text: str):
        print(f"\n{bot(text)}")

    def print_user(self, text: str):
        print(f"\n{user(text)}")

    def handle_command(self, cmd: str) -> bool:
        """Handle slash commands. Return True if handled."""
        parts = cmd.strip().split()
        if not parts:
            return False

        command = parts[0].lower()

        # ── /help ──
        if command in ("/help", "/h"):
            print(f"""
{C['bold']}Commands:{C['reset']}

  {C['yellow']}/list workflows{C['reset']}      List all workflows (graphs)
  {C['yellow']}/list agents{C['reset']}         List all agents
  {C['yellow']}/list tools{C['reset']}          List all tools
  {C['yellow']}/list datasets{C['reset']}       List all datasets
  {C['yellow']}/list llms{C['reset']}           List all LLM configs
  {C['yellow']}/list experiments{C['reset']}    List all experiments

  {C['yellow']}/show workflow <id>{C['reset']}  Show workflow diagram
  {C['yellow']}/show agent <id>{C['reset']}     Show agent config
  {C['yellow']}/show tool <id>{C['reset']}      Show tool config
  {C['yellow']}/show dataset <id>{C['reset']}   Show dataset info
  {C['yellow']}/show llm <id>{C['reset']}       Show LLM config
  {C['yellow']}/show experiment <id>{C['reset']} Show experiment status

  {C['yellow']}/run workflow <id>{C['reset']}   Run a workflow
  {C['yellow']}/run agent <id>{C['reset']}      Run a single agent
  {C['yellow']}/run experiment <id>{C['reset']} Replay experiment info

  {C['yellow']}/delete agent <id>{C['reset']}    Delete an agent
  {C['yellow']}/delete workflow <id>{C['reset']} Delete a workflow
  {C['yellow']}/delete tool <id>{C['reset']}     Delete a tool

  {C['yellow']}/retry{C['reset']}               Retry last command/message

  {C['yellow']}/exit{C['reset']}                Exit chat

{C['bold']}Natural language:{C['reset']}
  "列出所有 agents"
  "运行 bio_ner_graph 工作流"
  "显示 ner_demo 的详情"
  "查看所有 tools"
""")
            return True

        # ── /exit ──
        if command in ("/exit", "/quit"):
            print(f"\n{C['cyan']}Goodbye! 👋{C['reset']}\n")
            sys.exit(0)

        # ── /retry ──
        if command == "/retry":
            if not self.last_input or self.last_input == "/retry":
                self.print_bot("没有可重试的上一条命令")
                return True
            self.print_bot(f"正在重试: {self.last_input}")
            if self.last_input.startswith("/"):
                self.handle_command(self.last_input)
            else:
                # Avoid duplicate history entry: pop last user message if it matches
                if self.history and self.history[-1].get("content") == self.last_input:
                    self.history.pop()
                self.chat(self.last_input)
            return True

        # ── /delete <type> <id> ──
        if command == "/delete":
            if len(parts) >= 3:
                sub = parts[1].lower()
                eid = parts[2]
                type_map = {
                    "agent": "agents",
                    "workflow": "graphs",
                    "graph": "graphs",
                    "tool": "tools",
                    "llm": "llms",
                    "experiment": "exps",
                    "exp": "exps",
                }
                if sub in type_map:
                    self._delete_meta(type_map[sub], eid)
                else:
                    print(error(f"Unknown delete type: {sub}"))
            else:
                print(error("Usage: /delete <type> <id>"))
            return True

        # ── /list <type> ──
        if command == "/list":
            sub = parts[1].lower() if len(parts) > 1 else "workflows"
            if sub in ("workflows", "workflow", "graphs", "graph"):
                self._list_meta("graphs", "Available Workflows",
                    lambda stem, cfg: f"  {C['cyan']}{stem:<30}{C['reset']} {cfg.get('name', '')} [{', '.join(n for n in cfg.get('nodes', []) if n not in ('START', 'END'))}]")
            elif sub in ("agents", "agent"):
                self._list_meta("agents", "Available Agents",
                    lambda stem, cfg: f"  {(C['blue'] if cfg.get('type') == 'LLM' else C['magenta'] if cfg.get('type') == 'PGM' else C['yellow'] if cfg.get('type') == 'SUB' else C['white'])}{cfg.get('type', '?'):4}{C['reset']} {stem:<30} {cfg.get('name', '')}")
            elif sub in ("tools", "tool"):
                self._list_meta("tools", "Available Tools",
                    lambda stem, cfg: f"  {C['green']}{stem:<30}{C['reset']} {cfg.get('name', '')}")
            elif sub in ("datasets", "dataset"):
                self._list_datasets()
            elif sub in ("llms", "llm"):
                self._list_meta("llms", "LLM Configs",
                    lambda stem, cfg: f"  {C['magenta']}{stem:<25}{C['reset']} [{cfg.get('type', '?')}] {cfg.get('model', '?')} @ {cfg.get('base_url', '?')}")
            elif sub in ("experiments", "experiment", "exps", "exp"):
                self._list_meta("exps", "Experiments",
                    lambda stem, cfg: f"  {C['yellow']}{stem:<36}{C['reset']} {cfg.get('name', '')} [{cfg.get('status', '?')}] {cfg.get('runner_id', '')}")
            else:
                print(error(f"Unknown list type: {sub}. Try: workflows, agents, tools, datasets, llms, experiments"))
            return True

        # Backward compat aliases
        if command == "/graphs":
            self.handle_command("/list workflows")
            return True
        if command == "/agents":
            self.handle_command("/list agents")
            return True
        if command == "/llms":
            self.handle_command("/list llms")
            return True

        # ── /show <type> <id>  or  /show <id> ──
        if command == "/show":
            if len(parts) == 2:
                # Backward compat: /show <id> -> /show workflow <id>
                print(f"\n{draw_workflow(parts[1])}")
                return True
            if len(parts) >= 3:
                sub = parts[1].lower()
                eid = parts[2]
                if sub in ("workflow", "graph"):
                    print(f"\n{draw_workflow(eid)}")
                elif sub == "agent":
                    self._show_json("agents", eid, "Agent")
                elif sub == "tool":
                    self._show_json("tools", eid, "Tool")
                elif sub == "dataset":
                    self._show_dataset(eid)
                elif sub in ("llm",):
                    self._show_json("llms", eid, "LLM")
                elif sub in ("experiment", "exp"):
                    self._show_json("exps", eid, "Experiment")
                else:
                    print(error(f"Unknown show type: {sub}"))
                return True

        # ── /run <type> <id>  or  /run <id> ──
        if command == "/run":
            if len(parts) == 2:
                # Backward compat: /run <id> -> /run workflow <id>
                self._run_interactive(parts[1])
                return True
            if len(parts) >= 3:
                sub = parts[1].lower()
                eid = parts[2]
                if sub in ("workflow", "graph"):
                    self._run_interactive(eid)
                elif sub == "agent":
                    self._run_agent(eid)
                elif sub in ("experiment", "exp"):
                    self._run_experiment(eid)
                else:
                    print(error(f"Unknown run type: {sub}"))
                return True

        return False

    def _list_datasets(self):
        """List all datasets found in tests/ directory."""
        print(f"\n{C['bold']}Datasets:{C['reset']}")
        tests_dir = Path(__file__).parent / "tests"
        found = False
        if tests_dir.exists():
            for runner_dir in sorted(tests_dir.iterdir()):
                if runner_dir.is_dir():
                    for f in sorted(runner_dir.glob("*.csv")):
                        print(f"  {C['cyan']}{f.stem:<30}{C['reset']} (runner: {runner_dir.name})")
                        found = True
                    for f in sorted(runner_dir.glob("*.txt")):
                        print(f"  {C['cyan']}{f.stem:<30}{C['reset']} (runner: {runner_dir.name})")
                        found = True
        if not found:
            print(warn("No datasets found in tests/"))

    def _run_interactive(self, graph_id: str):
        """Run workflow with interactive input."""
        print(f"\n{draw_workflow(graph_id)}")

        # Collect inputs from user
        try:
            with open(META_DIR / "graphs" / f"{graph_id}.json") as f:
                graph = json.load(f)
        except:
            print(error(f"Workflow '{graph_id}' not found"))
            return

        # Find required input fields from first agent's inputs
        inputs = {}
        for node in graph.get("nodes", []):
            if node in ("START", "END"):
                continue
            try:
                with open(META_DIR / "agents" / f"{node}.json") as f:
                    agent = json.load(f)
                for inp in agent.get("inputs", []):
                    if inp not in inputs:
                        print(f"{C['yellow']}   Input '{inp}': {C['reset']}", end="")
                        val = input()
                        try:
                            inputs[inp] = json.loads(val)
                        except:
                            inputs[inp] = val
            except:
                pass

        if not inputs:
            print(warn("No inputs required or could not determine inputs"))
            return

        self._execute(graph_id, inputs)

    def _execute(self, graph_id: str, inputs: Dict):
        """Execute and display results."""
        title = f"{C['bold']}{graph_id}{C['reset']}"
        print(f"\n{step(1, f'Executing workflow: {title}')}")

        result = execute_workflow(graph_id, inputs)

        if result["status"] == "success":
            final_state = result["result"]
            print(f"\n{C['bold']}{C['green']}   ✅ Execution Complete{C['reset']}")

            # Display outputs
            for k, v in final_state.items():
                if k in inputs:  # Skip inputs
                    continue
                if isinstance(v, (dict, list)):
                    print(f"\n   {C['bold']}{k}:{C['reset']}")
                    print(code_block(json.dumps(v, indent=4, ensure_ascii=False)))
                else:
                    print(f"   {C['bold']}{k}:{C['reset']} {str(v)[:500]}")

            self.last_graph = graph_id
        else:
            print(error(f"Execution failed: {result.get('message', 'Unknown error')}"))

    def chat(self, message: str):
        """Process a chat message (non-command)."""
        self.history.append({"role": "user", "content": message})

        if self.parser is None:
            self._chat_fallback(message)
            return

        try:
            intent = self.parser.parse(message, self.history)
        except Exception as e:
            print(error(f"LLM 解析失败: {e}"))
            print(info("提示: 输入 /retry 可以重试上一条消息"))
            self._chat_fallback(message)
            return

        self._dispatch_intent(intent)

    def _dispatch_intent(self, intent: Dict[str, Any]):
        """Route LLM-parsed intent to the appropriate handler."""
        action = intent.get("action", "chat")
        params = intent.get("parameters", {})
        response = intent.get("response", "")

        if response:
            self.print_bot(response)

        if action == "chat":
            pass  # Response already printed
        elif action == "command":
            cmd = params.get("cmd", "")
            if cmd:
                if not self.handle_command(cmd):
                    print(error(f"未知命令: {cmd}"))
        elif action == "list_agents":
            self.handle_command("/list agents")
        elif action in ("list_workflows", "list_graphs"):
            self.handle_command("/list workflows")
        elif action == "list_tools":
            self.handle_command("/list tools")
        elif action == "list_datasets":
            self._list_datasets()
        elif action == "list_llms":
            self.handle_command("/list llms")
        elif action == "list_experiments":
            self.handle_command("/list experiments")
        elif action == "show_agent":
            aid = params.get("id", "")
            if aid:
                self.handle_command(f"/show agent {aid}")
            else:
                self.print_bot("请提供 agent ID")
        elif action in ("show_workflow", "show_graph"):
            gid = params.get("id", "")
            if gid:
                self.handle_command(f"/show workflow {gid}")
            else:
                self.print_bot("请提供 workflow ID")
        elif action == "show_tool":
            tid = params.get("id", "")
            if tid:
                self.handle_command(f"/show tool {tid}")
        elif action == "show_dataset":
            did = params.get("id", "")
            if did:
                self._show_dataset(did)
        elif action == "show_llm":
            lid = params.get("id", "")
            if lid:
                self.handle_command(f"/show llm {lid}")
        elif action == "show_experiment":
            eid = params.get("id", "")
            if eid:
                self.handle_command(f"/show experiment {eid}")
        elif action == "run_agent":
            aid = params.get("id", "")
            if aid:
                self._run_agent(aid)
            else:
                self.print_bot("请提供 agent ID")
        elif action in ("run_workflow", "run_graph"):
            gid = params.get("id", "")
            if gid:
                self._run_interactive(gid)
            else:
                self.print_bot("请提供 workflow ID")
        elif action == "run_experiment":
            eid = params.get("id", "")
            if eid:
                self._run_experiment(eid)
        elif action == "generate_agent":
            req = params.get("requirement", "")
            if req:
                self._handle_build_agent(req)
            else:
                self.print_bot("请描述你想生成的 agent")
        elif action in ("generate_workflow", "generate_graph"):
            req = params.get("requirement", "")
            if req:
                self._handle_build(req)
            else:
                self.print_bot("请描述你想生成的 workflow")
        elif action == "update_agent":
            self._update_meta("agents", params.get("id", ""), params.get("changes", ""))
        elif action in ("update_workflow", "update_graph"):
            self._update_meta("graphs", params.get("id", ""), params.get("changes", ""))
        elif action == "update_tool":
            self._update_meta("tools", params.get("id", ""), params.get("changes", ""))
        elif action == "update_llm":
            self._update_meta("llms", params.get("id", ""), params.get("changes", ""))
        elif action == "delete_agent":
            self._delete_meta("agents", params.get("id", ""))
        elif action in ("delete_workflow", "delete_graph"):
            self._delete_meta("graphs", params.get("id", ""))
        elif action == "delete_tool":
            self._delete_meta("tools", params.get("id", ""))
        elif action == "delete_llm":
            self._delete_meta("llms", params.get("id", ""))
        elif action == "delete_experiment":
            self._delete_meta("exps", params.get("id", ""))
        else:
            self.print_bot(f"未知操作: {action}")

    def _update_meta(self, subdir: str, entity_id: str, changes: str):
        """Update an existing config via LLM."""
        if not entity_id:
            self.print_bot("请提供要更新的实体 ID")
            return
        fpath = META_DIR / subdir / f"{entity_id}.json"
        if not fpath.exists():
            print(error(f"{subdir[:-1].title()} '{entity_id}' not found"))
            return

        try:
            existing = json.loads(fpath.read_text())
        except Exception as e:
            print(error(f"读取配置失败: {e}"))
            return

        print(f"\n{C['bold']}{C['yellow']}{'─' * 60}{C['reset']}")
        self.print_bot(f"正在更新 {entity_id}...")

        # Use LLM to generate updated config
        import autogen
        cm = autogen.ConfigManager(META_DIR)
        llm_config = cm.load_all("llms").get(self.llm_id)
        if not llm_config:
            print(error(f"LLM '{self.llm_id}' 未找到"))
            return

        system = textwrap.dedent("""\
        You are updating an existing NeuraGraph configuration.
        Read the current config and apply the user's requested changes.
        Return the COMPLETE updated config as valid JSON only.
        Preserve all fields unless the user explicitly asks to change them.
        Do not add markdown code blocks, return raw JSON only.
        """)
        user_prompt = f"Current config:\n{json.dumps(existing, indent=2, ensure_ascii=False)}\n\nChanges requested:\n{changes}"

        try:
            client = autogen.LLMClient(llm_config)
            response = client.chat(system, user_prompt)
        except Exception as e:
            print(error(f"LLM 调用失败: {e}"))
            return

        # Parse updated config
        updated = None
        try:
            updated = json.loads(response.strip())
        except json.JSONDecodeError:
            m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
            if m:
                try:
                    updated = json.loads(m.group(1).strip())
                except json.JSONDecodeError:
                    pass

        if updated is None:
            print(error("LLM 返回的更新配置无法解析"))
            return

        # Ensure ID is preserved
        updated["id"] = entity_id

        # Save back
        try:
            fpath.write_text(json.dumps(updated, indent=2, ensure_ascii=False))
            print(success(f"已更新 {entity_id}"))
            print(code_block(json.dumps(updated, indent=2, ensure_ascii=False)))
        except Exception as e:
            print(error(f"保存失败: {e}"))

        print(f"{C['bold']}{C['yellow']}{'─' * 60}{C['reset']}")

    def _delete_meta(self, subdir: str, entity_id: str):
        """Delete a config file with confirmation."""
        if not entity_id:
            self.print_bot("请提供要删除的实体 ID")
            return
        fpath = META_DIR / subdir / f"{entity_id}.json"
        if not fpath.exists():
            print(error(f"'{entity_id}' not found in {subdir}"))
            return

        print(f"\n{C['bold']}{C['red']}{'─' * 60}{C['reset']}")
        print(warn(f"确定要删除 {entity_id} 吗？此操作不可撤销。(y/n)"))
        print(f"{C['bold']}{C['yellow']}> {C['reset']}", end="")
        answer = input().strip().lower()
        if answer in ("y", "yes", "是"):
            try:
                fpath.unlink()
                print(success(f"已删除 {entity_id}"))
            except Exception as e:
                print(error(f"删除失败: {e}"))
        else:
            print(info("已取消删除"))
        print(f"{C['bold']}{C['red']}{'─' * 60}{C['reset']}")

    def _chat_fallback(self, message: str):
        """Fallback keyword-based logic when LLM parser is unavailable."""
        # 1. Try natural language command first
        nl_cmd = self._parse_natural_language(message)
        if nl_cmd:
            if not self.handle_command(nl_cmd):
                print(error(f"Could not execute natural language command: {nl_cmd}"))
            return

        # 2. Check if it's a request to build something
        build_keywords = ["build", "create", "make", "generate", "workflow", "pipeline",
                          "extract", "summarize", "classify", "translate", "analyze",
                          "识别", "提取", "分类", "翻译", "生成", "构建", "总结"]
        agent_keywords = ["agent", "agents", "智能体", "代理"]
        workflow_keywords = ["workflow", "workflows", "pipeline", "graph", "graphs", "工作流", "流程", "图"]

        is_build_request = any(kw in message.lower() for kw in build_keywords)
        is_agent_request = any(kw in message.lower() for kw in agent_keywords)
        is_workflow_request = any(kw in message.lower() for kw in workflow_keywords)

        if is_build_request:
            if is_agent_request and not is_workflow_request:
                self._handle_build_agent(message)
            else:
                self._handle_build(message)
        elif message.lower() in ("hi", "hello", "你好", "嗨"):
            self.print_bot("你好！我是 NeuraGraph Chat。请描述你想构建的 workflow 或 agent，或输入 /help 查看命令。")
        else:
            self.print_bot("我不太确定你的意图。你可以：\n   1. 描述你想构建的 workflow 或 agent（如：'提取生物医学文本中的实体'）\n   2. 输入 /help 查看命令")

    def _select_llm_interactive(self) -> Optional[str]:
        """Let user choose an LLM from available configs."""
        import autogen
        cm = autogen.ConfigManager(META_DIR)
        llms = cm.load_all("llms")
        if not llms:
            print(error("没有可用的 LLM 配置"))
            return None
        if len(llms) == 1:
            return list(llms.keys())[0]

        print(f"\n{C['bold']}可用的 LLM 配置:{C['reset']}")
        llm_list = sorted(llms.items(), key=lambda x: x[0])
        for i, (lid, lcfg) in enumerate(llm_list, 1):
            model = lcfg.get("model", "?")
            base = lcfg.get("base_url", "?")
            print(f"  {C['yellow']}[{i}]{C['reset']} {C['magenta']}{lid:<30}{C['reset']} [{lcfg.get('type', '?')}] {model} @ {base}")
        print(f"  {C['dim']}(输入编号或名称){C['reset']}")
        print(f"{C['yellow']}> {C['reset']}", end="")
        choice = input().strip()

        # Try numeric choice
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(llm_list):
                return llm_list[idx][0]
        except ValueError:
            pass

        # Try name
        if choice in llms:
            return choice

        print(warn(f"未识别的选择 '{choice}'，使用默认 LLM"))
        return self.llm_id

    def _handle_build_agent(self, requirement: str):
        """Handle single agent building request."""
        print(f"\n{C['bold']}{C['yellow']}{'─' * 60}{C['reset']}")

        # Ask for LLM
        llm_id = self._select_llm_interactive()
        if not llm_id:
            return

        self.print_bot("正在生成 Agent...")
        import autogen
        cm = autogen.ConfigManager(META_DIR)
        llm_config = cm.load_all("llms").get(llm_id)
        if not llm_config:
            print(error(f"LLM '{llm_id}' 未找到"))
            return

        engine = autogen.AutoGen(llm_config)
        engine.cm = cm

        try:
            result = engine.generate_single_agent(requirement, llm_id)
        except Exception as e:
            print(error(f"生成失败: {e}"))
            print(info("提示: 输入 /retry 可以重试上一条消息"))
            return

        if not result or result.get("status") != "success":
            print(error("Agent 生成失败"))
            print(info("提示: 输入 /retry 可以重试上一条消息"))
            return

        agent_id = result.get("agent_id", "")
        agent_cfg = result.get("agent_config", {})
        print(success(f"已生成 Agent: {agent_id}"))
        print(code_block(json.dumps(agent_cfg, indent=2, ensure_ascii=False)))

        # Ask to run
        self.print_bot("是否立即运行该 Agent？(y/n)")
        print(f"{C['bold']}{C['yellow']}> {C['reset']}", end="")
        answer = input().strip().lower()
        if answer in ("y", "yes", "是", ""):
            self._run_agent(agent_id)

        print(f"{C['bold']}{C['yellow']}{'─' * 60}{C['reset']}")

    def _handle_build(self, requirement: str):
        """Handle workflow building request."""
        print(f"\n{C['bold']}{C['yellow']}{'─' * 60}{C['reset']}")

        # Ask for LLM
        llm_id = self._select_llm_interactive()
        if not llm_id:
            return

        # Phase 1: Analyze
        self.print_bot("正在分析需求...")
        result = generate_workflow(requirement, llm_id)

        if not result or result.get("status") == "error":
            print(error(f"分析失败: {result.get('message', 'Unknown error')}"))
            print(info("提示: 输入 /retry 可以重试上一条消息"))
            return

        if result.get("status") == "validation_failed":
            print(error(f"验证失败:"))
            for e in result.get("errors", []):
                print(f"     - {e}")
            return

        plan = result.get("plan", {})
        graph_id = result.get("graph_id", "")
        generated = result.get("generated", [])

        # Show analysis
        analysis = plan.get("analysis", "")
        if analysis:
            print(info("分析:", analysis))

        # Show generated components
        agents = [a["id"] for a in plan.get("agent_plan", [])]
        if agents:
            print(success(f"已生成 {len(agents)} 个 agent: {', '.join(agents)}"))
        if generated:
            print(success(f"已生成 {len(generated)} 个配置文件"))

        # Show workflow diagram
        if graph_id:
            print(f"\n{draw_workflow(graph_id)}")
            self.last_graph = graph_id

        # Ask to execute
        self.print_bot("Workflow 已生成！是否执行？(y/n)")
        print(f"{C['bold']}{C['yellow']}> {C['reset']}", end="")
        answer = input().strip().lower()

        if answer in ("y", "yes", "是", ""):
            # Collect inputs
            inputs = {}
            graph = plan.get("graph_plan", {})

            # Find all unique input fields from agents
            input_fields = set()
            for agent_plan in plan.get("agent_plan", []):
                for inp in agent_plan.get("inputs", []):
                    input_fields.add(inp)

            # Remove outputs (they're produced by upstream agents)
            output_fields = set()
            for agent_plan in plan.get("agent_plan", []):
                out = agent_plan.get("outputs", {}).get("name", "")
                if out:
                    output_fields.add(out)

            required_inputs = input_fields - output_fields

            if required_inputs:
                self.print_bot("请提供输入数据:")
                for field in sorted(required_inputs):
                    print(f"{C['yellow']}   {field}: {C['reset']}", end="")
                    val = input().strip()
                    if not val:
                        val = self._demo_data(field)
                        print(f"   {C['dim']}(使用示例数据: {val}){C['reset']}")
                    try:
                        inputs[field] = json.loads(val)
                    except:
                        inputs[field] = val
            else:
                inputs = self._demo_inputs(graph_id)
                print(info("使用示例输入:", json.dumps(inputs, ensure_ascii=False)))

            self._execute(graph_id, inputs)

        print(f"{C['bold']}{C['yellow']}{'─' * 60}{C['reset']}")

    def _demo_data(self, field: str) -> str:
        """Generate demo data for common fields."""
        demos = {
            "text": "Aspirin is used to treat headache, fever, and inflammation. Metformin is prescribed for type 2 diabetes.",
            "labels": "Chemical,Disease",
            "query": "What are the side effects of aspirin?",
            "sentence": "The quick brown fox jumps over the lazy dog.",
            "content": "Artificial intelligence is transforming healthcare through faster diagnosis and personalized treatment.",
        }
        return demos.get(field, f"example_{field}")

    def _demo_inputs(self, graph_id: str) -> Dict:
        """Generate demo inputs based on graph."""
        return {"text": "Aspirin treats headache and fever. Metformin is used for diabetes.",
                "labels": "Chemical,Disease"}

    # ── Meta List / Show Helpers ──

    def _list_meta(self, subdir: str, title: str, formatter=None):
        """Generic list printer for meta directories."""
        print(f"\n{C['bold']}{title}:{C['reset']}")
        d = META_DIR / subdir
        if not d.exists():
            print(warn(f"Directory '{subdir}' not found"))
            return
        files = sorted(d.glob("*.json"))
        if not files:
            print(warn("No items found"))
            return
        for f in files:
            cfg = json.loads(f.read_text())
            if formatter:
                print(formatter(f.stem, cfg))
            else:
                print(f"  {f.stem}")

    def _show_json(self, subdir: str, entity_id: str, title: str):
        """Show a JSON entity with formatting."""
        fpath = META_DIR / subdir / f"{entity_id}.json"
        if not fpath.exists():
            print(error(f"{title} '{entity_id}' not found"))
            return
        cfg = json.loads(fpath.read_text())
        print(f"\n{C['bold']}{title}: {C['cyan']}{entity_id}{C['reset']}")
        print(code_block(json.dumps(cfg, indent=2, ensure_ascii=False)))

    def _show_dataset(self, dataset_id: str):
        """Show dataset info."""
        # Datasets are stored as test files under tests/<runner_id>/<dataset_id>
        found = False
        tests_dir = Path(__file__).parent / "tests"
        if tests_dir.exists():
            for runner_dir in tests_dir.iterdir():
                if runner_dir.is_dir():
                    for f in runner_dir.glob("*.csv"):
                        if f.stem == dataset_id or dataset_id in f.stem:
                            print(f"\n{C['bold']}Dataset: {C['cyan']}{f.name}{C['reset']}")
                            print(f"  Runner: {runner_dir.name}")
                            print(f"  Path: {f}")
                            found = True
                    for f in runner_dir.glob("*.txt"):
                        if f.stem == dataset_id or dataset_id in f.stem:
                            print(f"\n{C['bold']}Dataset: {C['cyan']}{f.name}{C['reset']}")
                            print(f"  Runner: {runner_dir.name}")
                            print(f"  Path: {f}")
                            found = True
        if not found:
            print(error(f"Dataset '{dataset_id}' not found in tests/"))

    def _run_agent(self, agent_id: str):
        """Run a single agent interactively."""
        agent_file = META_DIR / "agents" / f"{agent_id}.json"
        if not agent_file.exists():
            print(error(f"Agent '{agent_id}' not found"))
            return

        agent = json.loads(agent_file.read_text())
        print(f"\n{C['bold']}Agent: {C['cyan']}{agent.get('name', agent_id)}{C['reset']} [{agent.get('type', '?')}]")

        inputs = {}
        for inp in agent.get("inputs", []):
            print(f"{C['yellow']}   Input '{inp}': {C['reset']}", end="")
            val = input().strip()
            if not val:
                val = self._demo_data(inp)
                print(f"   {C['dim']}(使用示例数据: {val}){C['reset']}")
            try:
                inputs[inp] = json.loads(val)
            except:
                inputs[inp] = val

        if not inputs:
            inputs = self._demo_inputs(agent_id)
            print(info("使用示例输入:", json.dumps(inputs, ensure_ascii=False)))

        result = execute_agent(agent_id, inputs)
        if result["status"] == "success":
            print(f"\n{C['bold']}{C['green']}   ✅ Agent Execution Complete{C['reset']}")
            final_state = result["result"]
            for k, v in final_state.items():
                if k in inputs:
                    continue
                if isinstance(v, (dict, list)):
                    print(f"\n   {C['bold']}{k}:{C['reset']}")
                    print(code_block(json.dumps(v, indent=4, ensure_ascii=False)))
                else:
                    print(f"   {C['bold']}{k}:{C['reset']} {str(v)[:500]}")
        else:
            print(error(f"Execution failed: {result.get('message', 'Unknown error')}"))

    def _run_experiment(self, exp_id: str):
        """Run or replay an experiment."""
        exp_file = META_DIR / "exps" / f"{exp_id}.json"
        if not exp_file.exists():
            print(error(f"Experiment '{exp_id}' not found"))
            return
        exp = json.loads(exp_file.read_text())
        print(f"\n{C['bold']}Experiment: {C['cyan']}{exp.get('name', exp_id)}{C['reset']}")
        print(f"  Runner: {exp.get('runner_display', exp.get('runner_id', 'N/A'))}")
        print(f"  Dataset: {exp.get('dataset', 'N/A')}")
        print(f"  Status: {exp.get('status', 'unknown')}")
        print(f"  Samples: {exp.get('samples', 'N/A')}")
        print(warn("Experiments are run via the Web UI. Use /run workflow <id> to run workflows directly."))

    # ── Natural Language Parsing ──

    def _parse_natural_language(self, message: str) -> Optional[str]:
        """Parse natural language into slash command. Returns command string or None."""
        msg_lower = message.lower().strip()

        # Operation keywords
        list_kw = ["列出", "list", "显示所有", "查看所有", "所有", "all of"]
        show_kw = ["显示", "查看", "show", "详情", "detail", "看看", " info"]
        run_kw = ["运行", "执行", "调用", "run", "execute", "启动", "start", "invoke"]

        entity_map = {
            "workflows": ["workflows", "workflow", "graphs", "graph", "工作流", "流程", "图"],
            "agents": ["agents", "agent", "智能体", "代理"],
            "tools": ["tools", "tool", "工具"],
            "datasets": ["datasets", "dataset", "数据集", "数据"],
            "llms": ["llms", "llm", "模型", "大模型"],
            "experiments": ["experiments", "experiment", "exps", "exp", "实验"],
        }

        # Detect operation
        op = None
        if any(k in msg_lower for k in list_kw):
            op = "list"
        elif any(k in msg_lower for k in show_kw):
            op = "show"
        elif any(k in msg_lower for k in run_kw):
            op = "run"

        if not op:
            return None

        # Detect entity type
        entity = None
        for ekey, aliases in entity_map.items():
            if any(alias in msg_lower for alias in aliases):
                entity = ekey
                break

        if not entity:
            if op in ("show", "run"):
                entity = "workflows"
            else:
                return None

        # Extract ID for show/run
        if op in ("show", "run"):
            eid = self._extract_id_from_message(message)
            if not eid:
                return None
            etype_map = {
                "workflows": "workflow",
                "agents": "agent",
                "tools": "tool",
                "datasets": "dataset",
                "llms": "llm",
                "experiments": "experiment",
            }
            return f"/{op} {etype_map[entity]} {eid}"

        return f"/list {entity}"

    def _extract_id_from_message(self, message: str) -> Optional[str]:
        """Try to extract an entity ID from natural language message."""
        # Build known IDs from all meta directories
        known_ids = set()
        for subdir in ["graphs", "agents", "tools", "llms", "exps"]:
            d = META_DIR / subdir
            if d.exists():
                known_ids.update(f.stem for f in d.glob("*.json"))

        # Check if any known ID appears verbatim in the message
        for eid in sorted(known_ids, key=len, reverse=True):
            if eid in message:
                return eid

        # Try quoted or candidate words
        parts = message.split()
        skip_words = {"运行", "执行", "调用", "run", "execute", "启动", "start", "invoke",
                      "显示", "查看", "show", "详情", "detail", "看看",
                      "列出", "list", "所有", "all", "the", "a", "an", "这个", "那个"}
        for p in parts:
            p = p.strip("\"'",)
            if p.lower() in skip_words:
                continue
            if re.match(r'^[a-zA-Z0-9_\-]+$', p) and len(p) > 1:
                return p

        return None


# ═══════════════════════════════════════════════════════════════
# Main Loop
# ═══════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", help="LLM config ID for chat parsing and generation")
    args = parser.parse_args()

    # Load autogen module
    sys.path.insert(0, str(Path(__file__).parent))
    import autogen

    cm = autogen.ConfigManager(META_DIR)
    llms = cm.load_all("llms")

    if not llms:
        print(f"{C['red']}Error: No LLM configs found.{C['reset']}")
        print(f"Create one first:")
        print(f"  echo '{{\"id\":\"kimi-2.6\",\"type\":\"openai\",\"model\":\"kimi-k2.6\",\"base_url\":\"https://api.moonshot.cn/v1\",\"api_key\":\"YOUR_KEY\",\"temperature\":0.7}}' > {META_DIR}/llms/kimi-2.6.json")
        sys.exit(1)

    # Determine which LLM to use
    last_llm_file = META_DIR / ".last_chat_llm"
    llm_id = None

    if args.llm:
        if args.llm in llms:
            llm_id = args.llm
            # Save as default for next time
            last_llm_file.write_text(llm_id)
        else:
            print(f"{C['red']}Error: LLM config '{args.llm}' not found.{C['reset']}")
            print(f"Available:")
            for f in sorted((META_DIR / "llms").glob("*.json")):
                print(f"  - {f.stem}")
            sys.exit(1)
    else:
        # Try loading last used LLM
        if last_llm_file.exists():
            saved_llm = last_llm_file.read_text().strip()
            if saved_llm and saved_llm in llms:
                llm_id = saved_llm
                print(f"{C['dim']}使用上次选择的 LLM: {llm_id}{C['reset']}")

        if not llm_id:
            # Interactive selection
            print(f"\n{C['bold']}可用的 LLM 配置:{C['reset']}")
            llm_list = sorted(llms.items(), key=lambda x: x[0])
            for i, (lid, lcfg) in enumerate(llm_list, 1):
                model = lcfg.get("model", "?")
                base = lcfg.get("base_url", "?")
                print(f"  {C['yellow']}[{i}]{C['reset']} {C['magenta']}{lid:<30}{C['reset']} [{lcfg.get('type', '?')}] {model} @ {base}")
            print(f"  {C['dim']}(输入编号或名称，或直接回车使用第一个){C['reset']}")
            print(f"{C['yellow']}> {C['reset']}", end="")
            choice = input().strip()

            if not choice:
                llm_id = llm_list[0][0]
            else:
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(llm_list):
                        llm_id = llm_list[idx][0]
                except ValueError:
                    pass

                if not llm_id and choice in llms:
                    llm_id = choice

            if not llm_id:
                print(error("未选择有效的 LLM，退出"))
                sys.exit(1)

            # Save selection for next time
            last_llm_file.write_text(llm_id)

    llm_config = llms[llm_id]

    # Initialize LLM parser
    parser = None
    try:
        parser = LLMCommandParser(llm_config)
    except Exception as e:
        print(warn(f"LLM parser 初始化失败 ({e})，将以本地模式运行"))

    # ── Initialize readline for arrow keys & backspace ──
    try:
        import readline
        # Detect libedit (macOS system Python) vs GNU readline
        _is_libedit = readline.__doc__ and 'libedit' in readline.__doc__.lower()
        _backend = 'libedit' if _is_libedit else 'gnu'

        if _is_libedit:
            # libedit (BSD) bindings
            readline.parse_and_bind('bind "^[[A" ed-previous-history')
            readline.parse_and_bind('bind "^[[B" ed-next-history')
            readline.parse_and_bind('bind "^[[C" ed-next-char')
            readline.parse_and_bind('bind "^[[D" ed-prev-char')
            readline.parse_and_bind('bind "^?" ed-delete-prev-char')
        else:
            # GNU readline bindings
            readline.parse_and_bind('"\e[A": previous-history')
            readline.parse_and_bind('"\e[B": next-history')
            readline.parse_and_bind('"\e[C": forward-char')
            readline.parse_and_bind('"\e[D": backward-char')
            readline.parse_and_bind('"\C-?": backward-delete-char')
            readline.parse_and_bind('"\C-h": backward-delete-char')

        # Enable tab completion (forces full readline init on some systems)
        readline.parse_and_bind('tab: complete')
    except ImportError:
        _backend = 'none'

    engine = ChatEngine(llm_id=llm_id, parser=parser)

    print(header())
    engine.print_bot("你好！我是 NeuraGraph Chat。我已经加载了 SKILL.md，可以直接用自然语言跟我交流。\n试试：'列出所有 agents'、'运行 bio_ner_graph'、或者'帮我生成一个提取基因实体的 agent'。")

    while True:
        try:
            print()
            message = input(prompt()).strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{C['cyan']}Goodbye! 👋{C['reset']}")
            break

        if not message:
            continue

        engine.last_input = message

        # Commands bypass LLM parser
        if message.startswith("/"):
            if not engine.handle_command(message):
                print(error(f"Unknown command: {message}"))
            continue

        # Chat (LLM-driven or fallback)
        engine.chat(message)


if __name__ == "__main__":
    main()
