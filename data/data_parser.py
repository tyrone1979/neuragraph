#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections import defaultdict
import re
from dataclasses import dataclass, asdict, field

class DataParser:
    def __init__(self, text: str):
        """
        Initialize the parser with raw text.
        :param text: Raw dataset text in the specific format.
        """
        self.text = text
        self.article_map = {}  # Dictionary: {article_id: parsed_document_dict}

    def get_articles(self) -> list:
        """
        Return all parsed articles as a list of dictionaries.
        :return: List of article objects.
        """
        return list(self.article_map.values())

    def get(self, article_id: str) -> dict:
        """
        Retrieve a specific article by its identifier.
        :param article_id: Unique identifier of the article (e.g., PMID).
        :return: Dictionary containing the article data.
        """
        return self.article_map.get(article_id, {})




@dataclass(slots=True)
class Entity:
    pmid: str
    text: str
    etype: str        # entity type
    mesh: str
    start: int
    end: int

@dataclass(slots=True)
class Relation:
    pmid: str
    head_mesh: str
    tail_mesh: str
    relation: str = 'CID'  # 默认化学-疾病关系

@dataclass
class Article:
    pmid: str
    title: str
    abstract: str
    entities: list
    res: list
    text: str = None
    labels: str = None# 让 dataclass 自动初始化
    expected_entities: dict = field(default_factory=dict)
    expected_relations: list = field(default_factory=list)
    entity_link: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self.text = f'{self.title} {self.abstract}'
        etypes = {ent.etype for ent in self.entities if ent.etype}
        self.labels = ','.join(sorted(etypes))
        # 按 etype 分组 text
        self.expected_entities = {
            k: [ent.text for ent in self.entities if ent.etype == k]
            for k in etypes
        }
        for rel in self.res:
            self.expected_relations.append( (rel.head_mesh, rel.tail_mesh))

        mesh_map = defaultdict(set)
        for ent in self.entities:
                mesh_map[ent.text].add(ent.mesh)

        self.entity_link = {
                text: list(meshes) if len(meshes) > 1 else list(meshes)[0]
                for text, meshes in mesh_map.items()
            }

    def get(self, key, default=None):
            """
            像 dict.get 一样访问字段。
            支持嵌套 key，例如 get('entities.0.name')。
            """
            d = asdict(self)
            if '.' not in key:
                return d.get(key, default)

            # 简单支持一层嵌套
            parts = key.split('.')
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
        chunks = re.split(r'\n\s*\n', text.strip())
        for chk in chunks:
            lines = [L.rstrip() for L in chk.splitlines() if L.strip()]
            pmid = lines[0].split('|', 1)[0]
            title = abstr = ''
            entities, res = [], []

            for L in lines:
                if '|t|' in L:
                    title = L.split('|t|', 1)[1]
                elif '|a|' in L:
                    abstr = L.split('|a|', 1)[1]
                elif L.count('\t') == 5:
                    _, st, en, txt, etp, mesh = L.split('\t')
                    entities.append(Entity(pmid, txt, etp, mesh, int(st), int(en)))
                elif '\tCID\t' in L:
                    _, _, chem_mesh, dis_mesh = L.split('\t')
                    res.append(Relation(pmid, chem_mesh, dis_mesh, 'CID'))
            self.article_map[pmid]=Article(pmid, title, abstr, entities, res)

    def get_articles(self) -> list:
        """
        Return all parsed articles as a list of dictionaries.
        :return: List of article objects.
        """
        return list(self.article_map.values())

    def get(self,doc_id: str) -> dict:
        art = self.article_map.get(doc_id)
        if not art:
            return {}
        # 1. 实体
        entities = [
            {
                'text': e.text,
                'type': e.etype,
                'mesh': e.mesh,
                'position': f'{e.start}:{e.end}'
            }
            for e in art.entities
        ]

        # 2. 建立 mesh→(text, type) 映射（仅当前文章）
        ent_map = {e.mesh: (e.text, e.etype) for e in art.entities}

        # 3. 关系（动态查找类型 & 关系名）
        relations = []
        for rel in art.res:
            head_txt, head_type = ent_map.get(rel.head_mesh, (rel.head_mesh, 'Unknown'))
            tail_txt, tail_type = ent_map.get(rel.tail_mesh, (rel.tail_mesh, 'Unknown'))
            relations.append({
                'head_entity': head_txt,
                'head_type': head_type,
                'head_mesh': rel.head_mesh,
                'relationship': rel.relation,  # 不再写死 CID
                'tail_entity': tail_txt,
                'tail_type': tail_type,
                'tail_mesh': rel.tail_mesh
            })

        return {
            'doc_id': doc_id,
            'title': art.title,
            'abstract': art.abstr,
            'entities': entities,
            'relations': relations
        }


from pathlib import Path
from typing import List
class ChemDisGeneParser(CIDParser):
    def __init__(self, text: str, tsv_paths: List[Path]):
        super().__init__(text)
        self.tsv_paths = tsv_paths
        for tsv_path in tsv_paths:
            with tsv_path.open(newline='', encoding='utf-8') as f:
                for line in f:
                    line = line.rstrip('\n\r')
                    if not line:
                        continue
                    pmid, rel_type, head, tail = line.split('\t')
                    article=self.article_map.get(pmid)
                    article.res.append(Relation(pmid, head, tail, rel_type))

