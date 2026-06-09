"""Filter optimization suggestions that use forbidden shortcuts."""
from __future__ import annotations

import re
from typing import Any

# Topic groups already covered by relation_verify_llm v0010+ (Assumptions / Conditions).
_VERIFY_LLM_COVERED_TOPICS: tuple[tuple[str, ...], ...] = (
    (
        "physiological",
        "endogenous",
        "biomarker",
        "lab marker",
        "creatinine",
        "serotonin",
        "norepinephrine",
        "angiotensin",
        "prostaglandin",
        "sodium depletion",
        "volume depleted",
        "fasted",
        "control group",
    ),
    (
        "rescue",
        "antidote",
        "resuscitation",
        "supportive care",
        "diazepam",
        "morphine",
        "naloxone",
        "treatment for",
        "condition being treated",
    ),
    (
        "combination",
        "co-treatment",
        "co treatment",
        "regimen",
        "multi-drug",
        "multidrug",
        "component of the regimen",
    ),
)

_PGM_NEGATION_TIGHTEN_MARKERS = (
    "both head and tail",
    "within 30 char",
    "require proximity to both",
    "abs(idx - tidx) <= 30",
    "abs(idx - tidx) <= 100",
)


def _mod_text_blob(mod: dict[str, Any]) -> str:
    parts = [
        str(mod.get(k) or "")
        for k in (
            "rationale",
            "process_append",
            "process_replace",
            "prompt_system_append",
            "prompt_human_append",
            "prompt_system_replace",
            "prompt_human_replace",
        )
    ]
    return " ".join(parts).lower()


def disallowed_modification_reason(mod: dict[str, Any]) -> str:
    """Reject shortcuts that leak gold labels or use naive text position only."""
    blob = _mod_text_blob(mod)
    gold_markers = (
        "filtered_entities",
        "head_type",
        "tail_type",
        "entity type guard",
        "e.get('label')",
        'e.get("label")',
        "ent.get('label')",
        'ent.get("label")',
        "disease_is_chemical",
        "for e in entities",
        "for ent in (state.get('entities')",
        "chemical' or tail_type",
        'chemical" or tail_type',
        "type gate",
        "entity label",
        "label types are not chemical",
    )
    if any(marker in blob for marker in gold_markers):
        return "gold entity label / filtered_entities guard not allowed"
    keyword_markers = (
        "causal_keywords",
        "causal keyword",
        "keyword filter",
        "keyword-based filter",
        "full-text keyword",
        "full text keyword",
        "if any(kw in text",
        "if any(keyword in text",
    )
    if any(marker in blob for marker in keyword_markers):
        return "full-text keyword filter not allowed (hurts recall)"
    position_markers = (
        "head_pos",
        "tail_pos",
        "head_pos > tail_pos",
        "head appears after tail",
        "text.find(state.get('head'",
        'text.find(state.get("head"',
        "relation direction validation",
        "within 200 char",
        "char distance",
        "character position",
        "text order",
        "appears before the tail",
    )
    if any(marker in blob for marker in position_markers):
        return "position-only text-order heuristic not allowed"
    return ""


def _agent_prompt_blob(agents_cfg: dict[str, Any], agent_id: str) -> str:
    meta = agents_cfg.get(agent_id) if isinstance(agents_cfg, dict) else None
    if not isinstance(meta, dict):
        return ""
    pt = meta.get("prompt_template") or {}
    parts = [
        str(pt.get("system") or ""),
        str(pt.get("human") or ""),
        str(meta.get("process") or ""),
    ]
    return " ".join(parts).lower()


def _append_mostly_contained(append_text: str, existing_blob: str, *, threshold: float = 0.72) -> bool:
    append = re.sub(r"\s+", " ", (append_text or "").lower()).strip()
    if len(append) < 40:
        return False
    if append in existing_blob:
        return True
    words = [w for w in re.findall(r"[a-z0-9_{}]+", append) if len(w) >= 4]
    if len(words) < 6:
        return False
    hits = sum(1 for w in words if w in existing_blob)
    return hits / len(words) >= threshold


def _topic_covered_in_existing(mod_blob: str, existing_blob: str, topics: tuple[tuple[str, ...], ...]) -> bool:
    if not mod_blob.strip() or not existing_blob.strip():
        return False
    for group in topics:
        mod_hits = sum(1 for kw in group if kw in mod_blob)
        exist_hits = sum(1 for kw in group if kw in existing_blob)
        if mod_hits >= 2 and exist_hits >= 1:
            return True
    return False


def engineering_modification_reason(mod: dict[str, Any]) -> str:
    """Reject PGM/process/code edits — CID optimization must be biomedical prompt semantics."""
    if str(mod.get("process_append") or mod.get("process_replace") or "").strip():
        return "PGM/process code change not allowed; use biomedical prompt semantics only"
    agent_id = str(mod.get("target_agent_id") or "").strip()
    blob = _mod_text_blob(mod)
    if agent_id == "relation_result_to_id_pair" and any(
        m in blob
        for m in ("negation", "abs(idx", "proximity", "within 30", "within 50", "char", "guard")
    ):
        return "relation_result_to_id_pair engineering guard not allowed; fix relation_verify_llm prompt"
    return ""


