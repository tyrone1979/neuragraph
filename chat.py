#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NeuraGraph Chat - Terminal workflow builder (like Kimi Code).

Usage:
    python chat.py                    # Interactive chat mode
    python chat.py --llm kimi-2.6     # Use specific LLM
    python chat.py --no-unicode       # Disable emoji for Windows CMD/GBK terminals
"""

import json
import os
import re
import sys
import subprocess
import textwrap
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Terminal Encoding: Force UTF-8 on Windows to prevent GBK errors ──
def _force_utf8_stdout():
    import io
    if sys.stdout.encoding != 'utf-8':
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        except (AttributeError, io.UnsupportedOperation):
            pass
    if sys.stderr.encoding != 'utf-8':
        try:
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        except (AttributeError, io.UnsupportedOperation):
            pass

_force_utf8_stdout()

# ── Terminal Capability Detection (Windows CMD/GBK support) ──
_TERMINAL_UNICODE = True
_TERMINAL_COLOR = True

def _detect_terminal_caps():
    global _TERMINAL_UNICODE, _TERMINAL_COLOR

    # Explicit override via env var or CLI arg
    if '--no-unicode' in sys.argv or os.environ.get('CHAT_NO_UNICODE'):
        _TERMINAL_UNICODE = False

    if '--no-color' in sys.argv or os.environ.get('NO_COLOR'):
        _TERMINAL_COLOR = False
        return

    # Windows detection
    if os.name == 'nt' or sys.platform == 'win32':
        # Check for modern terminals (Windows Terminal, VS Code, etc.)
        modern_term = bool(
            os.environ.get('WT_SESSION') or           # Windows Terminal
            os.environ.get('ConEmuANSI') == 'ON' or   # ConEmu
            os.environ.get('ANSICON') or               # ANSICON
            os.environ.get('TERM')                     # Any TERM set
        )
        if not modern_term:
            # Legacy Windows CMD with GBK codepage
            _TERMINAL_UNICODE = False
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                if kernel32.GetConsoleOutputCP() == 936:
                    _TERMINAL_UNICODE = False
            except Exception:
                pass

_detect_terminal_caps()

# ── ANSI Colors with Windows Fallback ──
def _c(code: str) -> str:
    """Return ANSI escape code or empty string if colors disabled."""
    if not _TERMINAL_COLOR:
        return ""
    return code

def _u(emoji: str, ascii_fallback: str = "") -> str:
    """Return emoji or ASCII fallback if Unicode not supported."""
    if _TERMINAL_UNICODE:
        return emoji
    return ascii_fallback

# Color definitions
C = {
    "reset":   _c("\033[0m"),
    "bold":    _c("\033[1m"),
    "dim":     _c("\033[2m"),
    "red":     _c("\033[31m"),
    "green":   _c("\033[32m"),
    "yellow":  _c("\033[33m"),
    "blue":    _c("\033[34m"),
    "magenta": _c("\033[35m"),
    "cyan":    _c("\033[36m"),
    "white":   _c("\033[37m"),
    "bg_green":    _c("\033[42m"),
    "bg_blue":     _c("\033[44m"),
    "bg_magenta":  _c("\033[45m"),
}

# Emoji aliases with fallbacks
_E = {
    "bot":   _u("\U0001F916", "[BOT]"),
    "user":  _u("\U0001F464", "[USER]"),
    "check": _u("\u2713", "[OK]"),
    "cross": _u("\u2717", "[X]"),
    "warn":  _u("!", "!"),
    "start": _u("\u25B6", ">"),
    "wave":  _u("\U0001F44B", "Bye"),
    "sparkle": _u("\u2728", "*"),
}

META_DIR = Path(__file__).parent / "meta"

# ═══════════════════════════════════════════════════════════════
# UI Primitives
# ═══════════════════════════════════════════════════════════════

def box(title: str, content: str, width: int = 60, color: str = "cyan") -> str:
    """Draw a box with title."""
    cc = C[color]
    lines = content.strip().split("\n")
    result = [f"{cc}{'+-' if not _TERMINAL_UNICODE else '┌─'}{'─' * (width - 3)}{'+ ' if not _TERMINAL_UNICODE else '┐'}{C['reset']}"]
    if title:
        result.append(f"{cc}| {C['bold']} {title:<{width-4}} {C['reset']}{cc}|{C['reset']}")
        result.append(f"{cc}{'+-' if not _TERMINAL_UNICODE else '├─'}{'─' * (width - 3)}{'+ ' if not _TERMINAL_UNICODE else '┤'}{C['reset']}")
    for line in lines:
        result.append(f"{cc}|{C['reset']} {line:<{width-4}} {cc}|{C['reset']}")
    result.append(f"{cc}{'+-' if not _TERMINAL_UNICODE else '└─'}{'─' * (width - 3)}{'+ ' if not _TERMINAL_UNICODE else '┘'}{C['reset']}")
    return "\n".join(result)


def bot(text: str) -> str:
    """Bot message."""
    return f"{C['bg_blue']}{C['bold']} {_E['bot']} {C['reset']} {C['cyan']}{text}{C['reset']}"


def user(text: str) -> str:
    """User message."""
    return f"{C['bg_green']}{C['bold']} {_E['user']} {C['reset']} {C['green']}{text}{C['reset']}"


def info(label: str, text: str = "") -> str:
    """Info line."""
    return f"{C['dim']}   {label}{C['reset']} {text}"


def success(text: str) -> str:
    return f"{C['green']}   {_E['check']} {text}{C['reset']}"


def error(text: str) -> str:
    return f"{C['red']}   {_E['cross']} {text}{C['reset']}"


def warn(text: str) -> str:
    return f"{C['yellow']}   {_E['warn']} {text}{C['reset']}"


def step(num: int, text: str) -> str:
    return f"{C['bold']}{C['yellow']}   [{num}] {text}{C['reset']}"


def code_block(text: str, lang: str = "json") -> str:
    """Format code block."""
    lines = text.strip().split("\n")
    width = min(max(len(l) for l in lines) + 4, 80)
    hline = '-' * width if not _TERMINAL_UNICODE else '─' * width
    result = [f"{C['dim']}   {hline}{C['reset']}"]
    for line in lines[:50]:  # Limit lines
        result.append(f"{C['dim']}   |{C['reset']} {line}")
    result.append(f"{C['dim']}   {hline}{C['reset']}")
    return "\n".join(result)


def header() -> str:
    border = ('+-' if not _TERMINAL_UNICODE else '') + '=' * 60 + ('-+' if not _TERMINAL_UNICODE else '')
    return f"""
{C['bold']}{C['cyan']}{'=' if _TERMINAL_UNICODE else '+'}{'=' * 60}{'=' if _TERMINAL_UNICODE else '+'}{C['reset']}
{'|' if not _TERMINAL_UNICODE else ''}  {_E['sparkle']} NeuraGraph Chat - Terminal Workflow Builder{' ' * (24 if _TERMINAL_UNICODE else 19)}{'|' if not _TERMINAL_UNICODE else ''}
{'|' if not _TERMINAL_UNICODE else ''}  {C['dim']}Type commands: /help, /list, /run, /show, /exit{C['cyan']}{' ' * 10 if _TERMINAL_UNICODE else '          '}{'|' if not _TERMINAL_UNICODE else ''}{C['reset']}
{C['bold']}{C['cyan']}{'=' if _TERMINAL_UNICODE else '+'}{'=' * 60}{'=' if _TERMINAL_UNICODE else '+'}{C['reset']}"""


def prompt() -> str:
    """Return plain-text prompt. Never put ANSI codes in input() prompt."""
    return "> "


# ═══════════════════════════════════════════════════════════════
# Workflow ASCII Visualizer
# ═══════════════════════════════════════════════════════════════

def draw_workflow(graph_id: str, meta_dir: Path = META_DIR) -> str:
    """Draw ASCII workflow diagram."""
    try:
        with open(meta_dir / "graphs" / f"{graph_id}.json", encoding="utf-8") as f:
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
            with open(meta_dir / "agents" / f"{nid}.json", encoding="utf-8") as f:
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
    hline = '-' * 50 if not _TERMINAL_UNICODE else '─' * 50
    lines.append(f"{C['dim']}   {hline}{C['reset']}")

    lines.append(f"   {C['green']} START {C['reset']}  {C['dim']}-->{C['reset']}" if not _TERMINAL_UNICODE else f"   {C['green']} START {C['reset']}  {C['dim']}─┬─▶{C['reset']}")
    for i, (src, tgt) in enumerate(order):
        prefix = "   "
        if i == len(order) - 1:
            connector = f"{C['dim']}       -->{C['reset']}" if not _TERMINAL_UNICODE else f"{C['dim']}       └─▶{C['reset']}"
        else:
            connector = f"{C['dim']}       -->{C['reset']}" if not _TERMINAL_UNICODE else f"{C['dim']}       ├─▶{C['reset']}"

        agent_type = "?"
        name = tgt
        if tgt in node_info:
            match = re.match(r'\[(\w+)\] (.+)', node_info[tgt])
            if match:
                agent_type = match.group(1)
                name = match.group(2)

        type_color = {"LLM": C["blue"], "PGM": C["magenta"], "SUB": C["yellow"]}.get(agent_type, C["white"])
        lines.append(f"{connector} {type_color}[{agent_type}]{C['reset']} {name}")

    lines.append(f"   {C['dim']}       -->{C['reset']} {C['red']} END {C['reset']}" if not _TERMINAL_UNICODE else f"   {C['dim']}       └─▶{C['reset']} {C['red']} END {C['reset']}")
    lines.append(f"{C['dim']}   {hline}{C['reset']}")
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
        self.skill_path = Path(__file__).parent / "doc" / "AUTOGEN_SKILL.md"
        self.skill_context = self._load_skill()

    def _load_skill(self) -> str:
        if self.skill_path.exists():
            return self.skill_path.read_text(encoding='utf-8')
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
                    cfg = json.loads(f.read_text(encoding='utf-8'))
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
        - "create_testset"
          parameters: {{"runner_id": "workflow_or_agent_id", "filename": "testset.csv", "source_file": "optional_existing.csv", "count": 5}}
        - "create_experiment"
          parameters: {{"runner_id": "graph_id", "dataset": "dataset.csv", "runner_type": "graph"}}
        - "copy_workflow" / "copy_graph"
          parameters: {{"source_id": "workflow_id", "target_id": "new_workflow_id"}}
        - "start_optimize_loop" / "optimize_loop"
          parameters: {{"exp_id": "experiment_id", "max_updates": 1}}
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
           - Use "generate_agent" if they mention "agent", "\u667a\u80fd\u4f53", or "\u4ee3\u7406" without mentioning "workflow", "\u5de5\u4f5c\u6d41", "\u6d41\u7a0b", or "graph".
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
            thinking_emoji = _u("\U0001F4AD", "...")
            print(f"\n{C['dim']}{thinking_emoji} ", end="", flush=True)
            full_response = []

            for chunk in self.llm.chat_stream(system, user_content):
                full_response.append(chunk)

            print(C['reset'])
            buffer = "".join(full_response)
            intent = self._parse_intent_from_text(buffer)

            # Type out the thinking text character by character
            thinking = intent.get("thinking", "")
            if thinking:
                print(f"{C['dim']}{thinking_emoji} ", end="", flush=True)
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
                "response": f"LLM \u8c03\u7528\u5931\u8d25: {e}\n\u53ef\u4ee5\u8f93\u5165 /retry \u91cd\u8bd5\u3002",
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
                "response": text[:500] if text else "\u62b1\u6b49\uff0c\u6211\u6ca1\u80fd\u6b63\u786e\u89e3\u6790\u4f60\u7684\u610f\u56fe\u3002",
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
    """Execute workflow via service layer (TerminalRunner)."""
    from service.api.terminal import TerminalRunner
    runner = TerminalRunner(verbose=True)
    return runner.run(graph_id, inputs)


def execute_agent(agent_id: str, inputs: Dict) -> Dict:
    """Execute a single agent via service layer (TerminalRunner)."""
    from service.api.terminal import TerminalRunner
    runner = TerminalRunner(verbose=True)
    return runner.run_agent(agent_id, inputs)


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

        # -- /help --
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
  "List all agents"
  "Run bio_ner_graph workflow"
  "Show ner_demo details"
  "View all tools"
""")
            return True

        # -- /exit --
        if command in ("/exit", "/quit"):
            wave = _u("\U0001F44B", "Bye")
            print(f"\n{C['cyan']}Goodbye! {wave}{C['reset']}\n")
            sys.exit(0)

        # -- /retry --
        if command == "/retry":
            if not self.last_input or self.last_input == "/retry":
                self.print_bot("No previous command to retry")
                return True
            self.print_bot(f"Retrying: {self.last_input}")
            if self.last_input.startswith("/"):
                self.handle_command(self.last_input)
            else:
                # Avoid duplicate history entry: pop last user message if it matches
                if self.history and self.history[-1].get("content") == self.last_input:
                    self.history.pop()
                self.chat(self.last_input)
            return True

        # -- /delete <type> <id> --
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

        # -- /list <type> --
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
                    lambda stem, cfg: f"  {C['yellow']}{stem:<36}{C['reset']} {cfg.get('name', '')} {cfg.get('samples', '')} [{cfg.get('status', '?')}] {cfg.get('runner_id', '')}")
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

        # -- /show <type> <id>  or  /show <id> --
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

        # -- /run <type> <id>  or  /run <id> --
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

    def _list_meta(self, subdir: str, title: str, formatter):
        """List all entities in a meta subdirectory."""
        print(f"\n{C['bold']}{title}:{C['reset']}")
        meta_path = META_DIR / subdir
        found = False
        if meta_path.exists():
            for f in sorted(meta_path.glob("*.json")):
                try:
                    cfg = json.loads(f.read_text(encoding='utf-8'))
                    print(formatter(f.stem, cfg))
                    found = True
                except Exception:
                    print(f"  {C['dim']}{f.stem} (unreadable){C['reset']}")
                    found = True
        if not found:
            print(warn(f"No {subdir} found"))

    def _run_interactive(self, graph_id: str):
        """Run workflow with interactive input."""
        print(f"\n{draw_workflow(graph_id)}")

        # Collect inputs from user
        try:
            with open(META_DIR / "graphs" / f"{graph_id}.json", encoding="utf-8") as f:
                graph = json.load(f)
        except:
            print(error(f"Workflow '{graph_id}' not found"))
            return

        # Find the first agent (the one directly connected from START)
        edges = graph.get("edges", [])
        first_agents = []
        for e in edges:
            if len(e) >= 2 and e[0] == "START":
                first_agents.append(e[1])

        if not first_agents:
            print(error("Workflow has no START edge"))
            return

        # Only ask for inputs of the first agent(s)
        from service.meta.loader import MetaLoader
        inputs = {}
        for agent_id in first_agents:
            try:
                agent = MetaLoader.load("agents", agent_id)
                if not agent:
                    continue
                for inp in agent.get("inputs", []):
                    if inp not in inputs:
                        print(f"{C['yellow']}   Input '{inp}' (JSON or text): {C['reset']}", end="")
                        val = input()
                        try:
                            parsed = json.loads(val)
                            # If user entered {"inp": value}, extract value
                            if isinstance(parsed, dict) and inp in parsed and len(parsed) == 1:
                                inputs[inp] = parsed[inp]
                            else:
                                # If dict has multiple fields, use all as workflow inputs
                                if isinstance(parsed, dict):
                                    inputs.update(parsed)
                                else:
                                    inputs[inp] = parsed
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
            print(f"\n{C['bold']}{C['green']}   {_E['check']} Execution Complete{C['reset']}")

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
            print(error(f"LLM \u89e3\u6790\u5931\u8d25: {e}"))
            print(info("Tip: Type /retry to retry the last message"))
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
                    print(error(f"Unknown command: {cmd}"))
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
                self.print_bot("Please provide an agent ID")
        elif action in ("show_workflow", "show_graph"):
            gid = params.get("id", "")
            if gid:
                self.handle_command(f"/show workflow {gid}")
            else:
                self.print_bot("Please provide a workflow ID")
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
                self.print_bot("Please provide an agent ID")
        elif action in ("run_workflow", "run_graph"):
            gid = params.get("id", "")
            if gid:
                self._run_interactive(gid)
            else:
                self.print_bot("Please provide a workflow ID")
        elif action == "run_experiment":
            eid = params.get("id", "")
            if eid:
                self._run_experiment(eid)
        elif action == "generate_agent":
            req = params.get("requirement", "")
            if req:
                self._handle_build_agent(req)
            else:
                self.print_bot("Please describe the agent you want to create")
        elif action in ("generate_workflow", "generate_graph"):
            req = params.get("requirement", "")
            if req:
                self._handle_build(req)
            else:
                self.print_bot("Please describe the workflow you want to create")
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
            self.print_bot(f"Unknown action: {action}")

    def _update_meta(self, subdir: str, entity_id: str, changes: str):
        """Update an existing config via LLM."""
        if not entity_id:
            self.print_bot("Please provide the entity ID to update")
            return
        fpath = META_DIR / subdir / f"{entity_id}.json"
        if not fpath.exists():
            print(error(f"{subdir[:-1].title()} '{entity_id}' not found"))
            return

        try:
            existing = json.loads(fpath.read_text(encoding='utf-8'))
        except Exception as e:
            print(error(f"Failed to read config: {e}"))
            return

        hline = '-' * 60 if not _TERMINAL_UNICODE else '─' * 60
        print(f"\n{C['bold']}{C['yellow']}{hline}{C['reset']}")
        self.print_bot(f"Updating {entity_id}...")

        # Use LLM to generate updated config
        import autogen
        cm = autogen.ConfigManager(META_DIR)
        llm_config = cm.load_all("llms").get(self.llm_id)
        if not llm_config:
            print(error(f"LLM '{self.llm_id}' not found"))
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
            print(error(f"LLM call failed: {e}"))
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
            print(error("Cannot parse updated config from LLM response"))
            return

        # Ensure ID is preserved
        updated["id"] = entity_id

        # Save back
        try:
            fpath.write_text(json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8")
            print(success(f"Updated {entity_id}"))
            print(code_block(json.dumps(updated, indent=2, ensure_ascii=False)))
        except Exception as e:
            print(error(f"Save failed: {e}"))

        print(f"{C['bold']}{C['yellow']}{hline}{C['reset']}")

    def _delete_meta(self, subdir: str, entity_id: str):
        """Delete a config file with confirmation."""
        if not entity_id:
            self.print_bot("Please provide the entity ID to delete")
            return
        fpath = META_DIR / subdir / f"{entity_id}.json"
        if not fpath.exists():
            print(error(f"'{entity_id}' not found in {subdir}"))
            return

        hline = '-' * 60 if not _TERMINAL_UNICODE else '─' * 60
        print(f"\n{C['bold']}{C['red']}{hline}{C['reset']}")
        print(warn(f"Are you sure you want to delete {entity_id}? This cannot be undone. (y/n)"))
        print(f"{C['bold']}{C['yellow']}> {C['reset']}", end="")
        answer = input().strip().lower()
        if answer in ("y", "yes"):
            try:
                fpath.unlink()
                print(success(f"Deleted {entity_id}"))
            except Exception as e:
                print(error(f"Delete failed: {e}"))
        else:
            print(info("Delete cancelled"))
        print(f"{C['bold']}{C['red']}{hline}{C['reset']}")

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
                          "\u8bc6\u522b", "\u63d0\u53d6", "\u5206\u7c7b", "\u7ffb\u8bd1", "\u751f\u6210", "\u6784\u5efa", "\u603b\u7ed3"]
        agent_keywords = ["agent", "agents", "\u667a\u80fd\u4f53", "\u4ee3\u7406"]
        workflow_keywords = ["workflow", "workflows", "pipeline", "graph", "graphs", "\u5de5\u4f5c\u6d41", "\u6d41\u7a0b", "\u56fe"]

        is_build_request = any(kw in message.lower() for kw in build_keywords)
        is_agent_request = any(kw in message.lower() for kw in agent_keywords)
        is_workflow_request = any(kw in message.lower() for kw in workflow_keywords)

        if is_build_request:
            if is_agent_request and not is_workflow_request:
                self._handle_build_agent(message)
            else:
                self._handle_build(message)
        elif message.lower() in ("hi", "hello", "\u4f60\u597d", "\u55e8"):
            self.print_bot("Hello! I'm NeuraGraph Chat. Describe a workflow or agent to build, or type /help for commands.")
        else:
            self.print_bot("I'm not sure what you want. You can:\n   1. Describe a workflow or agent to build\n   2. Type /help for available commands")

    def _select_llm_interactive(self) -> Optional[str]:
        """Let user choose an LLM from available configs."""
        import autogen
        cm = autogen.ConfigManager(META_DIR)
        llms = cm.load_all("llms")
        if not llms:
            print(error("No LLM configs available"))
            return None
        if len(llms) == 1:
            return list(llms.keys())[0]

        print(f"\n{C['bold']}Available LLM configs:{C['reset']}")
        llm_list = sorted(llms.items(), key=lambda x: x[0])
        for i, (lid, lcfg) in enumerate(llm_list, 1):
            model = lcfg.get("model", "?")
            base = lcfg.get("base_url", "?")
            print(f"  {C['yellow']}[{i}]{C['reset']} {C['magenta']}{lid:<30}{C['reset']} [{lcfg.get('type', '?')}] {model} @ {base}")
        print(f"  {C['dim']}(Enter number or name){C['reset']}")
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

        print(warn(f"Unrecognized choice '{choice}', using default LLM"))
        return self.llm_id

    def _handle_build_agent(self, requirement: str):
        """Handle single agent building request."""
        hline = '-' * 60 if not _TERMINAL_UNICODE else '─' * 60
        print(f"\n{C['bold']}{C['yellow']}{hline}{C['reset']}")

        # Ask for LLM
        llm_id = self._select_llm_interactive()
        if not llm_id:
            return

        self.print_bot("Generating Agent...")
        import autogen
        cm = autogen.ConfigManager(META_DIR)
        llm_config = cm.load_all("llms").get(llm_id)
        if not llm_config:
            print(error(f"LLM '{llm_id}' not found"))
            return

        engine = autogen.AutoGen(llm_config, verbose=True)
        engine.cm = cm

        try:
            result = engine.generate_single_agent(requirement, llm_id)
        except Exception as e:
            print(error(f"Generation failed: {e}"))
            return

        if result.get("status") == "success":
            agent_id = result["agent_id"]
            agent_cfg = result["agent_config"]
            print(f"\n{C['bold']}{C['green']}   Agent '{agent_id}' generated successfully{C['reset']}")
            print(code_block(json.dumps(agent_cfg, indent=2, ensure_ascii=False)))
            print(info("You can now run it with: /run agent " + agent_id))
        else:
            print(error(f"Generation failed: {result.get('message', 'Unknown error')}"))

        print(f"{C['bold']}{C['yellow']}{hline}{C['reset']}")

    def _handle_build(self, requirement: str):
        """Handle workflow building request."""
        hline = '-' * 60 if not _TERMINAL_UNICODE else '─' * 60
        print(f"\n{C['bold']}{C['yellow']}{hline}{C['reset']}")

        # Ask for LLM
        llm_id = self._select_llm_interactive()
        if not llm_id:
            return

        self.print_bot("Analyzing requirement and generating workflow...")
        import autogen
        cm = autogen.ConfigManager(META_DIR)
        llm_config = cm.load_all("llms").get(llm_id)
        if not llm_config:
            print(error(f"LLM '{llm_id}' not found"))
            return

        engine = autogen.AutoGen(llm_config, verbose=True)
        engine.cm = cm

        # Run full pipeline
        try:
            inputs = {}
            result = engine.run(requirement, inputs=inputs, dry_run=True)
        except Exception as e:
            print(error(f"Generation failed: {e}"))
            return

        if result.get("status") == "success":
            plan = result.get("plan", {})
            graph_id = plan.get("graph_plan", {}).get("id", "")
            print(f"\n{C['bold']}{C['green']}   Workflow '{graph_id}' generated successfully{C['reset']}")

            # Show generated files
            for p in result.get("generated", []):
                print(f"   {_E['check']} {p}")

            # Show workflow diagram
            if graph_id:
                print(f"\n{draw_workflow(graph_id)}")

            print(info("You can now run it with: /run workflow " + graph_id))
        else:
            print(error(f"Generation failed: {result.get('message', 'Unknown error')}"))

        print(f"{C['bold']}{C['yellow']}{hline}{C['reset']}")

    def _run_agent(self, agent_id: str):
        """Run a single agent interactively."""
        try:
            with open(META_DIR / "agents" / f"{agent_id}.json", encoding="utf-8") as f:
                agent = json.load(f)
        except:
            print(error(f"Agent '{agent_id}' not found"))
            return

        agent_name = agent.get("name", agent_id)
        agent_type = agent.get("type", "?")
        print(f"\n{C['bold']}{agent_name}{C['reset']} [{agent_type}]")

        # Collect inputs
        inputs = {}
        for inp in agent.get("inputs", []):
            print(f"{C['yellow']}   Input '{inp}': {C['reset']}", end="")
            val = input()
            try:
                inputs[inp] = json.loads(val)
            except:
                inputs[inp] = val

        if not inputs:
            print(warn("No inputs required"))
            return

        # Execute
        print("\n" + step(1, "Executing agent: " + C["bold"] + agent_id + C["reset"]))
        result = execute_agent(agent_id, inputs)

        if result["status"] == "success":
            final_state = result["result"]
            print(f"\n{C['bold']}{C['green']}   {_E['check']} Execution Complete{C['reset']}")

            # Display outputs
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
        """Run an experiment with terminal progress bar.
        
        业务逻辑全部委托给 service/api/terminal.py 中的 TerminalRunner，
        本方法仅负责终端 UI 展示（进度条渲染、结果汇总）。
        
        注意：不直接调用 MetaLoader/ResultLoader，所有数据通过 TerminalRunner 封装方法获取。
        """
        import sys
        from service.api.terminal import TerminalRunner

        # ── 1. 初始化 Runner ──
        runner = TerminalRunner(verbose=self.verbose if hasattr(self, 'verbose') else False)

        # ── 2. 获取实验信息（通过 TerminalRunner 封装，不暴露 MetaLoader）──
        exp_info = runner.get_experiment_info(exp_id)
        if not exp_info:
            print(error(f"Experiment '{exp_id}' not found"))
            return

        # ── 3. 获取断点续跑计数（通过 TerminalRunner 封装）──
        resume_count = runner.get_experiment_resume_count(exp_id)

        # ── 4. 打印实验信息头 ──
        hline = '─' * 60 if _TERMINAL_UNICODE else '-' * 60
        print()
        print(f"{C['bold']}{C['cyan']}{hline}{C['reset']}")
        print(f"{C['bold']}   Experiment: {exp_info['name']}{C['reset']}")
        print(f"   {C['dim']}Runner:{C['reset']}    {exp_info['runner_display']} [{exp_info['runner_type']}]")
        print(f"   {C['dim']}Dataset:{C['reset']}   {exp_info['dataset']}")
        if exp_info['samples']:
            print(f"   {C['dim']}Samples:{C['reset']}   {exp_info['samples']:,}")
        if resume_count:
            print(f"   {C['dim']}Resume:{C['reset']}    {C['green']}{resume_count}{C['reset']} already completed")
        print(f"{C['bold']}{C['cyan']}{hline}{C['reset']}")

        # ── 5. 定义进度回调（负责终端进度条渲染）──
        def _progress_callback(current: int, total: int, elapsed: float, success_count: int, fail_count: int):
            """每步执行后调用，覆盖打印进度条。"""
            bar_line = TerminalRunner.format_progress_bar(
                current=current,
                total=total,
                elapsed=elapsed,
                width=28,
                unicode_mode=_TERMINAL_UNICODE,
                color_enabled=_TERMINAL_COLOR,
            )
            
            # 如果有失败，将图标改为警告
            if fail_count > 0:
                if _TERMINAL_UNICODE:
                    bar_line = bar_line.replace("✓", "!")
                else:
                    bar_line = bar_line.replace("*", "!")
                bar_line = bar_line.replace("\033[32m", "\033[33m", 1)

            # 覆盖打印同一行
            sys.stdout.write(chr(13) + bar_line)
            sys.stdout.flush()

        # ── 6. 执行实验（核心逻辑在 TerminalRunner 中）──
        try:
            result = runner.run_experiment(
                exp_id=exp_id,
                progress_callback=_progress_callback,
                unicode_mode=_TERMINAL_UNICODE,
                color_enabled=_TERMINAL_COLOR,
            )
        except KeyboardInterrupt:
            print()
            print()
            print(f"{C['yellow']}   ⚠ Interrupted by user{C['reset']}")
            return
        finally:
            print()

        # ── 7. 处理执行结果 ──
        if result["status"] == "error":
            print(error(result.get("message", "Unknown error")))
            return

        # ── 8. 打印最终汇总（使用 TerminalRunner 的格式化方法）──
        summary = TerminalRunner.format_experiment_summary(
            result=result,
            unicode_mode=_TERMINAL_UNICODE,
            color_enabled=_TERMINAL_COLOR,
        )
        print(summary)

    def _show_json(self, subdir: str, entity_id: str, label: str):
        """Show a JSON config file."""
        fpath = META_DIR / subdir / f"{entity_id}.json"
        if not fpath.exists():
            print(error(f"{label} '{entity_id}' not found"))
            return
        try:
            cfg = json.loads(fpath.read_text(encoding='utf-8'))
            print(f"\n{C['bold']}{label}: {entity_id}{C['reset']}")
            print(code_block(json.dumps(cfg, indent=2, ensure_ascii=False)))
        except Exception as e:
            print(error(f"Cannot read {label}: {e}"))

    def _show_dataset(self, dataset_id: str):
        """Show dataset info."""
        tests_dir = Path(__file__).parent / "tests"
        found = False
        if tests_dir.exists():
            for runner_dir in sorted(tests_dir.iterdir()):
                if not runner_dir.is_dir():
                    continue
                for f in sorted(runner_dir.glob("*")):
                    if f.stem == dataset_id:
                        size = f.stat().st_size
                        print(f"\n{C['bold']}Dataset: {dataset_id}{C['reset']}")
                        print(f"  Path: {f}")
                        print(f"  Size: {size} bytes")
                        found = True
                        break
                if found:
                    break
        if not found:
            print(error(f"Dataset '{dataset_id}' not found"))

    def _parse_natural_language(self, message: str) -> str:
        """Parse common natural language patterns into slash commands."""
        m = message.lower().strip()

        # List patterns
        list_patterns = [
            (r'^(list|show|display|view|all)\s+(agents?|agent)$', '/list agents'),
            (r'^(list|show|display|view|all)\s+(workflows?|graphs?|pipelines?)$', '/list workflows'),
            (r'^(list|show|display|view|all)\s+(tools?)$', '/list tools'),
            (r'^(list|show|display|view|all)\s+(llms?|models?)$', '/list llms'),
            (r'^(list|show|display|view|all)\s+(datasets?)$', '/list datasets'),
            (r'^(list|show|display|view|all)\s+(experiments?|exps?)$', '/list experiments'),
        ]
        for pattern, cmd in list_patterns:
            if re.match(pattern, m):
                return cmd

        # Run patterns
        run_patterns = [
            (r'^(run|execute|start)\s+(?:workflow|graph)\s+(\S+)$', lambda m: f"/run workflow {m.group(2)}"),
            (r'^(run|execute|start)\s+(?:agent)\s+(\S+)$', lambda m: f"/run agent {m.group(2)}"),
            (r'^(run|execute|start)\s+(\S+)$', lambda m: f"/run workflow {m.group(2)}"),
        ]
        for pattern, fn in run_patterns:
            match = re.match(pattern, m)
            if match:
                return fn(match)

        # Show patterns
        show_patterns = [
            (r'^(show|display|view|info)\s+(?:workflow|graph)\s+(\S+)$', lambda m: f"/show workflow {m.group(2)}"),
            (r'^(show|display|view|info)\s+(?:agent)\s+(\S+)$', lambda m: f"/show agent {m.group(2)}"),
        ]
        for pattern, fn in show_patterns:
            match = re.match(pattern, m)
            if match:
                return fn(match)

        return ""


