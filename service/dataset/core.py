"""Build structured CSVs from raw gold files; outputs map via tests/<agent_id>/."""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

from service.dataset.parsers import (
    RAW_UPLOAD_DATASET,
    RAW_DIR,
    article_count,
    load_articles_from_source,
    resolve_source_path,
    row_options_for_source,
)
from service.dataset.rows import FORMAT_FIELDS, ROW_BUILDERS
from service.entity.test import TestLoader, TEST_DIR

ROOT = Path(__file__).resolve().parents[2]


class DatasetCatalog:
    """Stateless helpers: source path + parser auto-detect; no dataset registry."""

    def resolve_source(self, source: str | Path) -> Path:
        return resolve_source_path(source)

    def load_articles(self, source: str | Path) -> list:
        return load_articles_from_source(source)

    def _row(self, row_opts: dict[str, str], fmt: str, art) -> dict[str, str]:
        builder = ROW_BUILDERS[fmt]
        if fmt == "pubtator":
            return builder(art, rel_label=row_opts["rel_label"])
        if fmt == "ner":
            return builder(
                art,
                relation_mode=row_opts["relation_mode"],
                default_labels=row_opts["default_labels"],
                rel_label=row_opts["rel_label"],
            )
        return builder(art, relation_mode=row_opts["relation_mode"], rel_label=row_opts["rel_label"])

    def save_structured(
        self,
        agent_id: str,
        filename: str,
        articles: list,
        *,
        source: str | Path,
        format: str = "re",
        relation_mode: str | None = None,
        rel_label: str | None = None,
        default_labels: str | None = None,
    ) -> Path:
        fmt = (format or "re").strip().lower()
        if fmt not in ROW_BUILDERS:
            raise ValueError(f"unsupported format: {format}")
        opts = row_options_for_source(source)
        if relation_mode:
            opts["relation_mode"] = relation_mode
        if rel_label:
            opts["rel_label"] = rel_label
        if default_labels:
            opts["default_labels"] = default_labels
        rows = [self._row(opts, fmt, a) for a in articles]
        return TestLoader.save_csv_rows(agent_id, filename, FORMAT_FIELDS[fmt], rows)

    def _write_mirror(
        self,
        articles: list,
        filename: str,
        *,
        source: str | Path,
        format: str,
        mirror: list[dict[str, str]] | None,
    ) -> list[dict[str, str]]:
        written: list[dict[str, str]] = []
        for entry in mirror or []:
            aid = str(entry.get("agent_id") or "").strip()
            fmt = str(entry.get("format") or format).strip().lower()
            if not aid:
                continue
            path = self.save_structured(aid, filename, articles, source=source, format=fmt)
            written.append({"agent_id": aid, "format": fmt, "path": str(path)})
        return written

    def list_raw_sources(self) -> list[dict[str, Any]]:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        out: list[dict[str, Any]] = []
        for path in sorted(RAW_DIR.glob("*.txt")):
            try:
                count = article_count(RAW_UPLOAD_DATASET, path.name)
            except Exception:
                count = None
            out.append(
                {
                    "name": path.name,
                    "source": f"data/raw/{path.name}",
                    "dataset_key": RAW_UPLOAD_DATASET,
                    "location": "data/raw",
                    "count": count,
                }
            )
        return out

    def list_agent_files(self, agent_id: str) -> list[dict[str, Any]]:
        return self._list_agent_csvs(agent_id)

    def list_split_outputs(self, agent_id: str) -> list[dict[str, Any]]:
        keywords = ("tuning", "test_remain", "__tune_", "__test_")
        rows = []
        for item in self._list_agent_csvs(agent_id):
            name = item["name"]
            if not any(k in name.lower() for k in keywords):
                continue
            kind = "tuning" if "tuning" in name.lower() or "tune" in name.lower() else "test"
            rows.append({**item, "kind": kind, "agent_id": agent_id})
        return rows

    def registry(self, source: str | Path, agent_id: str | None = None) -> dict[str, Any]:
        source_path = resolve_source_path(source)
        articles = load_articles_from_source(source_path)
        try:
            rel = str(source_path.relative_to(ROOT))
        except ValueError:
            rel = str(source_path)
        out: dict[str, Any] = {
            "source": rel,
            "source_raw": {"path": rel, "count": len(articles)},
            "row_options": row_options_for_source(source_path),
        }
        if agent_id:
            out["agent_id"] = agent_id
            out["test_files"] = self._list_agent_csvs(agent_id)
        return out

    def build_full(
        self,
        agent_id: str,
        *,
        source: str | Path,
        format: str = "re",
        output_name: str | None = None,
        mirror: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        source_path = resolve_source_path(source)
        articles = load_articles_from_source(source_path)
        stem = source_path.stem.replace(".", "_")
        out = output_name or f"{stem}_full.csv"
        path = self.save_structured(agent_id, out, articles, source=source_path, format=format)
        result = {
            "source": str(source_path),
            "agent_id": agent_id,
            "format": format,
            "output": out,
            "path": str(path),
            "count": len(articles),
        }
        mirrored = self._write_mirror(articles, out, source=source_path, format=format, mirror=mirror)
        if mirrored:
            result["mirror"] = mirrored
        return result

    def build_tuning(
        self,
        agent_id: str,
        *,
        source: str | Path,
        format: str = "re",
        size: int = 20,
        tuning_out: str | None = None,
        test_out: str | None = None,
        write_test_remain: bool = True,
        mirror: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        source_path = resolve_source_path(source)
        articles = load_articles_from_source(source_path)
        picked_arts, picked_idx = stratified_pick(articles, max(1, int(size)))
        stem = source_path.stem.replace(".", "_")
        tuning_name = tuning_out or f"{stem}_tuning.csv"
        test_name = test_out or f"{stem}_test_remain.csv"
        tuning_path = self.save_structured(
            agent_id, tuning_name, picked_arts, source=source_path, format=format
        )
        result: dict[str, Any] = {
            "source": str(source_path),
            "agent_id": agent_id,
            "format": format,
            "tuning_output": tuning_name,
            "tuning_path": str(tuning_path),
            "tuning_count": len(picked_arts),
            "summary": summarize_selection(articles, picked_idx),
        }
        if write_test_remain:
            remain_idx = [i for i in range(len(articles)) if i not in set(picked_idx)]
            remain_arts = [articles[i] for i in remain_idx]
            test_path = self.save_structured(
                agent_id, test_name, remain_arts, source=source_path, format=format
            )
            result["test_output"] = test_name
            result["test_path"] = str(test_path)
            result["test_count"] = len(remain_arts)
        mirrored = self._write_mirror(
            picked_arts, tuning_name, source=source_path, format=format, mirror=mirror
        )
        if write_test_remain:
            remain_idx = [i for i in range(len(articles)) if i not in set(picked_idx)]
            remain_arts = [articles[i] for i in remain_idx]
            mirrored += self._write_mirror(
                remain_arts, test_name, source=source_path, format=format, mirror=mirror
            )
        if mirrored:
            result["mirror"] = mirrored
        return result

    def extract_test(
        self,
        agent_id: str,
        output_name: str,
        *,
        source: str | Path,
        format: str = "re",
        mode: str = "remain",
        size: int | None = None,
        pmids: list[str] | None = None,
        exclude_tuning_file: str | None = None,
        exclude_tuning_agent: str | None = None,
        seed: int = 42,
        mirror: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        source_path = resolve_source_path(source)
        articles = load_articles_from_source(source_path)
        mode = (mode or "remain").strip().lower()
        exclude_agent = exclude_tuning_agent or agent_id
        excluded_texts = self._tuning_texts(exclude_agent, exclude_tuning_file) if exclude_tuning_file else set()

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
            picked = random.Random(int(seed)).sample(pool, n)
        elif mode == "stratified":
            pool = [a for a in articles if a.text.strip() not in excluded_texts]
            if not pool:
                raise ValueError("no articles available after exclude")
            n = int(size or 20)
            picked, _idx = stratified_pick(pool, max(1, min(len(pool), n)))
        else:
            raise ValueError(f"unsupported extract mode: {mode}")

        path = self.save_structured(agent_id, output_name, picked, source=source_path, format=format)
        result = {
            "source": str(source_path),
            "agent_id": agent_id,
            "format": format,
            "output": output_name,
            "path": str(path),
            "count": len(picked),
            "mode": mode,
            "exclude_tuning_file": exclude_tuning_file or None,
        }
        mirrored = self._write_mirror(picked, output_name, source=source_path, format=format, mirror=mirror)
        if mirrored:
            result["mirror"] = mirrored
        return result

    def build_pubtator_test(
        self,
        agent_id: str,
        *,
        source: str | Path,
        output_name: str | None = None,
        size: int = 10,
        seed: int = 42,
    ) -> dict[str, Any]:
        source_path = resolve_source_path(source)
        articles = [a for a in load_articles_from_source(source_path) if a.expected_relations]
        if not articles:
            raise ValueError("no articles with gold relations in source")
        n = max(1, min(int(size), len(articles)))
        picked, picked_idx = stratified_pick(articles, n)
        stem = source_path.stem.replace(".", "_")
        out = output_name or f"{stem}_{n}articles.csv"
        path = self.save_structured(agent_id, out, picked, source=source_path, format="pubtator")
        return {
            "source": str(source_path),
            "agent_id": agent_id,
            "format": "pubtator",
            "output": out,
            "path": str(path),
            "count": len(picked),
            "pmids": [a.pmid for a in picked],
            "picked_indices": picked_idx,
            "seed": int(seed),
        }

    def sample_csv(
        self,
        agent_id: str,
        source_file: str,
        output_file: str,
        *,
        size: int,
        seed: int = 42,
    ) -> dict[str, Any]:
        source_file = (source_file or "").strip()
        output_file = (output_file or "").strip()
        if not source_file.lower().endswith(".csv"):
            source_file = f"{source_file}.csv"
        if not output_file.lower().endswith(".csv"):
            output_file = f"{output_file}.csv"
        fields, rows = TestLoader.load_by_id_file(agent_id, source_file)
        row_list = [dict(r) for r in (rows or [])]
        if not row_list:
            raise ValueError(f"source dataset `{source_file}` has no rows")
        n = max(1, min(int(size), len(row_list)))
        picked = random.Random(int(seed)).sample(row_list, n)
        out_path = TestLoader.save_csv_rows(agent_id, output_file, list(fields), picked)
        return {
            "agent_id": agent_id,
            "source": source_file,
            "output": output_file,
            "path": str(out_path),
            "sample_size": n,
            "source_count": len(row_list),
            "seed": int(seed),
        }

    def preview(
        self,
        source: str | Path,
        *,
        limit: int = 20,
        offset: int = 0,
        search: str = "",
    ) -> dict[str, Any]:
        articles = load_articles_from_source(source)
        if search:
            q = search.lower()
            articles = [a for a in articles if q in a.pmid.lower() or q in a.title.lower()]
        page = [asdict(a) for a in articles[offset : offset + limit]]
        for row in page:
            row.pop("entity_link", None)
        return {"total": len(articles), "offset": offset, "limit": limit, "items": page}

    @staticmethod
    def _list_agent_csvs(agent_id: str) -> list[dict[str, Any]]:
        agent_dir = TEST_DIR / agent_id
        if not agent_dir.is_dir():
            return []
        rows: list[dict[str, Any]] = []
        for csv_path in sorted(agent_dir.glob("*.csv")):
            try:
                with csv_path.open("r", encoding="utf-8", newline="") as f:
                    count = max(0, sum(1 for _ in f) - 1)
            except Exception:
                count = None
            rows.append({"name": csv_path.name, "count": count})
        return rows

    @staticmethod
    def _tuning_texts(agent_id: str, tuning_file: str) -> set[str]:
        if not tuning_file:
            return set()
        _fields, rows = TestLoader.load_by_id_file(agent_id, tuning_file)
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
    title_hit = body_hit = False
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
            [i for i, art in enumerate(articles) if i not in used and _title_body_profile(art) == "body_only_gold"],
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
            [i for i, art in enumerate(articles) if i not in used and _ent_bucket(len(art.entities)) == ent_key],
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
