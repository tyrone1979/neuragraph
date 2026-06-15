"""PubTator / ChemDisGene article parsers (Entity, Relation, Article)."""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


class DataParser:
    def __init__(self, text: str):
        self.text = text
        self.article_map: dict = {}

    def get_articles(self) -> list:
        return list(self.article_map.values())

    def get(self, article_id: str) -> dict:
        return self.article_map.get(article_id, {})


@dataclass(slots=True)
class Entity:
    pmid: str
    text: str
    etype: str
    mesh: str
    start: int
    end: int


@dataclass(slots=True)
class Relation:
    pmid: str
    head_mesh: str
    tail_mesh: str
    relation: str = "CID"


@dataclass
class Article:
    pmid: str
    title: str
    abstract: str
    entities: list
    res: list
    text: str | None = None
    labels: str | None = None
    expected_entities: dict = field(default_factory=dict)
    expected_relations: list = field(default_factory=list)
    entity_link: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self.text = f"{self.title} {self.abstract}"
        etypes = {ent.etype for ent in self.entities if ent.etype}
        self.labels = ",".join(sorted(etypes))
        self.expected_entities = {
            k: [ent.text for ent in self.entities if ent.etype == k] for k in etypes
        }
        for rel in self.res:
            self.expected_relations.append((rel.head_mesh, rel.tail_mesh))

        mesh_map: dict[str, set] = defaultdict(set)
        for ent in self.entities:
            mesh_map[ent.text].add(ent.mesh)

        self.entity_link = {
            text: list(meshes) if len(meshes) > 1 else list(meshes)[0]
            for text, meshes in mesh_map.items()
        }

    def get(self, key, default=None):
        d = asdict(self)
        if "." not in key:
            return d.get(key, default)
        parts = key.split(".")
        cur = d
        for p in parts:
            if isinstance(cur, dict):
                cur = cur.get(p, default)
            elif isinstance(cur, list) and p.isdigit():
                idx = int(p)
                cur = cur[idx] if 0 <= idx < len(cur) else default
            else:
                return default
        return cur


class CIDParser(DataParser):
    def __init__(self, text: str):
        super().__init__(text)
        chunks = re.split(r"\n\s*\n", text.strip())
        for chk in chunks:
            lines = [L.rstrip() for L in chk.splitlines() if L.strip()]
            pmid = lines[0].split("|", 1)[0]
            title = abstr = ""
            entities, res = [], []

            for L in lines:
                if "|t|" in L:
                    title = L.split("|t|", 1)[1]
                elif "|a|" in L:
                    abstr = L.split("|a|", 1)[1]
                elif L.count("\t") == 5:
                    _, st, en, txt, etp, mesh = L.split("\t")
                    entities.append(Entity(pmid, txt, etp, mesh, int(st), int(en)))
                elif "\tCID\t" in L:
                    _, _, chem_mesh, dis_mesh = L.split("\t")
                    res.append(Relation(pmid, chem_mesh, dis_mesh, "CID"))
            self.article_map[pmid] = Article(pmid, title, abstr, entities, res)

    def get_articles(self) -> list:
        return list(self.article_map.values())

    def get(self, doc_id: str) -> dict:
        art = self.article_map.get(doc_id)
        if not art:
            return {}
        entities = [
            {
                "text": e.text,
                "type": e.etype,
                "mesh": e.mesh,
                "position": f"{e.start}:{e.end}",
            }
            for e in art.entities
        ]
        ent_map = {e.mesh: (e.text, e.etype) for e in art.entities}
        relations = []
        for rel in art.res:
            head_txt, head_type = ent_map.get(rel.head_mesh, (rel.head_mesh, "Unknown"))
            tail_txt, tail_type = ent_map.get(rel.tail_mesh, (rel.tail_mesh, "Unknown"))
            relations.append(
                {
                    "head_entity": head_txt,
                    "head_type": head_type,
                    "head_mesh": rel.head_mesh,
                    "relationship": rel.relation,
                    "tail_entity": tail_txt,
                    "tail_type": tail_type,
                    "tail_mesh": rel.tail_mesh,
                }
            )
        return {
            "doc_id": doc_id,
            "title": art.title,
            "abstract": art.abstract,
            "entities": entities,
            "relations": relations,
        }


