"""Tests for optimize suggestion post-filter (redundancy + PGM guard)."""
from __future__ import annotations

from service.optimize_suggestion_filter import filter_disallowed_modifications

_VERIFY_V0010_HUMAN = (
    "Assumptions:\n"
    "1.3 if {head} appears only as a physiological/dietary state or experimental grouping "
    "(e.g. 'sodium depletion/repletion', 'volume depleted', 'fasted', 'control group') "
    "and not as a chemical administered to subjects, answer '~'.\n"
    "1.5 if {head} is used as resuscitation, rescue therapy, antidote, or treatment for {tail} "
    "and {tail} is the condition being treated rather than caused by {head}, answer '~'.\n"
    "Conditions:\n"
    "3. else if {head} is administered together with other chemical(s) as a combination/"
    "co-treatment regimen and {tail} is reported as an adverse event, answer '$'"
)

_AGENTS_CFG = {
    "relation_verify_llm": {
        "prompt_template": {"system": "Answer '$' or '~' only.", "human": _VERIFY_V0010_HUMAN},
    },
    "relation_result_to_id_pair": {
        "process": "if abs(idx - tidx) <= 50: continue  # negation near head or tail",
    },
}


def test_rejects_redundant_physiological_substance_assumption():
    mod = {
        "target_agent_id": "relation_verify_llm",
        "rationale": "Reduce FP from creatinine/serotonin as head chemical.",
        "prompt_human_append": (
            "1.6 if {head} is an endogenous substance, lab biomarker, or physiological "
            "parameter (e.g. creatinine, serotonin, norepinephrine, angiotensin) and not "
            "administered as an exogenous drug, answer '~'."
        ),
    }
    kept, rejected = filter_disallowed_modifications([mod], agents_cfg=_AGENTS_CFG)
    assert kept == []
    assert rejected[0]["filter_reason"].startswith("topic already covered")


def test_rejects_redundant_rescue_drug_assumption():
    mod = {
        "target_agent_id": "relation_verify_llm",
        "rationale": "diazepam/morphine/naloxone given as rescue therapy.",
        "prompt_human_append": (
            "1.7 if {head} is administered as treatment, antidote, rescue therapy, or "
            "supportive care (e.g. diazepam, morphine, naloxone) for {tail}, answer '~'."
        ),
    }
    kept, rejected = filter_disallowed_modifications([mod], agents_cfg=_AGENTS_CFG)
    assert kept == []
    assert "topic already covered" in rejected[0]["filter_reason"]


def test_rejects_pgm_negation_tighten_without_sample_evidence():
    mod = {
        "target_agent_id": "relation_result_to_id_pair",
        "rationale": "Require negation within 30 chars of both head and tail.",
        "process_append": "if abs(idx - tidx) <= 30 and abs(idx - hidx) <= 30: skip",
    }
    kept, rejected = filter_disallowed_modifications([mod], agents_cfg=_AGENTS_CFG)
    assert kept == []
    assert "sample index" in rejected[0]["filter_reason"]


def test_rejects_pgm_process_append():
    mod = {
        "target_agent_id": "relation_result_to_id_pair",
        "rationale": "Tighten negation guard",
        "process_append": "if abs(idx - tidx) <= 30: skip",
    }
    kept, rejected = filter_disallowed_modifications([mod], agents_cfg=_AGENTS_CFG)
    assert kept == []
    assert "PGM/process" in rejected[0]["filter_reason"]


def test_rejects_replace_biomarker_assumption_without_condition_fix():
    mod = {
        "target_agent_id": "relation_verify_llm",
        "rationale": "FP reduction from creatinine and serotonin as head.",
        "prompt_human_replace": (
            "Assumptions: 1.6 if creatinine serotonin endogenous biomarker answer ~. "
            "Conditions: 1. if caused answer $"
        ),
    }
    kept, rejected = filter_disallowed_modifications([mod], agents_cfg=_AGENTS_CFG)
    assert kept == []
    assert "1.6" in rejected[0]["filter_reason"] or "already covered" in rejected[0]["filter_reason"]
