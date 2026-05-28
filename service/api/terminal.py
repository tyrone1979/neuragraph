"""
service/api/terminal.py
终端程庝直接调用 service 层的统一入坣。
和 Flask 坎端共用坌一套 AgentEntity / GraphEntity / RunnerLoader。
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from service.entity.runner import RunnerLoader
from service.meta.loader import MetaLoader


class TerminalRunner:
    """终端统一执行器——直接夝用 service 层 RunnerLoader。"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def run(self, target_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        智能分坑：先尝试 agent，冝尝试 graph。
        和 Flask 坎端调用方弝完全一致。
        """
        meta_agent = MetaLoader.load("agents", target_id)
        if meta_agent and meta_agent.get("type") != "SUB":
            return self._run_agent(target_id, inputs)

        meta_graph = MetaLoader.load("graphs", target_id)
        if meta_graph:
            return self._run_graph(target_id, inputs)

        return {"status": "error", "message": f"'{target_id}' not found as agent or graph"}

    def run_agent(self, agent_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return self._run_agent(agent_id, inputs)

    def run_graph(self, graph_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return self._run_graph(graph_id, inputs)

    def _run_agent(self, agent_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        try:
            runner = RunnerLoader.load(agent_id)
            if not runner:
                return {"status": "error", "message": f"Agent '{agent_id}' not found"}
            result = runner.invoke(inputs)
            return {"status": "success", "result": result}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def _run_graph(self, graph_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        try:
            runner = RunnerLoader.load(graph_id)
            if not runner:
                return {"status": "error", "message": f"Graph '{graph_id}' not found"}
            result = runner.invoke(inputs)
            return {"status": "success", "result": result}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    # ╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝
    # Experiment Info Helpers (尝装 MetaLoader，对外隝藝实现细节)
    # ╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝

    def get_experiment_info(self, exp_id: str) -> Optional[Dict[str, Any]]:
        """获坖实验基本信杯，用于终端展示信杯头。

        Returns:
            {
                "name": str,
                "runner_id": str,
                "runner_type": str,
                "runner_display": str,
                "dataset": str,
                "samples": int,
                "exists": bool,
            }
            或 None（实验丝存在）
        """
        exp_cfg = MetaLoader.load("exps", exp_id)
        if not exp_cfg:
            return None

        return {
            "name": exp_cfg.get("name", exp_id),
            "runner_id": exp_cfg.get("runner_id", ""),
            "runner_type": exp_cfg.get("runner_type", ""),
            "runner_display": exp_cfg.get("runner_display", "") or exp_cfg.get("runner_id", ""),
            "dataset": exp_cfg.get("dataset", ""),
            "samples": exp_cfg.get("samples", 0),
            "exists": True,
        }

    def get_experiment_resume_count(self, exp_id: str) -> int:
        """获坖已完戝的样本数針（用于断点续跑杝示）。

        Returns:
            已完戝的样本数，0 表示没有已有结果或实验丝存在。
        """
        try:
            from service.result.loader import ResultLoader
            existing_results = ResultLoader.load(exp_id) or {}
            return sum(1 for k in existing_results.keys() if k.isdigit())
        except Exception:
            return 0

    # ╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝
    # Experiment Execution with Progress Bar
    # ╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝

    def run_experiment(
        self,
        exp_id: str,
        progress_callback: Optional[Callable[[int, int, float, int, int], None]] = None,
        unicode_mode: bool = True,
        color_enabled: bool = True,
    ) -> Dict[str, Any]:
        """
        执行实验并返回完整结果。

        Args:
            exp_id: 实验酝置 ID
            progress_callback: 坯选的进度回调函数
                signature: callback(current, total, elapsed, success_count, fail_count)
            unicode_mode: 是坦使用 Unicode 字符绘制进度条
            color_enabled: 是坦坯用 ANSI 颜色

        Returns:
            {
                "status": "success" | "error" | "interrupted",
                "exp_id": str,
                "total": int,
                "success": int,
                "failed": int,
                "elapsed": float,
                "message": str,
                "results": Dict,  # 最终加载的结果
            }
        """
        # ── 1. 加载实验酝置 ──
        exp_cfg = MetaLoader.load("exps", exp_id)
        if not exp_cfg:
            return {
                "status": "error",
                "exp_id": exp_id,
                "message": f"Experiment '{exp_id}' not found",
            }

        runner_id = exp_cfg.get("runner_id", "")
        dataset_file = exp_cfg.get("dataset", "")

        if not runner_id or not dataset_file:
            return {
                "status": "error",
                "exp_id": exp_id,
                "message": "Experiment config incomplete: missing runner_id or dataset",
            }

        # ── 2. 加载测试数杮 ──
        try:
            from service.entity.test import TestLoader
            fields, data = TestLoader.load_by_id_file(runner_id, dataset_file)
            total = len(data)
        except Exception as e:
            return {
                "status": "error",
                "exp_id": exp_id,
                "message": f"Failed to load dataset '{dataset_file}': {e}",
            }

        if total == 0:
            return {
                "status": "error",
                "exp_id": exp_id,
                "message": "Dataset is empty, nothing to run",
            }

        # ── 3. 加载 Runner ──
        try:
            runner = RunnerLoader.load(runner_id)
            if not runner:
                return {
                    "status": "error",
                    "exp_id": exp_id,
                    "message": f"Runner '{runner_id}' not found",
                }
        except Exception as e:
            return {
                "status": "error",
                "exp_id": exp_id,
                "message": f"Failed to load runner: {e}",
            }

        # ── 4. 检查已有结果（断点续跑）──
        try:
            from service.result.loader import ResultLoader
            existing_results = ResultLoader.load(exp_id) or {}
            completed_indices = set(int(k) for k in existing_results.keys() if k.isdigit())
        except Exception:
            existing_results = {}
            completed_indices = set()

        # ── 5. 执行循环 ──
        start_time = time.time()
        success_count = len(completed_indices)
        fail_count = 0
        interrupted = False

        # 更新状思为 running
        exp_cfg["status"] = "running"
        exp_cfg["progress"] = int(100 * success_count / total)
        exp_cfg["samples"] = total
        MetaLoader.dump("exps", exp_id, exp_cfg)

        try:
            for idx, row in enumerate(data):
                if idx in completed_indices:
                    continue

                if isinstance(row, dict):
                    input_dict = dict(row)
                else:
                    input_dict = dict(zip(fields, row))

                try:
                    result = runner.invoke(input_dict)

                    # 保存结果
                    try:
                        ResultLoader.save(exp_id, str(idx), result)
                    except Exception:
                        # Fallback：存入 history
                        if "history" not in exp_cfg:
                            exp_cfg["history"] = []
                        exp_cfg["history"].append({
                            "idx": idx,
                            "timestamp": datetime.now().isoformat(),
                            "status": "completed",
                            "result": result,
                        })

                    success_count += 1

                except Exception as exec_err:
                    fail_count += 1
                    if "history" not in exp_cfg:
                        exp_cfg["history"] = []
                    exp_cfg["history"].append({
                        "idx": idx,
                        "timestamp": datetime.now().isoformat(),
                        "status": "failed",
                        "error": str(exec_err),
                    })

                # 计算当剝进度
                current_progress = success_count + fail_count + len(completed_indices)
                progress_pct = int(100 * current_progress / total)
                exp_cfg["progress"] = progress_pct

                # 毝 10 个样本挝久化一次
                if (current_progress % 10 == 0) or (current_progress >= total):
                    MetaLoader.dump("exps", exp_id, exp_cfg)

                # 调用进度回调
                elapsed = time.time() - start_time
                if progress_callback:
                    try:
                        progress_callback(current_progress, total, elapsed, success_count, fail_count)
                    except Exception:
                        pass  # 回调异常丝影哝主浝程

        except KeyboardInterrupt:
            interrupted = True
            exp_cfg["status"] = "interrupted"
            MetaLoader.dump("exps", exp_id, exp_cfg)

        # ── 6. 最终状思更新 ──
        total_time = time.time() - start_time

        if interrupted:
            final_status = "interrupted"
        elif fail_count == 0:
            final_status = "completed"
            exp_cfg["status"] = "completed"
        else:
            final_status = "completed_with_errors"
            exp_cfg["status"] = "completed_with_errors"

        if not interrupted:
            exp_cfg["progress"] = 100
            exp_cfg["updated_at"] = datetime.now().isoformat()
            MetaLoader.dump("exps", exp_id, exp_cfg)

        # ── 7. 加载最终结果 ──
        final_results = {}
        try:
            final_results = ResultLoader.load(exp_id) or {}
        except Exception:
            pass

        return {
            "status": final_status,
            "exp_id": exp_id,
            "total": total,
            "success": success_count,
            "failed": fail_count,
            "elapsed": total_time,
            "message": f"Experiment {final_status}: {success_count}/{total} succeeded, {fail_count} failed",
            "results": final_results,
            "exp_cfg": exp_cfg,
        }

    # ╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝
    # Progress Bar Formatting Helpers (static methods)
    # ╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝╝

    @staticmethod
    def format_progress_bar(
        current: int,
        total: int,
        elapsed: float,
        width: int = 28,
        unicode_mode: bool = True,
        color_enabled: bool = True,
    ) -> str:
        """生戝格弝化的进度条字符串。

        Returns:
            包坫进度条〝百分比〝ETA 的完整状思行。
        """
        if total == 0:
            return ""

        filled = int(width * current / total)
        empty = width - filled
        pct = 100.0 * current / total

        # ANSI color helpers
        def _c(code: str) -> str:
            return code if color_enabled else ""

        GREEN = _c("[32m")
        DIM = _c("[2m")
        BOLD = _c("[1m")
        RESET = _c("[0m")
        YELLOW = _c("[33m")

        # Progress bar characters
        if unicode_mode:
            bar = f"{GREEN}{'█' * filled}{RESET}{DIM}{'░' * empty}{RESET}"
            icon = "✓"
        else:
            bar = f"{GREEN}{'#' * filled}{RESET}{DIM}{'-' * empty}{RESET}"
            icon = "*"

        # ETA calculation
        if current == 0:
            eta_str = "Elapsed: 0:00:00 | ETA: --:-- | 0.0 it/s"
        else:
            rate = current / elapsed
            remaining = total - current
            eta_seconds = remaining / rate
            eta = timedelta(seconds=int(eta_seconds))
            elapsed_td = timedelta(seconds=int(elapsed))
            eta_str = f"Elapsed: {elapsed_td} | ETA: {eta} | {rate:.1f} it/s"

        pad_len = len(str(total))
        return (
            f"   {GREEN}{icon}{RESET} [{current:>{pad_len}}/{total}] "
            f"{bar} {BOLD}{pct:5.1f}%{RESET} {DIM}{eta_str}{RESET}"
        )

    @staticmethod
    def format_experiment_summary(
        result: Dict[str, Any],
        unicode_mode: bool = True,
        color_enabled: bool = True,
    ) -> str:
        """根杮 run_experiment 返回的 result 生戝终端汇总字符串。"""
        def _c(code: str) -> str:
            return code if color_enabled else ""

        BOLD = _c("[1m")
        GREEN = _c("[32m")
        RED = _c("[31m")
        YELLOW = _c("[33m")
        DIM = _c("[2m")
        RESET = _c("[0m")
        CYAN = _c("[36m")

        hline = "─" * 60 if unicode_mode else "-" * 60
        status = result.get("status", "unknown")
        total = result.get("total", 0)
        success = result.get("success", 0)
        failed = result.get("failed", 0)
        elapsed = result.get("elapsed", 0.0)

        if status == "completed":
            status_text = f"{GREEN}COMPLETED{RESET}"
        elif status == "completed_with_errors":
            status_text = f"{YELLOW}COMPLETED WITH ERRORS{RESET}"
        elif status == "interrupted":
            status_text = f"{YELLOW}INTERRUPTED{RESET}"
        else:
            status_text = f"{RED}FAILED{RESET}"

        elapsed_str = str(timedelta(seconds=int(elapsed)))
        avg_time = elapsed / total if total > 0 else 0.0

        lines = [
            "",
            f"{BOLD}{GREEN}{hline}{RESET}",
            f"   {BOLD}Execution Summary{RESET}",
            f"   {DIM}Status:{RESET}   {status_text}",
            f"   {DIM}Total:{RESET}    {total:,} samples",
            f"   {DIM}Success:{RESET}  {GREEN}{success:,}{RESET}",
        ]
        if failed > 0:
            lines.append(f"   {DIM}Failed:{RESET}   {RED}{failed:,}{RESET}")
        lines.extend([
            f"   {DIM}Time:{RESET}     {elapsed_str}",
            f"   {DIM}Avg:{RESET}      {avg_time:.3f}s/sample",
            f"{BOLD}{GREEN}{hline}{RESET}",
        ])

        # 结果预览
        results = result.get("results", {})
        if results:
            preview_keys = list(results.keys())[:3]
            lines.append("")
            lines.append(f"   {DIM}Result preview (first {len(preview_keys)} items):{RESET}")
            for k in preview_keys:
                v = results[k]
                preview = str(v)[:80] + "..." if len(str(v)) > 80 else str(v)
                lines.append(f"   {DIM}[{k}]{RESET} {preview}")

        lines.append("")
        lines.append(f"   {DIM}Use '/show experiment {result.get('exp_id', '')}' to view full details{RESET}")

        # 使用 chr(10) 代替 "\n" 靿兝转义问题
        return chr(10).join(lines)


def draw_workflow(graph_id: str) -> str:
    """为终端绘制 workflow 结构图。"""
    meta = MetaLoader.load("graphs", graph_id)
    if not meta:
        return f"[Workflow '{graph_id}' not found]"

    nodes = meta.get("nodes", [])
    edges = meta.get("edges", [])

    lines = [f"   Workflow: {meta.get('name', graph_id)}", "   " + "-" * 50]

    # 获坖 agent 类型和坝称
    node_info = {}
    for n in nodes:
        if n in ("START", "END"):
            continue
        am = MetaLoader.load("agents", n)
        t = am.get("type", "?") if am else "?"
        name = am.get("name", n) if am else n
        node_info[n] = f"[{t}] {name}"

    # 按边顺庝展示
    edge_map = {e[0]: e[1] for e in edges if len(e) >= 2}
    lines.append("    START   -->")
    current = "START"
    while current in edge_map:
        nxt = edge_map[current]
        if nxt == "END":
            break
        lines.append(f"       --> {node_info.get(nxt, nxt)}")
        current = nxt
    lines.append("       -->  END")
    lines.append("   " + "-" * 50)
    # 使用 chr(10) 代替 "\n"
    return chr(10).join(lines)


def list_configs(name: str) -> List[Dict]:
    cfgs = MetaLoader.loads(name)
    return cfgs or []


def config_exists(name: str, cid: str) -> bool:
    return MetaLoader.exists(name, cid)


def save_config(name: str, cid: str, data: Dict) -> bool:
    return MetaLoader.dump(name, cid, data)


def load_config(name: str, cid: str) -> Optional[Dict]:
    return MetaLoader.load(name, cid)