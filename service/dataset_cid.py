"""CID dataset registry, PubTator→CSV conversion, tuning/test extraction."""
from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

from data.data_parser import CIDParser
from service.entity.test import TestLoader, TEST_DIR

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
DEFAULT_SOURCE = RAW_DIR / "dev.txt"
DEFAULT_RE_RUNNER = "wf_cid_re_llm_linear"
DEFAULT_NER_RUNNER = "wf_cid_ner_llm_eval"
DEFAULT_PUBTATOR_RUNNER = "wf_re_pubtator_dev10"

RE_FIELDS = ["text", "entities", "gold_relations"]
NER_FIELDS = ["text", "labels", "gold_entities", "gold_relations"]
PUBTATOR_FIELDS = ["text", "entities", "pmid", "gold_relations"]

CID_REGISTRY: dict[str, Any] = {
    "id": "cid_dev",
    "label": "BC5CDR CID Dev (gold)",
    "source_raw": "data/raw/dev.txt",
    "runners": {
        DEFAULT_RE_RUNNER: {
            "format": "re",
            "structured_full": "cid_dev_full.csv",
            "tuning": "cid_dev_tuning_stratified.csv",
            "test": "cid_dev_test_remain.csv",
        },
        DEFAULT_NER_RUNNER: {
            "format": "ner",
            "structured_full": "cid_dev_full.csv",
            "tuning": "cid_dev_tuning_stratified.csv",
            "test": "cid_dev_test_remain.csv",
        },
        DEFAULT_PUBTATOR_RUNNER: {
            "format": "pubtator",
            "test": "cid_dev_10articles.csv",
        },
    },
}


def resolve_source_path(source: str | Path | None = None) -> Path:
    raw = Path(str(source or DEFAULT_SOURCE))
    if raw.is_file():
        return raw.resolve()
    candidates = [
        ROOT / raw,
        RAW_DIR / raw.name,
    ]
    if raw.parts and raw.parts[0] == "data":
        candidates.insert(0, ROOT / raw)
    # Legacy: dev.txt used to live at project root
    if raw.name == "dev.txt":
        candidates.append(ROOT / "dev.txt")
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(f"source dataset not found: {raw}")


