#!/usr/bin/env python3
"""Batch-invoke every meta agent on tests/<agent_id>/sample.csv.

Modes:
- Default (mock LLM): fast wiring/parse checks — does NOT catch prompt or real-model bugs.
- --live-llm: real API calls; use after prompt/parser changes (ontology_hypernym_* etc.).

Live runs pin LLM agents to deepseek or gpt-oss_120b only (--llm auto|deepseek|gpt-oss).

Reports: ui_tests/reports/agent_test_report_latest.{json,md}
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from contextlib import contextmanager, nullcontext
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from copy import deepcopy
from typing import Any, Callable
from unittest.mock import patch

from langchain_core.runnables import RunnableConfig

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

# In-process PGM (no remote sandbox required for most agents).
os.environ.setdefault("PLUGIN_SANDBOX", "0")

from plugin.plugin_loader import get_plugin as _real_get_plugin  # noqa: E402

from service.entity.agent import AgentEntity, AgentLoader  # noqa: E402
from service.entity.test import TestLoader  # noqa: E402
from service.meta.loader import MetaLoader  # noqa: E402
from ui_tests.utils.agent_sample_row_fixtures import write_all_agent_sample_csvs  # noqa: E402
from utils.conversion import jsonify_state, parse_plan_json  # noqa: E402

_AGENT_UNDER_TEST: str | None = None

# Only these providers are used for --live-llm (user-approved).
LIVE_LLM_IDS = frozenset({"deepseek", "gpt-oss_120b"})
# Prefer gpt-oss for tool-using / long JSON agents; deepseek for the rest.
LIVE_LLM_GPT_OSS_AGENTS = frozenset(
    {
        "ontology_hypernym_filter",
        "ontology_entity_link",
        "kg_triple_extract_llm",
        "ner_from_tree_llm",
        "relation_from_tree_llm",
        "syntax_dep_parse",
        "text_coreference",
    }
)


def _entities_json() -> str:
    return json.dumps(
        [
            {"text": "Aspirin", "id": "D001241", "label": "Chemical"},
            {"text": "heart disease", "id": "D006331", "label": "Disease"},
        ],
        ensure_ascii=False,
    )


def _mock_llm_content(agent_id: str) -> str:
    mocks: dict[str, str | Callable[[], str]] = {
        "agent_refiner": '{"modifications": []}',
        "kg_triple_extract_llm": '[{"head": "Aspirin", "predicate": "treats", "tail": "heart disease"}]',
        "ner_comparison_report": "## NER Comparison\n\nFlair and LLM metrics are comparable on the sample.",
        "ner_from_tree_llm": '{"Chemical": ["Aspirin"], "Disease": ["heart disease"]}',
        "ner_llm": '{"Chemical": ["Aspirin"], "Disease": ["heart disease"]}',
        "ontology_entity_link": '{"Aspirin": {"canonical": "Aspirin", "id": "D001241"}}',
        "ontology_hypernym_filter": _entities_json(),
        "ontology_synonym_resolve": '{"Aspirin": ["acetylsalicylic acid"]}',
        "relation_extract_llm": '["Aspirin | treats | heart disease"]',
        "relation_from_tree_llm": '[{"head": "Aspirin", "predicate": "treats", "tail": "heart disease"}]',
        "relation_verify_llm": "$",
        "report_comparator": "## Comparison\n\nBaseline and candidate reports are similar.",
        "report_experiment": "## 1) Metrics\n\n| Metric | Value |\n| --- | --- |\n| F1 | 0.5 |\n\n## 2) FN and FP Analysis\n\nSample FN noted.\n\n## 3) Agent Modification Suggestions\n\nTune relation_verify_llm prompt.",
        "report_experiment_tool": "## 1) Metrics\n\nF1=0.5\n\n## 2) FN and FP Analysis\n\nTool-assisted review complete.\n\n## 3) Agent Modification Suggestions\n\nNone.",
        "syntax_dep_parse": "1\tAspirin\taspirin\tNN\t_\t2\tnsubj\t_\t_\t_\t_\n2\ttreats\ttreat\tVBZ\t_\t0\troot\t_\t_\t_\t_\n3\tpain\tpain\tNN\t_\t2\tobj\t_\t_\t_\t_\n",
        "relation_from_tree_llm": "Aspirin | treats | pain",
        "text_coreference": "Aspirin may reduce the risk of heart disease.",
        "text_sentence_split": '["Aspirin may reduce the risk of heart disease.", "Lithium carbonate toxicity was reported."]',
        "text_summarize": "Aspirin may reduce heart disease risk; lithium toxicity was reported.",
        "text_word_segment": "| Aspirin | may | reduce | the | risk | of | heart | disease |",
    }
    val = mocks.get(agent_id, "mock llm output")
    return val() if callable(val) else val


@contextmanager
def _llm_mock_context(enable: bool = True):
    if not enable:
        yield
        return

    original_invoke = AgentEntity.invoke

    def patched_invoke(self, state, *args, **kwargs):  # type: ignore[no-untyped-def]
        if self.type != "LLM":
            return original_invoke(self, state, *args, **kwargs)
        agent_id = _AGENT_UNDER_TEST or getattr(self, "id", None) or ""
        content = _mock_llm_content(agent_id)
        return self._build_output_dict(content, state)

    AgentEntity.invoke = patched_invoke  # type: ignore[method-assign]
    try:
        yield
    finally:
        AgentEntity.invoke = original_invoke  # type: ignore[method-assign]


@contextmanager
def _plugin_mock(extra: dict[str, Any]):
    """Patch only exec-time get_plugin in AgentEntity (avoid plugin_loader recursion)."""

    def _getter(name: str):
        if name in extra:
            return extra[name]
        return _real_get_plugin(name)

    with patch("service.entity.agent.get_plugin", side_effect=_getter):
        yield


@contextmanager
def _cid_builder_mock():
    class _FakeBuilder:
        @staticmethod
        def build_tuning(runner_id, **kwargs):  # noqa: ANN001
            return {
                "runner_id": runner_id,
                "tuning_output": kwargs.get("tuning_out") or "cid_agent_test_tuning.csv",
                "tuning_path": f"tests/{runner_id}/cid_agent_test_tuning.csv",
                "tuning_count": int(kwargs.get("size") or 2),
                "summary": {"picked": 2, "source": kwargs.get("source")},
            }

    with _plugin_mock({"CidDatasetBuilder": _FakeBuilder()}):
        yield


@contextmanager
def _pubtator_plugin_mock():
    class _FakePubTator:
        @staticmethod
        def extract_relations(text="", pmid="", entities=None, bioconcept="chemical,disease"):  # noqa: ANN001
            _ = text, pmid, entities, bioconcept
            return {"relations": ["Aspirin | CID | heart disease"], "source": "mock"}

    with _plugin_mock({"PubTatorRelationExtractor": _FakePubTator()}):
        yield


@dataclass
class AgentTestResult:
    agent_id: str
    agent_type: str
    output_name: str
    status: str  # pass | fail | skip
    message: str
    output_preview: str = ""
    duration_ms: int = 0
    dataset: str = "sample.csv"


@dataclass
class AgentTestReport:
    generated_at: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    mock_llm: bool = True
    results: list[AgentTestResult] = field(default_factory=list)


def _preview(value: Any, limit: int = 240) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        text = str(value)
    text = text.replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _is_empty(value: Any, out_type: str) -> bool:
    out_type = (out_type or "str").lower()
    if value is None:
        return True
    if out_type in ("str", "text"):
        return not str(value).strip()
    if out_type == "dict":
        if not value:
            return True
        if isinstance(value, dict) and value.get("error") and len(value) <= 2:
            return True
        return False
    if out_type == "list":
        return isinstance(value, list) and len(value) == 0
    if out_type == "tuple":
        return False
    return False


def _validate_output(meta: dict[str, Any], result: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(result, dict):
        return False, "invoke did not return a dict"
    if result.get("error"):
        return False, f"error field: {result['error']}"

    outputs = meta.get("outputs") or {}
    out_name = outputs.get("name")
    if not out_name:
        return False, "agent meta missing outputs.name"
    if out_name not in result:
        return False, f"missing output key {out_name!r}"

    value = result[out_name]
    out_type = outputs.get("type", "str")

    if out_name == "hypernyms":
        if not isinstance(value, list):
            return False, "hypernyms must be a list"
        junk = frozenset({"type", "text,type,mesh", "text, type, mesh"})
        for item in value:
            if isinstance(item, str):
                if item.strip().lower() in junk:
                    return False, "hypernyms contains format-hint string 'type' (parser/prompt bug)"
                return False, f"hypernyms must be dict rows, got string: {item!r}"
            if isinstance(item, dict):
                ent = (item.get("entity") or item.get("head") or "").strip()
                hyp = (item.get("hypernym") or item.get("tail") or "").strip()
                if not ent or not hyp:
                    return False, f"invalid hypernym row (need entity+hypernym): {item!r}"
            else:
                return False, f"invalid hypernym row type: {type(item).__name__}"
        return True, "ok" if value else "ok (no hypernym pairs)"

    if out_name == "plan_json":
        parsed = parse_plan_json(value)
        if not isinstance(parsed.get("modifications"), list):
            return False, "plan_json missing modifications array"
        return True, "ok"

    if out_name == "triples" and isinstance(value, list):
        if not value:
            return False, "triples list is empty"
        for item in value:
            if isinstance(item, str) and "|" not in item:
                if item.strip().upper() == "NONE":
                    return True, "ok (no triples)"
                return False, f"triple line missing pipes: {item!r}"
        return True, "ok"

    if out_name == "synonyms" and isinstance(value, str):
        if not value.strip() or value.strip().upper() == "NONE":
            return False, "synonyms output empty"
        if "|is|" not in value and "| is |" not in value.lower():
            return False, "synonyms missing pipe pairs (expected original|is|synonym)"
        return True, "ok"

    if _is_empty(value, out_type):
        return False, f"empty or invalid output for {out_name!r} ({out_type})"

    if out_name in ("metrics", "flair_metrics", "llm_metrics", "merged_metrics") and isinstance(value, dict):
        if out_name == "merged_metrics":
            if not value.get("flair_metrics") and not value.get("llm_metrics"):
                return False, "merged_metrics is empty"
        elif out_name in ("flair_metrics", "llm_metrics"):
            if int(value.get("total_entities") or 0) <= 0:
                return False, f"{out_name} has zero total_entities"
        elif not any(k in value for k in ("micro", "macro", "precision", "f1")):
            nested = value.get("metrics") if isinstance(value.get("metrics"), dict) else {}
            if not any(k in nested for k in ("precision", "recall", "f1")):
                return False, "metrics dict lacks precision/recall/f1 fields"

    if out_name == "entities" and isinstance(value, dict):
        if not any(isinstance(v, list) and len(v) > 0 for v in value.values()):
            return False, "entities dict has no mentions"

    if out_name == "plan_json":
        parsed = parse_plan_json(value)
        if not isinstance(parsed.get("modifications"), list):
            return False, "plan_json missing modifications array"

    if out_name == "mesh_ontology" and isinstance(value, dict):
        if value.get("error") and not value.get("matches"):
            return False, value.get("error", "mesh lookup failed")

    if out_name == "tuning_result" and isinstance(value, dict) and value.get("error"):
        return False, str(value["error"])

    if out_name == "filtered_entities" and isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip().lower() in ("type", "text,type,mesh"):
                return False, "filtered_entities contains format-hint junk"

    return True, "ok"


def _resolve_live_model(agent_id: str, meta: dict[str, Any], llm_flag: str) -> str:
    """Pick deepseek or gpt-oss_120b for live runs."""
    llm_flag = (llm_flag or "auto").strip().lower()
    if llm_flag in ("deepseek", "gpt-oss", "gpt-oss_120b"):
        return "gpt-oss_120b" if llm_flag.startswith("gpt") else "deepseek"
    current = str(meta.get("model") or "").strip()
    if current in LIVE_LLM_IDS:
        return current
    return "gpt-oss_120b" if agent_id in LIVE_LLM_GPT_OSS_AGENTS else "deepseek"


@contextmanager
def _live_llm_meta_context(agent_id: str, model_id: str):
    """Override agent meta model before AgentLoader.load rebuilds the entity."""
    orig_load = MetaLoader.load

    def _patched_load(category: str, item_id: str, *args: Any, **kwargs: Any):
        data = orig_load(category, item_id, *args, **kwargs)
        if category == "agents" and item_id == agent_id and data and data.get("type") == "LLM":
            data = deepcopy(data)
            data["model"] = model_id
        return data

    MetaLoader.load = _patched_load  # type: ignore[method-assign]
    try:
        yield
    finally:
        MetaLoader.load = orig_load  # type: ignore[method-assign]


def _load_sample_inputs(agent_id: str) -> dict[str, Any]:
    _, rows = TestLoader.load_by_id_file(agent_id, "sample.csv")
    if not rows:
        raise FileNotFoundError(f"No rows in tests/{agent_id}/sample.csv")
    return jsonify_state(dict(rows[0]))


def run_single_agent(
    agent_id: str,
    *,
    mock_llm: bool = True,
    live_llm: str = "auto",
) -> AgentTestResult:
    global _AGENT_UNDER_TEST
    meta = MetaLoader.load("agents", agent_id) or {}
    agent_type = meta.get("type", "?")
    output_name = (meta.get("outputs") or {}).get("name", "")

    import time

    t0 = time.perf_counter()
    try:
        inputs = _load_sample_inputs(agent_id)
    except Exception as exc:
        return AgentTestResult(
            agent_id=agent_id,
            agent_type=agent_type,
            output_name=output_name,
            status="fail",
            message=f"dataset load failed: {exc}",
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )

    live_model = _resolve_live_model(agent_id, meta, live_llm) if not mock_llm and agent_type == "LLM" else ""
    config: RunnableConfig = {
        "configurable": {"thread_id": f"agent_test_{agent_id}_{int(time.perf_counter() * 1000)}"}
    }

    def _invoke_loaded(runner: Any) -> dict[str, Any]:
        if agent_id == "relation_extract_pubtator":
            with _pubtator_plugin_mock():
                return runner.invoke(inputs, config=config)
        if agent_id == "dataset_cid_tuning_build":
            with _cid_builder_mock():
                return runner.invoke(inputs, config=config)
        return runner.invoke(inputs, config=config)

    _AGENT_UNDER_TEST = agent_id
    try:
        mock_ctx = _llm_mock_context(mock_llm and agent_type == "LLM")
        live_ctx = (
            _live_llm_meta_context(agent_id, live_model)
            if live_model
            else nullcontext()
        )
        with mock_ctx, live_ctx:
            runner = AgentLoader.load(agent_id)
            if runner is None:
                return AgentTestResult(
                    agent_id=agent_id,
                    agent_type=agent_type,
                    output_name=output_name,
                    status="fail",
                    message="AgentLoader.load returned None",
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                )
            result = _invoke_loaded(runner)
    except Exception as exc:
        return AgentTestResult(
            agent_id=agent_id,
            agent_type=agent_type,
            output_name=output_name,
            status="fail",
            message=f"invoke exception: {exc}",
            output_preview=traceback.format_exc(limit=2),
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
    finally:
        _AGENT_UNDER_TEST = None

    ok, msg = _validate_output(meta, result)
    out_key = output_name or "result"
    preview = _preview(result.get(out_key, result))
    if live_model and ok:
        msg = f"ok (live:{live_model})"
    return AgentTestResult(
        agent_id=agent_id,
        agent_type=agent_type,
        output_name=output_name,
        status="pass" if ok else "fail",
        message=msg,
        output_preview=preview,
        duration_ms=int((time.perf_counter() - t0) * 1000),
    )


def run_all_agents(
    *,
    mock_llm: bool = True,
    live_llm: str = "auto",
    write_datasets: bool = True,
) -> AgentTestReport:
    if write_datasets:
        write_all_agent_sample_csvs()

    agent_ids = sorted(p.stem for p in (ROOT / "meta" / "agents").glob("*.json"))
    report = AgentTestReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        mock_llm=mock_llm,
    )
    for agent_id in agent_ids:
        item = run_single_agent(agent_id, mock_llm=mock_llm, live_llm=live_llm)
        report.results.append(item)
        report.total += 1
        if item.status == "pass":
            report.passed += 1
        elif item.status == "skip":
            report.skipped += 1
        else:
            report.failed += 1
    return report


def write_report(report: AgentTestReport, out_dir: Path | None = None) -> tuple[Path, Path]:
    out_dir = out_dir or REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"agent_test_report_{stamp}.json"
    md_path = out_dir / f"agent_test_report_{stamp}.md"
    latest_json = out_dir / "agent_test_report_latest.json"
    latest_md = out_dir / "agent_test_report_latest.md"

    payload = asdict(report)
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")

    lines = [
        "# Agent Test Report",
        "",
        f"- Generated: {report.generated_at}",
        f"- Mock LLM: {report.mock_llm} (live = real deepseek / gpt-oss_120b only)",
        f"- Total: {report.total} | Passed: {report.passed} | Failed: {report.failed} | Skipped: {report.skipped}",
        "",
        "| Agent | Type | Status | ms | Message | Output preview |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for r in report.results:
        msg = r.message.replace("|", "\\|")
        prev = r.output_preview.replace("|", "\\|")
        lines.append(
            f"| `{r.agent_id}` | {r.agent_type} | **{r.status.upper()}** | {r.duration_ms} | {msg} | {prev} |"
        )
    md_text = "\n".join(lines) + "\n"
    md_path.write_text(md_text, encoding="utf-8")
    latest_md.write_text(md_text, encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run all agent sample tests and write ui_tests/reports/")
    parser.add_argument("--live-llm", action="store_true", help="Call real LLM APIs instead of mocks")
    parser.add_argument(
        "--llm",
        default="auto",
        choices=["auto", "deepseek", "gpt-oss"],
        help="Live run model id (only deepseek or gpt-oss_120b)",
    )
    parser.add_argument("--no-write-datasets", action="store_true", help="Skip regenerating tests/<agent>/sample.csv")
    parser.add_argument("--agent", help="Run a single agent id")
    args = parser.parse_args(argv)

    mock_llm = not args.live_llm
    if args.agent:
        if not args.no_write_datasets:
            write_all_agent_sample_csvs()
        result = run_single_agent(args.agent, mock_llm=mock_llm, live_llm=args.llm)
        report = AgentTestReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            total=1,
            passed=1 if result.status == "pass" else 0,
            failed=0 if result.status == "pass" else 1,
            mock_llm=mock_llm,
            results=[result],
        )
    else:
        report = run_all_agents(
            mock_llm=mock_llm,
            live_llm=args.llm,
            write_datasets=not args.no_write_datasets,
        )

    json_path, md_path = write_report(report)
    print(f"Report JSON: {json_path}")
    print(f"Report MD:   {md_path}")
    for r in report.results:
        mark = "PASS" if r.status == "pass" else r.status.upper()
        print(f"{mark:4}  {r.agent_id}: {r.message}")
    print(f"\nTotal {report.total}  Passed {report.passed}  Failed {report.failed}  Skipped {report.skipped}")
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
