#!/usr/bin/env python3
"""Batch-invoke every meta agent on tests/<agent_id>/sample.csv (default: mock LLM, no API).

Why mock LLM by default?
- Fast, free, deterministic CI: 40+ LLM agents would otherwise need keys, quota, and minutes per run.
- This suite checks wiring (inputs, PGM/plugins, output shape/validation), not prompt quality.
- Use --live-llm to call real providers when validating prompts or model changes.

Reports: ui_tests/reports/agent_test_report_latest.{json,md}
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

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
from utils.conversion import jsonify_state  # noqa: E402

_AGENT_UNDER_TEST: str | None = None


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
        "ontology_hypernym_identify": '[{"head": "Aspirin", "tail": "heart disease", "hypernym": "Drug"}]',
        "ontology_synonym_extract": '{"Aspirin": ["acetylsalicylic acid"]}',
        "ontology_synonym_resolve": '{"Aspirin": ["acetylsalicylic acid"]}',
        "relation_dti_analyze": '{"interaction": "inhibits", "confidence": "medium"}',
        "relation_extract_llm": '["Aspirin | treats | heart disease"]',
        "relation_from_tree_llm": '[{"head": "Aspirin", "predicate": "treats", "tail": "heart disease"}]',
        "relation_verify_llm": "$",
        "report_comparator": "## Comparison\n\nBaseline and candidate reports are similar.",
        "report_experiment": "## 1) Metrics\n\n| Metric | Value |\n| --- | --- |\n| F1 | 0.5 |\n\n## 2) FN and FP Analysis\n\nSample FN noted.\n\n## 3) Agent Modification Suggestions\n\nTune relation_verify_llm prompt.",
        "report_experiment_tool": "## 1) Metrics\n\nF1=0.5\n\n## 2) FN and FP Analysis\n\nTool-assisted review complete.\n\n## 3) Agent Modification Suggestions\n\nNone.",
        "syntax_dep_parse": "1\tAspirin\taspirin\tNN\t_\t0\thead\t_\t_\t_\t_\n2\tmay\tmay\tMD\t_\t1\tadvmod\t_\t_\t_\t_\n",
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
        try:
            parsed = json.loads(str(value))
        except json.JSONDecodeError as exc:
            return False, f"plan_json is not valid JSON: {exc}"
        if "modifications" not in parsed:
            return False, "plan_json missing modifications key"

    if out_name == "mesh_ontology" and isinstance(value, dict):
        if value.get("error") and not value.get("matches"):
            return False, value.get("error", "mesh lookup failed")

    if out_name == "tuning_result" and isinstance(value, dict) and value.get("error"):
        return False, str(value["error"])

    return True, "ok"


def _load_sample_inputs(agent_id: str) -> dict[str, Any]:
    _, rows = TestLoader.load_by_id_file(agent_id, "sample.csv")
    if not rows:
        raise FileNotFoundError(f"No rows in tests/{agent_id}/sample.csv")
    return jsonify_state(dict(rows[0]))


def run_single_agent(agent_id: str, *, mock_llm: bool = True) -> AgentTestResult:
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

    _AGENT_UNDER_TEST = agent_id
    try:
        with _llm_mock_context(mock_llm and agent_type == "LLM"):
            if agent_id == "relation_extract_pubtator":
                with _pubtator_plugin_mock():
                    result = runner.invoke(inputs)
            elif agent_id == "dataset_cid_tuning_build":
                with _cid_builder_mock():
                    result = runner.invoke(inputs)
            else:
                result = runner.invoke(inputs)
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
    return AgentTestResult(
        agent_id=agent_id,
        agent_type=agent_type,
        output_name=output_name,
        status="pass" if ok else "fail",
        message=msg,
        output_preview=preview,
        duration_ms=int((time.perf_counter() - t0) * 1000),
    )


def run_all_agents(*, mock_llm: bool = True, write_datasets: bool = True) -> AgentTestReport:
    if write_datasets:
        write_all_agent_sample_csvs()

    agent_ids = sorted(p.stem for p in (ROOT / "meta" / "agents").glob("*.json"))
    report = AgentTestReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        mock_llm=mock_llm,
    )
    for agent_id in agent_ids:
        item = run_single_agent(agent_id, mock_llm=mock_llm)
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
        f"- Mock LLM: {report.mock_llm}",
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
    parser.add_argument("--no-write-datasets", action="store_true", help="Skip regenerating tests/<agent>/sample.csv")
    parser.add_argument("--agent", help="Run a single agent id")
    args = parser.parse_args(argv)

    mock_llm = not args.live_llm
    if args.agent:
        if not args.no_write_datasets:
            write_all_agent_sample_csvs()
        result = run_single_agent(args.agent, mock_llm=mock_llm)
        report = AgentTestReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            total=1,
            passed=1 if result.status == "pass" else 0,
            failed=0 if result.status == "pass" else 1,
            mock_llm=mock_llm,
            results=[result],
        )
    else:
        report = run_all_agents(mock_llm=mock_llm, write_datasets=not args.no_write_datasets)

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