def list_raw_sources() -> list[dict[str, Any]]:
    """List PubTator gold sources under data/raw/."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out: list[dict[str, Any]] = []
    for path in sorted(RAW_DIR.glob("*.txt")):
        source = f"data/raw/{path.name}"
        try:
            count = len(CIDParser(path.read_text(encoding="utf-8")).get_articles())
        except Exception:
            count = None
        out.append(
            {
                "name": path.name,
                "source": source,
                "dataset_key": "raw",
                "location": "data/raw",
                "count": count,
            }
        )
    return out


def list_split_outputs(runner_id: str) -> list[dict[str, Any]]:
    """List tuning/test CSV outputs generated from raw splits for a runner."""
    runner_dir = TEST_DIR / runner_id
    if not runner_dir.is_dir():
        return []
    keywords = ("tuning", "test_remain", "__tune_", "__test_")
    rows = []
    for csv_path in sorted(runner_dir.glob("*.csv")):
        name = csv_path.name
        if not any(k in name.lower() for k in keywords):
            continue
        try:
            with csv_path.open("r", encoding="utf-8", newline="") as f:
                count = max(0, sum(1 for _ in f) - 1)
        except Exception:
            count = None
        kind = "tuning" if "tuning" in name.lower() or "tune" in name.lower() else "test"
        rows.append({"name": name, "kind": kind, "count": count, "runner_id": runner_id})
    return rows


def load_source_articles(source: str | Path | None = None) -> list:
    path = resolve_source_path(source)
    articles = CIDParser(path.read_text(encoding="utf-8")).get_articles()
    if not articles:
        raise ValueError(f"no articles parsed from {path.name}")
    return articles


def re_row(art) -> dict[str, str]:
    entities = [{"text": e.text, "id": e.mesh, "label": e.etype} for e in art.entities]
    rel_lines = [f"{head_mesh} | {tail_mesh}" for head_mesh, tail_mesh in art.expected_relations]
    return {
        "text": art.text,
        "entities": json.dumps(entities, ensure_ascii=False),
        "gold_relations": "\n".join(rel_lines),
    }


def ner_row(art) -> dict[str, str]:
    mesh_to_text = {e.mesh: e.text for e in art.entities}
    rel_lines = []
    for head_mesh, tail_mesh in art.expected_relations:
        h = mesh_to_text.get(head_mesh, head_mesh)
        t = mesh_to_text.get(tail_mesh, tail_mesh)
        rel_lines.append(f"{h} | CID | {t}")
    return {
        "text": art.text,
        "labels": art.labels or "Chemical,Disease",
        "gold_entities": json.dumps(art.expected_entities, ensure_ascii=False),
        "gold_relations": "\n".join(rel_lines),
    }


def pubtator_row(art) -> dict[str, str]:
    """Row for PubTator RE eval: gold entities + PMID + head | CID | tail gold relations."""
    entities = [{"text": e.text, "id": e.mesh, "label": e.etype} for e in art.entities]
    mesh_to_text = {e.mesh: e.text for e in art.entities}
    rel_lines = []
    for head_mesh, tail_mesh in art.expected_relations:
        h = mesh_to_text.get(head_mesh, head_mesh)
        t = mesh_to_text.get(tail_mesh, tail_mesh)
        rel_lines.append(f"{h} | CID | {t}")
    return {
        "text": art.text,
        "entities": json.dumps(entities, ensure_ascii=False),
        "pmid": str(art.pmid),
        "gold_relations": "\n".join(rel_lines),
    }


def _runner_format(runner_id: str) -> str:
    cfg = CID_REGISTRY["runners"].get(runner_id) or {}
    return str(cfg.get("format") or "re")


def _row_fn(runner_id: str):
    fmt = _runner_format(runner_id)
    if fmt == "ner":
        return ner_row
    if fmt == "pubtator":
        return pubtator_row
    return re_row


def _fields_for(runner_id: str) -> list[str]:
    fmt = _runner_format(runner_id)
    if fmt == "ner":
        return NER_FIELDS
    if fmt == "pubtator":
        return PUBTATOR_FIELDS
    return RE_FIELDS


def save_structured(runner_id: str, filename: str, articles: list) -> Path:
    rows = [_row_fn(runner_id)(a) for a in articles]
    return TestLoader.save_csv_rows(runner_id, filename, _fields_for(runner_id), rows)


def _tuning_texts(runner_id: str, tuning_file: str) -> set[str]:
    if not tuning_file:
        return set()
    _fields, rows = TestLoader.load_by_id_file(runner_id, tuning_file)
    return {str(r.get("text") or "").strip() for r in (rows or []) if str(r.get("text") or "").strip()}


def _rel_bucket(n: int) -> str:
    if n <= 1:
        return "rel_1"
    if n == 2:
        return "rel_2"
    if n == 3:
        return "rel_3"
    if n <= 6:
        return "rel_4_6"
    return "rel_7_plus"


def _ent_bucket(n: int) -> str:
    if n <= 10:
        return "ent_low"
    if n <= 20:
        return "ent_mid"
    return "ent_high"


def _len_bucket(n: int, q33: int, q66: int) -> str:
    if n <= q33:
        return "len_short"
    if n <= q66:
        return "len_mid"
    return "len_long"


def _title_body_profile(art) -> str:
    parts = art.text.split(".", 1)
    title = parts[0].lower()
    body = parts[1].lower() if len(parts) > 1 else ""
    rels = art.expected_relations
    if not rels:
        return "no_gold"
    title_hit = False
    body_hit = False
    for head_mesh, tail_mesh in rels:
        head_texts = [e.text.lower() for e in art.entities if e.mesh == head_mesh]
        tail_texts = [e.text.lower() for e in art.entities if e.mesh == tail_mesh]
        for ht in head_texts:
            for tt in tail_texts:
                if ht in title and tt in title:
                    title_hit = True
                if ht in body and tt in body:
                    body_hit = True
    if title_hit and not body_hit:
        return "title_only_gold"
    if body_hit and not title_hit:
        return "body_only_gold"
    if title_hit and body_hit:
        return "title_body_gold"
    return "other_gold"


def stratified_pick(articles: list, sample_size: int) -> tuple[list, list[int]]:
    if sample_size >= len(articles):
        return list(articles), list(range(len(articles)))

    lengths = sorted(len(a.text) for a in articles)
    q33 = lengths[len(lengths) // 3]
    q66 = lengths[(2 * len(lengths)) // 3]

    rel_quota = {
        "rel_1": max(1, round(sample_size * 0.25)),
        "rel_2": max(1, round(sample_size * 0.20)),
        "rel_3": max(1, round(sample_size * 0.15)),
        "rel_4_6": max(1, round(sample_size * 0.20)),
        "rel_7_plus": max(1, round(sample_size * 0.20)),
    }
    total_q = sum(rel_quota.values())
    if total_q > sample_size:
        keys = list(rel_quota.keys())
        while sum(rel_quota.values()) > sample_size:
            for k in keys:
                if rel_quota[k] > 1 and sum(rel_quota.values()) > sample_size:
                    rel_quota[k] -= 1
    elif total_q < sample_size:
        rel_quota["rel_1"] += sample_size - total_q

    by_rel: dict[str, list[int]] = defaultdict(list)
    for i, art in enumerate(articles):
        by_rel[_rel_bucket(len(art.expected_relations))].append(i)

    selected: list[int] = []
    used: set[int] = set()
    ent_counts: Counter = Counter()
    profile_counts: Counter = Counter()

    def _score(idx: int) -> tuple:
        art = articles[idx]
        profile = _title_body_profile(art)
        ent_key = _ent_bucket(len(art.entities))
        profile_rank = {
            "body_only_gold": 0,
            "title_only_gold": 1,
            "title_body_gold": 2,
            "other_gold": 3,
        }.get(profile, 4)
        return (
            ent_counts[ent_key],
            profile_counts[profile],
            profile_rank,
            -len(art.text),
            idx,
        )

    def _take(idx: int) -> None:
        used.add(idx)
        selected.append(idx)
        art = articles[idx]
        ent_counts[_ent_bucket(len(art.entities))] += 1
        profile_counts[_title_body_profile(art)] += 1

    for rel_key, quota in rel_quota.items():
        pool = sorted(by_rel.get(rel_key, []), key=_score)
        picked = 0
        for idx in pool:
            if picked >= quota or len(selected) >= sample_size:
                break
            if idx in used:
                continue
            _take(idx)
            picked += 1

    if profile_counts["body_only_gold"] < 2 and len(selected) < sample_size:
        pool = sorted(
            [
                i
                for i, art in enumerate(articles)
                if i not in used and _title_body_profile(art) == "body_only_gold"
            ],
            key=_score,
        )
        for idx in pool:
            if profile_counts["body_only_gold"] >= 2 or len(selected) >= sample_size:
                break
            _take(idx)

    for ent_key in ("ent_low", "ent_mid", "ent_high"):
        if ent_counts[ent_key] >= 3 or len(selected) >= sample_size:
            continue
        pool = sorted(
            [
                i
                for i, art in enumerate(articles)
                if i not in used and _ent_bucket(len(art.entities)) == ent_key
            ],
            key=_score,
        )
        for idx in pool:
            if ent_counts[ent_key] >= 3 or len(selected) >= sample_size:
                break
            _take(idx)

    if len(selected) < sample_size:
        strata: dict[tuple, list[int]] = defaultdict(list)
        for i, art in enumerate(articles):
            if i in used:
                continue
            key = (
                _rel_bucket(len(art.expected_relations)),
                _ent_bucket(len(art.entities)),
                _len_bucket(len(art.text), q33, q66),
                _title_body_profile(art),
            )
            strata[key].append(i)
        keys = sorted(strata.keys())
        while len(selected) < sample_size and keys:
            next_keys = []
            for key in keys:
                if len(selected) >= sample_size:
                    break
                bucket = strata.get(key) or []
                while bucket:
                    idx = bucket.pop(0)
                    if idx in used:
                        continue
                    used.add(idx)
                    selected.append(idx)
                    break
                if bucket:
                    next_keys.append(key)
            keys = next_keys

    selected.sort()
    return [articles[i] for i in selected], selected


def summarize_selection(articles: list, selected_indices: list[int]) -> dict[str, Any]:
    picked = [articles[i] for i in selected_indices]
    return {
        "selected_count": len(picked),
        "relation_buckets": dict(Counter(_rel_bucket(len(a.expected_relations)) for a in picked)),
        "entity_buckets": dict(Counter(_ent_bucket(len(a.entities)) for a in picked)),
        "title_body_profiles": dict(Counter(_title_body_profile(a) for a in picked)),
        "pmids": [a.pmid for a in picked],
    }


def _csv_row_count(runner_id: str, filename: str) -> int | None:
    if not filename:
        return None
    try:
        _fields, rows = TestLoader.load_by_id_file(runner_id, filename)
        return len(rows or [])
    except Exception:
        return None


def get_registry_status(runner_id: str = DEFAULT_RE_RUNNER) -> dict[str, Any]:
    runner_cfg = CID_REGISTRY["runners"].get(runner_id, {})
    source_path = resolve_source_path(CID_REGISTRY["source_raw"])
    articles = load_source_articles(source_path)
    return {
        "registry_id": CID_REGISTRY["id"],
        "label": CID_REGISTRY["label"],
        "runner_id": runner_id,
        "source_raw": {
            "path": str(source_path.relative_to(ROOT)),
            "count": len(articles),
        },
        "structured": {
            "full": {
                "file": runner_cfg.get("structured_full", ""),
                "count": _csv_row_count(runner_id, runner_cfg.get("structured_full", "")),
            },
            "tuning": {
                "file": runner_cfg.get("tuning", ""),
                "count": _csv_row_count(runner_id, runner_cfg.get("tuning", "")),
            },
            "test": {
                "file": runner_cfg.get("test", ""),
                "count": _csv_row_count(runner_id, runner_cfg.get("test", "")),
            },
        },
    }


def build_structured_full(
    runner_id: str,
    *,
    source: str | Path | None = None,
    output_name: str | None = None,
    mirror_ner: bool = True,
) -> dict[str, Any]:
    runner_cfg = CID_REGISTRY["runners"].get(runner_id)
    if not runner_cfg:
        raise ValueError(f"unknown runner for CID registry: {runner_id}")
    articles = load_source_articles(source)
    out = output_name or runner_cfg["structured_full"]
    path = save_structured(runner_id, out, articles)
    result = {
        "runner_id": runner_id,
        "output": out,
        "path": str(path),
        "count": len(articles),
    }
    if mirror_ner and runner_id == DEFAULT_RE_RUNNER and DEFAULT_NER_RUNNER in CID_REGISTRY["runners"]:
        ner_path = save_structured(DEFAULT_NER_RUNNER, out, articles)
        result["ner_runner"] = DEFAULT_NER_RUNNER
        result["ner_path"] = str(ner_path)
    return result


def build_tuning_dataset(
    runner_id: str,
    *,
    source: str | Path | None = None,
    size: int = 20,
    tuning_out: str | None = None,
    test_out: str | None = None,
    write_test_remain: bool = True,
    mirror_ner: bool = True,
) -> dict[str, Any]:
    runner_cfg = CID_REGISTRY["runners"].get(runner_id)
    if not runner_cfg:
        raise ValueError(f"unknown runner for CID registry: {runner_id}")
    articles = load_source_articles(source)
    picked_arts, picked_idx = stratified_pick(articles, max(1, int(size)))
    tuning_name = tuning_out or runner_cfg["tuning"]
    test_name = test_out or runner_cfg["test"]
    tuning_path = save_structured(runner_id, tuning_name, picked_arts)
    summary = summarize_selection(articles, picked_idx)
    result: dict[str, Any] = {
        "runner_id": runner_id,
        "tuning_output": tuning_name,
        "tuning_path": str(tuning_path),
        "tuning_count": len(picked_arts),
        "summary": summary,
    }
    if write_test_remain:
        remain_idx = [i for i in range(len(articles)) if i not in set(picked_idx)]
        remain_arts = [articles[i] for i in remain_idx]
        test_path = save_structured(runner_id, test_name, remain_arts)
        result["test_output"] = test_name
        result["test_path"] = str(test_path)
        result["test_count"] = len(remain_arts)
    if mirror_ner and runner_id == DEFAULT_RE_RUNNER and DEFAULT_NER_RUNNER in CID_REGISTRY["runners"]:
        save_structured(DEFAULT_NER_RUNNER, tuning_name, picked_arts)
        if write_test_remain:
            remain_idx = [i for i in range(len(articles)) if i not in set(picked_idx)]
            save_structured(DEFAULT_NER_RUNNER, test_name, [articles[i] for i in remain_idx])
        result["ner_runner"] = DEFAULT_NER_RUNNER
    return result


def extract_test_dataset(
    runner_id: str,
    output_name: str,
    *,
    source: str | Path | None = None,
    mode: str = "remain",
    size: int | None = None,
    pmids: list[str] | None = None,
    exclude_tuning_file: str | None = None,
    exclude_tuning_runner: str | None = None,
    seed: int = 42,
    mirror_ner: bool = True,
) -> dict[str, Any]:
    articles = load_source_articles(source)
    mode = (mode or "remain").strip().lower()
    exclude_runner = exclude_tuning_runner or runner_id
    exclude_file = exclude_tuning_file or CID_REGISTRY["runners"].get(runner_id, {}).get("tuning", "")
    excluded_texts = _tuning_texts(exclude_runner, exclude_file) if exclude_file else set()

    if mode == "full":
        picked = list(articles)
    elif mode == "pmids":
        want = {str(p).strip() for p in (pmids or []) if str(p).strip()}
        if not want:
            raise ValueError("mode=pmids requires pmids")
        picked = [a for a in articles if a.pmid in want]
        if not picked:
            raise ValueError(f"no articles matched pmids: {sorted(want)}")
    elif mode == "remain":
        picked = [a for a in articles if a.text.strip() not in excluded_texts]
        if not picked:
            raise ValueError("remain mode produced empty test set (check exclude_tuning_file)")
    elif mode in ("random", "count"):
        pool = [a for a in articles if a.text.strip() not in excluded_texts]
        if not pool:
            raise ValueError("no articles available after exclude")
        n = int(size or len(pool))
        n = max(1, min(len(pool), n))
        rng = random.Random(int(seed))
        picked = rng.sample(pool, n)
    elif mode == "stratified":
        pool = [a for a in articles if a.text.strip() not in excluded_texts]
        if not pool:
            raise ValueError("no articles available after exclude")
        n = int(size or 20)
        picked, _idx = stratified_pick(pool, max(1, min(len(pool), n)))
    else:
        raise ValueError(f"unsupported extract mode: {mode}")

    path = save_structured(runner_id, output_name, picked)
    result = {
        "runner_id": runner_id,
        "output": output_name,
        "path": str(path),
        "count": len(picked),
        "mode": mode,
        "exclude_tuning_file": exclude_file or None,
    }
    if mirror_ner and runner_id == DEFAULT_RE_RUNNER and DEFAULT_NER_RUNNER in CID_REGISTRY["runners"]:
        ner_path = save_structured(DEFAULT_NER_RUNNER, output_name, picked)
        result["ner_runner"] = DEFAULT_NER_RUNNER
        result["ner_path"] = str(ner_path)
    return result


def build_pubtator_test_dataset(
    runner_id: str = DEFAULT_PUBTATOR_RUNNER,
    output_name: str | None = None,
    *,
    source: str | Path | None = None,
    size: int = 10,
    seed: int = 42,
) -> dict[str, Any]:
    """Build a PubTator RE eval CSV from BC5CDR dev.txt (no tuning split)."""
    runner_cfg = CID_REGISTRY["runners"].get(runner_id)
    if not runner_cfg or _runner_format(runner_id) != "pubtator":
        raise ValueError(f"runner {runner_id} is not registered for pubtator format")
    articles = [a for a in load_source_articles(source) if a.expected_relations]
    if not articles:
        raise ValueError("no articles with gold CID relations in source")
    n = max(1, min(int(size), len(articles)))
    picked, picked_idx = stratified_pick(articles, n)
    out = output_name or runner_cfg.get("test") or f"cid_dev_{n}articles.csv"
    path = save_structured(runner_id, out, picked)
    return {
        "runner_id": runner_id,
        "output": out,
        "path": str(path),
        "count": len(picked),
        "pmids": [a.pmid for a in picked],
        "picked_indices": picked_idx,
        "source": str(resolve_source_path(source)),
        "seed": int(seed),
    }


def sample_agent_csv_dataset(
    runner_id: str,
    source_file: str,
    output_file: str,
    *,
    size: int,
    seed: int = 42,
) -> dict[str, Any]:
    """Randomly sample N unique rows from an existing agent CSV testset."""
    source_file = (source_file or "").strip()
    output_file = (output_file or "").strip()
    if not source_file.lower().endswith(".csv"):
        source_file = f"{source_file}.csv"
    if not output_file.lower().endswith(".csv"):
        output_file = f"{output_file}.csv"
    fields, rows = TestLoader.load_by_id_file(runner_id, source_file)
    row_list = [dict(r) for r in (rows or [])]
    if not row_list:
        raise ValueError(f"source dataset `{source_file}` has no rows")
    n = max(1, min(int(size), len(row_list)))
    rng = random.Random(int(seed))
    picked = rng.sample(row_list, n)
    out_path = TestLoader.save_csv_rows(runner_id, output_file, list(fields), picked)
    return {
        "runner_id": runner_id,
        "source": source_file,
        "output": output_file,
        "path": str(out_path),
        "sample_size": n,
        "source_count": len(row_list),
        "seed": int(seed),
    }


def raw_article_preview(limit: int = 20, offset: int = 0, search: str = "") -> dict[str, Any]:
    articles = load_source_articles()
    if search:
        q = search.lower()
        articles = [a for a in articles if q in a.pmid.lower() or q in a.title.lower()]
    total = len(articles)
    page = [asdict(a) for a in articles[offset : offset + limit]]
    for row in page:
        row.pop("entity_link", None)
    return {"total": total, "offset": offset, "limit": limit, "items": page}