def _mod_prompt_blob(mod: dict[str, Any]) -> str:
    parts = [
        str(mod.get("prompt_human_append") or ""),
        str(mod.get("prompt_system_append") or ""),
        str(mod.get("prompt_human_replace") or ""),
        str(mod.get("prompt_system_replace") or ""),
        str(mod.get("process_append") or ""),
    ]
    return " ".join(parts).lower()


def redundant_modification_reason(
    mod: dict[str, Any],
    agents_cfg: dict[str, Any] | None = None,
) -> str:
    """Reject modifications that duplicate rules already present in the target agent."""
    agent_id = str(mod.get("target_agent_id") or "").strip()
    if not agent_id or not isinstance(agents_cfg, dict):
        return ""
    existing = _agent_prompt_blob(agents_cfg, agent_id)
    if not existing:
        return ""

    append_parts = [
        str(mod.get("prompt_human_append") or ""),
        str(mod.get("prompt_system_append") or ""),
        str(mod.get("process_append") or ""),
    ]
    append_blob = " ".join(append_parts).lower()
    mod_blob = _mod_prompt_blob(mod)
    if not mod_blob.strip() and not append_blob.strip():
        return ""

    check_blob = mod_blob or append_blob
    if _append_mostly_contained(check_blob, existing):
        remove_rules = mod.get("prompt_human_remove_rules") or mod.get("prompt_system_remove_rules")
        if remove_rules or mod.get("prompt_human_replace") or mod.get("prompt_system_replace"):
            existing_words = set(re.findall(r"[a-z0-9_{}]+", existing))
            mod_words = set(re.findall(r"[a-z0-9_{}]+", check_blob))
            novel = [w for w in mod_words - existing_words if len(w) >= 5]
            if len(novel) >= 2:
                return ""
        return "mod largely duplicates existing agent prompt/process"

    if agent_id == "relation_verify_llm" and _topic_covered_in_existing(
        check_blob, existing, _VERIFY_LLM_COVERED_TOPICS
    ):
        adds_assumption = re.search(r"\b1\.[6-9]\b|\bassumption 1\.[6-9]", check_blob)
        touches_conditions = "conditions:" in check_blob or "condition 1" in check_blob or "condition 2" in check_blob
        if adds_assumption and not touches_conditions:
            return "topic already covered; refine existing Assumption/Condition instead of adding 1.6+"

    if agent_id == "relation_verify_llm":
        rationale = str(mod.get("rationale") or "").lower()
        fp_only = any(w in rationale for w in ("fp reduction", "reduce fp", "false positive"))
        fn_cited = bool(re.search(r"\bfn\b|false negative|sample\s*\d+", rationale))
        adds_assumption = "assumptions:" in check_blob and re.search(r"\b1\.[6-9]\b", check_blob)
        if fp_only and adds_assumption and not fn_cited:
            return "FP-only new Assumption likely hurts recall; refine existing rule or strengthen Conditions"

    assumption_markers = ("assumption", "answer '~'", "answer ~")
    if check_blob.count("1.") + check_blob.count("2.") >= 2 and any(
        m in check_blob for m in assumption_markers
    ):
        if existing.count("assumptions:") >= 1 and check_blob.count("if ") >= 2:
            if not mod.get("prompt_human_remove_rules") and not mod.get("prompt_system_remove_rules"):
                return "multiple Assumption rules without remove_rules (prefer refine one existing rule)"

    return ""


def risky_pgm_modification_reason(mod: dict[str, Any]) -> str:
    """Reject PGM negation-tightening patches without FN sample evidence."""
    agent_id = str(mod.get("target_agent_id") or "").strip()
    if agent_id != "relation_result_to_id_pair":
        return ""
    blob = _mod_text_blob(mod)
    if not any(m in blob for m in _PGM_NEGATION_TIGHTEN_MARKERS):
        return ""
    rationale = str(mod.get("rationale") or "").lower()
    if not re.search(r"\bsample\s*\d+|\barticle\s*\d+|\bidx\s*[=:]\s*\d+", rationale):
        return "PGM negation guard change requires tuning sample index in rationale"
    return ""


def filter_disallowed_modifications(
    modifications: list[dict[str, Any]],
    *,
    agents_cfg: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for mod in modifications:
        if not isinstance(mod, dict):
            continue
        reason = (
            disallowed_modification_reason(mod)
            or engineering_modification_reason(mod)
            or redundant_modification_reason(mod, agents_cfg)
            or risky_pgm_modification_reason(mod)
        )
        if reason:
            rejected.append({**mod, "filter_reason": reason})
        else:
            kept.append(mod)
    return kept, rejected