def main():
    parser = argparse.ArgumentParser(description="NeuraGraph Chat - Terminal Workflow Builder")
    parser.add_argument("--llm", default="kimi-2.6", help="LLM config ID to use")
    parser.add_argument("--no-unicode", action="store_true", help="Disable emoji/Unicode for Windows CMD/GBK terminals")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    parser.add_argument("--meta-dir", default=str(META_DIR), help="Meta directory path")

    args = parser.parse_args()

    # Re-parse terminal flags if they were passed
    if args.no_unicode:
        global _TERMINAL_UNICODE
        _TERMINAL_UNICODE = False
    if args.no_color:
        global _TERMINAL_COLOR
        _TERMINAL_COLOR = False

    meta_dir = Path(args.meta_dir)

    # Show startup info
    if not _TERMINAL_UNICODE:
        print("[INFO] Unicode disabled - using ASCII fallback")
    if not _TERMINAL_COLOR:
        print("[INFO] Colors disabled")

    print(header())

    # Initialize LLM parser
    import autogen
    cm = autogen.ConfigManager(meta_dir)
    llms = cm.load_all("llms")
    llm_config = llms.get(args.llm)

    parser_obj = None
    if llm_config:
        try:
            parser_obj = LLMCommandParser(llm_config, meta_dir)
            print(f"\n   Using LLM: {C['magenta']}{args.llm}{C['reset']} [{llm_config.get('model', '?')}]")
        except Exception as e:
            print(f"   {C['yellow']}[WARN] LLM parser init failed: {e}{C['reset']}")
    else:
        print(f"   {C['yellow']}[WARN] LLM '{args.llm}' not found. Running in fallback mode.{C['reset']}")
        print(f"   Available: {', '.join(sorted(llms.keys()))}")

    # Start chat
    engine = ChatEngine(llm_id=args.llm, parser=parser_obj)

    # Welcome message
    welcome_msg = "Hello! I'm NeuraGraph Chat. Describe a workflow or agent to build, or type /help for commands."
    engine.print_bot(welcome_msg)

    while True:
        try:
            print(f"{prompt()}", end="", flush=True)
            user_input = input().strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{C['cyan']}Goodbye! {_E['wave']}{C['reset']}\n")
            break

        if not user_input:
            continue

        engine.last_input = user_input

        if user_input.startswith("/"):
            if not engine.handle_command(user_input):
                print(error(f"Unknown command: {user_input}"))
                print(info("Type /help for available commands"))
        else:
            engine.chat(user_input)


# ── Readline Support (Command History) ──
def _setup_readline():
    """Enable command history with arrow keys."""
    try:
        import readline
        histfile = Path.home() / ".neuragraph_chat_history"
        try:
            readline.read_history_file(str(histfile))
        except (FileNotFoundError, IOError):
            pass
        readline.parse_and_bind(r'"\e[A": previous-history')
        readline.parse_and_bind(r'"\e[B": next-history')
        readline.parse_and_bind(r'"\e[C": forward-char')
        readline.parse_and_bind(r'"\e[D": backward-char')
        readline.parse_and_bind(r'"\C-?": backward-delete-char')
        readline.parse_and_bind(r'"\C-h": backward-delete-char')
        import atexit
        atexit.register(lambda: readline.write_history_file(str(histfile)))
    except ImportError:
        pass  # readline not available on Windows without pyreadline3

_setup_readline()

if __name__ == "__main__":
    main()