def _load_tsv_relations(tsv_paths: Iterable[Path]) -> dict[str, list[Relation]]:
    """Load ChemDisGene gold relations from companion TSV files."""
    grouped: dict[str, list[Relation]] = defaultdict(list)
    seen: set[tuple[str, str, str, str]] = set()
    for tsv_path in tsv_paths:
        with tsv_path.open(newline="", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n\r")
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) < 4:
                    continue
                pmid, rel_type, head, tail = parts[0], parts[1], parts[2], parts[3]
                key = (pmid, rel_type, head, tail)
                if key in seen:
                    continue
                seen.add(key)
                grouped[pmid].append(Relation(pmid, head, tail, rel_type))
    return grouped


def _parse_pubtator_chunks(text: str) -> dict[str, tuple[str, str, list, list]]:
    article_data: dict[str, tuple[str, str, list, list]] = {}
    chunks = re.split(r"\n\s*\n", text.strip())
    for chk in chunks:
        lines = [L.rstrip() for L in chk.splitlines() if L.strip()]
        if not lines:
            continue
        pmid = lines[0].split("|", 1)[0]
        title = abstr = ""
        entities, res = [], []
        for L in lines:
            if "|t|" in L:
                title = L.split("|t|", 1)[1]
            elif "|a|" in L:
                abstr = L.split("|a|", 1)[1]
            elif L.count("\t") == 5:
                _, st, en, txt, etp, mesh = L.split("\t")
                entities.append(Entity(pmid, txt, etp, mesh, int(st), int(en)))
            elif "\tCID\t" in L:
                _, _, chem_mesh, dis_mesh = L.split("\t")
                res.append(Relation(pmid, chem_mesh, dis_mesh, "CID"))
        article_data[pmid] = (title, abstr, entities, res)
    return article_data


class ChemDisGeneParser(CIDParser):
    """PubTator article parser with companion TSV relation annotations."""

    def __init__(self, text: str, tsv_paths: list[Path] | None = None):
        DataParser.__init__(self, text)
        self.tsv_paths = list(tsv_paths or [])
        article_data = _parse_pubtator_chunks(text)
        tsv_by_pmid = _load_tsv_relations(self.tsv_paths)
        self.article_map = {}
        for pmid, (title, abstr, entities, inline_res) in article_data.items():
            res = list(inline_res)
            res.extend(tsv_by_pmid.get(pmid, []))
            self.article_map[pmid] = Article(pmid, title, abstr, entities, res)

    def get(self, doc_id: str) -> dict:
        art = self.article_map.get(doc_id)
        if not art:
            return {}
        entities = [
            {
                "text": e.text,
                "type": e.etype,
                "mesh": e.mesh,
                "position": f"{e.start}:{e.end}",
            }
            for e in art.entities
        ]
        ent_map = {e.mesh: (e.text, e.etype) for e in art.entities}
        relations = []
        for rel in art.res:
            head_txt, head_type = ent_map.get(rel.head_mesh, (rel.head_mesh, "Unknown"))
            tail_txt, tail_type = ent_map.get(rel.tail_mesh, (rel.tail_mesh, "Unknown"))
            relations.append(
                {
                    "head_entity": head_txt,
                    "head_type": head_type,
                    "head_mesh": rel.head_mesh,
                    "relationship": rel.relation,
                    "tail_entity": tail_txt,
                    "tail_type": tail_type,
                    "tail_mesh": rel.tail_mesh,
                }
            )
        return {
            "doc_id": doc_id,
            "title": art.title,
            "abstract": art.abstract,
            "entities": entities,
            "relations": relations,
        }
