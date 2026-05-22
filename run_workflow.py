#!/usr/bin/env python3
"""
run_workflow.py
终端 workflow 执行入口——直接调用 service/api/terminal.py。
和 Flask 后端共用同一套 service 层代码。
"""

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from service.api.terminal import TerminalRunner, draw_workflow, list_configs


def main():
    parser = argparse.ArgumentParser(description="NeuraGraph Workflow Runner (Unified)")
    parser.add_argument("--graph", "-g", help="Graph ID to execute")
    parser.add_argument("--agent", "-a", help="Agent ID to execute")
    parser.add_argument("--input", "-i", default="{}", help="JSON input string")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--list-agents", action="store_true", help="List available agents")
    parser.add_argument("--list-graphs", action="store_true", help="List available graphs")
    args = parser.parse_args()

    runner = TerminalRunner(verbose=args.verbose)

    if args.list_agents:
        agents = list_configs("agents")
        print(f"\nAvailable agents ({len(agents)}):")
        for a in agents:
            print(f"  [{a.get('type', '?'):4s}] {a['id']:30s} {a.get('name', '')}")
        return

    if args.list_graphs:
        graphs = list_configs("graphs")
        print(f"\nAvailable graphs ({len(graphs)}):")
        for g in graphs:
            print(f"  {g['id']:30s} {g.get('name', '')}")
        return

    try:
        inputs = json.loads(args.input)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid input JSON: {e}")
        sys.exit(1)

    target = args.graph or args.agent
    if not target:
        print("[ERROR] Specify --graph <id> or --agent <id>")
        sys.exit(1)

    if args.verbose and args.graph:
        print(draw_workflow(args.graph))

    result = runner.run(target, inputs)

    if result["status"] == "success":
        print(json.dumps(result["result"], indent=2, ensure_ascii=False, default=str))
    else:
        print(f"[ERROR] {result.get('message', 'Unknown error')}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
