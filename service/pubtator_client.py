"""PubTator3 client for biomedical relation extraction."""

from __future__ import annotations

import json
import time
import urllib.parse
from typing import Any

import certifi
import requests

BASE_V3 = "https://www.ncbi.nlm.nih.gov/research/pubtator3-api"
USER_AGENT = "agentic-llmre/pubtator-client"
MIN_REQUEST_INTERVAL = 0.34  # PubTator3: max 3 requests/second
MAX_RETRIES = 3

CHEM_DISEASE_REL_TYPES = {
    "positive_correlation",
    "negative_correlation",
    "association",
    "cause",
    "treat",
    "prevent",
    "inhibit",
    "stimulate",
    "positive_correlate",
    "negative_correlate",
    "cid",
    "chemicalinduceddisease",
}

_last_request_at = 0.0


def _rate_limit() -> None:
    global _last_request_at
    now = time.monotonic()
    wait = MIN_REQUEST_INTERVAL - (now - _last_request_at)
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def _format_request_error(ex: Exception) -> str:
    msg = str(ex).strip()
    if msg:
        return msg
    reason = getattr(ex, "reason", None)
    if reason is not None:
        reason_msg = str(reason).strip()
        if reason_msg:
            return reason_msg
    return repr(ex)


def _http_request(
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 90,
) -> str:
    req_headers = {
        "User-Agent": USER_AGENT,
        **(headers or {}),
    }
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        _rate_limit()
        try:
            if data is not None:
                resp = requests.post(
                    url,
                    data=data,
                    headers=req_headers,
                    timeout=timeout,
                    verify=certifi.where(),
                )
            else:
                resp = requests.get(
                    url,
                    headers=req_headers,
                    timeout=timeout,
                    verify=certifi.where(),
                )
            if resp.status_code == 429:
                time.sleep(min(3 * (attempt + 1), 10))
                continue
            if resp.status_code >= 500:
                time.sleep(2**attempt)
                continue
            if resp.status_code >= 400:
                body = (resp.text or resp.reason or "")[:200]
                raise RuntimeError(f"PubTator HTTP {resp.status_code}: {body}")
            return resp.text
        except RuntimeError:
            raise
        except requests.RequestException as ex:
            last_error = ex
            time.sleep(2**attempt)
    raise RuntimeError(
        f"PubTator request failed after {MAX_RETRIES} attempts: "
        f"{_format_request_error(last_error or Exception('unknown'))}"
    )


def _http_get_json(url: str, *, timeout: int = 90) -> Any:
    return json.loads(_http_request(url, timeout=timeout))


def _join_pmids(pmids: str | list[str]) -> str:
    if isinstance(pmids, str):
        return pmids.strip()
    return ",".join(str(p).strip() for p in pmids if str(p).strip())


def export_biocjson(
    pmids: str | list[str],
    *,
    full: bool = True,
) -> dict[str, Any]:
    """Export PubTator3 annotations as BioC-JSON."""
    joined = _join_pmids(pmids)
    if not joined:
        return {"PubTator3": []}
    params: dict[str, str] = {"pmids": joined}
    if full:
        params["full"] = "true"
    url = f"{BASE_V3}/publications/export/biocjson?{urllib.parse.urlencode(params)}"
    data = _http_get_json(url, timeout=120)
    return data if isinstance(data, dict) else {"PubTator3": []}


def export_pubtator(pmids: str | list[str]) -> str:
    """Export PubTator3 annotations in PubTator tab-delimited format."""
    joined = _join_pmids(pmids)
    if not joined:
        return ""
    url = (
        f"{BASE_V3}/publications/export/pubtator"
        f"?pmids={urllib.parse.quote(joined)}"
    )
    return _http_request(url, timeout=120)


def export_pmid_biocjson(pmid: str) -> dict[str, Any]:
    """Export precomputed PubTator3 annotations for a PMID."""
    pmid = str(pmid or "").strip()
    if not pmid:
        return {}
    data = export_biocjson(pmid, full=True)
    articles = data.get("PubTator3") or []
    return articles[0] if articles else {}


def search_publications(text: str, *, page: int = 1) -> dict[str, Any]:
    """Search PubTator3 literature index."""
    query = str(text or "").strip()
    if not query:
        return {"results": [], "total_pages": 0}
    params = urllib.parse.urlencode({"text": query, "page": str(page)})
    url = f"{BASE_V3}/search/?{params}"
    data = _http_get_json(url, timeout=60)
    return data if isinstance(data, dict) else {"results": [], "total_pages": 0}


def resolve_pmid_from_text(text: str) -> str:
    """Resolve a PubMed ID from free text via PubTator3 search API."""
    text = str(text or "").strip()
    if not text:
        return ""

    first_line = text.splitlines()[0].strip()
    title = first_line.split(".")[0].strip() if first_line else text
    if len(title) < 20:
        title = first_line[:240]
    else:
        title = title[:240]

    queries = [f'"{title}"', title]
    if first_line and first_line not in queries:
        queries.append(first_line[:240])

    for query in queries:
        results = search_publications(query).get("results") or []
        if not results:
            continue
        pmid = str(results[0].get("pmid") or "").strip()
        if pmid:
            return pmid
    return ""


def entity_autocomplete(
    query: str,
    *,
    concept: str = "",
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Find normalized entity IDs via PubTator3 autocomplete API."""
    query = str(query or "").strip()
    if not query:
        return []
    params: dict[str, str] = {"query": query, "limit": str(limit)}
    if concept:
        params["concept"] = concept
    url = f"{BASE_V3}/entity/autocomplete/?{urllib.parse.urlencode(params)}"
    data = _http_get_json(url, timeout=30)
    return data if isinstance(data, list) else []


def annotate_text(text: str, bioconcept: str = "chemical,disease") -> str:
    """Export PubTator tab format for text via PubTator3 (PMID resolved by search)."""
    del bioconcept  # PubTator3 export returns full precomputed annotations.
    pmid = resolve_pmid_from_text(text)
    if not pmid:
        raise RuntimeError(
            "PubTator3 could not resolve a PMID from text. "
            "Provide pmid explicitly or use text from a PubMed abstract/title."
        )
    return export_pubtator(pmid)


def _norm(s: str) -> str:
    return str(s or "").strip().lower()


def normalize_entity_filter(entities: Any) -> dict[str, list[str]] | None:
    """Accept label->names dict, JSON string, or [{text, label, id}, ...] entity list."""
    from service.relation_normalize import canonical_mesh_id, parse_entities_raw

    parsed = parse_entities_raw(entities)
    if parsed:
        entities = parsed
    if not entities:
        return None
    if isinstance(entities, dict):
        out: dict[str, list[str]] = {}
        for label, names in entities.items():
            if isinstance(names, str):
                names = [names]
            if isinstance(names, list):
                out[str(label)] = [str(n) for n in names if str(n).strip()]
        return out or None
    if isinstance(entities, list):
        out: dict[str, list[str]] = {}
        id_out: dict[str, list[str]] = {}
        for item in entities:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or item.get("type") or "").strip()
            name = str(item.get("text") or item.get("name") or "").strip()
            ent_id = canonical_mesh_id(str(item.get("id") or item.get("identifier") or ""))
            if label and name:
                out.setdefault(label, []).append(name)
            if label and ent_id:
                id_out.setdefault(label, []).append(ent_id)
        if not out:
            return None
        out["_ids"] = id_out  # type: ignore[assignment]
        return out
    return None


def _entity_id_allowed(ent_id: str, label: str, entities: dict[str, Any] | None) -> bool:
    from service.relation_normalize import canonical_mesh_id

    if not entities or not ent_id:
        return False
    id_bucket = (entities.get("_ids") or {}).get(label) or (entities.get("_ids") or {}).get(
        label.lower()
    ) or []
    if not id_bucket:
        return False
    return canonical_mesh_id(ent_id) in id_bucket


def _entity_allowed(name: str, label: str, entities: dict[str, Any] | None) -> bool:
    if not entities:
        return True
    bucket = entities.get(label) or entities.get(label.lower()) or []
    if isinstance(bucket, str):
        bucket = [bucket]
    if not bucket:
        return True
    target = _norm(name)
    return any(_norm(x) == target or target in _norm(x) or _norm(x) in target for x in bucket)


def _entity_side_allowed(
    name: str,
    ent_id: str,
    label: str,
    entities: dict[str, Any] | None,
) -> bool:
    if not entities:
        return True
    if _entity_allowed(name, label, entities):
        return True
    if ent_id and _entity_id_allowed(ent_id, label, entities):
        return True
    bucket = entities.get(label) or entities.get(label.lower()) or []
    id_bucket = (entities.get("_ids") or {}).get(label) or (entities.get("_ids") or {}).get(
        label.lower()
    ) or []
    if bucket or id_bucket:
        return False
    return True


def parse_pubtator_relations(raw: str) -> list[dict[str, str]]:
    """Parse relation rows from PubTator tab-delimited export."""
    rows: list[dict[str, str]] = []
    for line in (raw or "").splitlines():
        parts = [p.strip() for p in line.split("\t")]
        if len(parts) < 6:
            continue
        rel_type = _norm(parts[1])
        if rel_type in {"t", "a", "title", "abstract"}:
            continue
        if rel_type not in CHEM_DISEASE_REL_TYPES:
            continue
        id1, text1, id2, text2 = parts[2], parts[3], parts[4], parts[5]
        id1u, id2u = id1.upper(), id2.upper()
        if id1u.startswith("@CHEMICAL") or id1u.startswith("MESH:C"):
            head, tail = text1, text2
            head_id, tail_id = id1, id2
        elif id2u.startswith("@CHEMICAL") or id2u.startswith("MESH:C"):
            head, tail = text2, text1
            head_id, tail_id = id2, id1
        elif id1u.startswith("@DISEASE") or id1u.startswith("MESH:D"):
            head, tail = text2, text1
            head_id, tail_id = id2, id1
        elif id2u.startswith("@DISEASE") or id2u.startswith("MESH:D"):
            head, tail = text1, text2
            head_id, tail_id = id1, id2
        else:
            head, tail = text1, text2
            head_id, tail_id = id1, id2
        if not head or not tail:
            continue
        rows.append(
            {
                "relation_type": parts[1],
                "head": head,
                "tail": tail,
                "head_id": head_id,
                "tail_id": tail_id,
            }
        )
    return rows


def _role_from_infons(role: dict[str, Any] | None) -> dict[str, str]:
    role = role or {}
    return {
        "text": str(role.get("name") or role.get("text") or "").strip(),
        "type": _norm(role.get("type") or role.get("biotype") or ""),
        "identifier": str(
            role.get("identifier")
            or role.get("normalized_id")
            or role.get("accession")
            or ""
        ).strip(),
    }


def parse_biocjson_relations(article: dict[str, Any]) -> list[dict[str, str]]:
    """Parse chemical–disease relations from PubTator3 BioC-JSON export."""
    rows: list[dict[str, str]] = []
    passages = article.get("passages") or []
    annotations: list[dict[str, str]] = []
    for passage in passages:
        for ann in passage.get("annotations") or []:
            infons = ann.get("infons") or {}
            annotations.append(
                {
                    "index": len(annotations),
                    "text": ann.get("text") or infons.get("name") or "",
                    "type": _norm(infons.get("type") or infons.get("identifier") or ""),
                    "identifier": infons.get("identifier") or infons.get("accession") or "",
                }
            )

    for rel in article.get("relations") or []:
        infons = rel.get("infons") or {}
        rel_type = _norm(infons.get("type") or infons.get("relation") or "")
        if rel_type and rel_type not in CHEM_DISEASE_REL_TYPES:
            continue

        role1 = _role_from_infons(infons.get("role1") if isinstance(infons.get("role1"), dict) else None)
        role2 = _role_from_infons(infons.get("role2") if isinstance(infons.get("role2"), dict) else None)
        if role1.get("text") and role2.get("text"):
            left, right = role1, role2
        else:
            nodes = rel.get("nodes") or []
            if len(nodes) < 2:
                continue
            try:
                left_idx = int(nodes[0].get("refid") if isinstance(nodes[0], dict) else nodes[0])
                right_idx = int(nodes[1].get("refid") if isinstance(nodes[1], dict) else nodes[1])
            except (TypeError, ValueError):
                continue
            left = annotations[left_idx] if 0 <= left_idx < len(annotations) else {}
            right = annotations[right_idx] if 0 <= right_idx < len(annotations) else {}
            if not left or not right:
                continue

        left_type = _norm(left.get("type") or "")
        right_type = _norm(right.get("type") or "")
        if left_type == "chemical" and right_type == "disease":
            head, tail = left.get("text", ""), right.get("text", "")
            head_id, tail_id = left.get("identifier", ""), right.get("identifier", "")
        elif left_type == "disease" and right_type == "chemical":
            head, tail = right.get("text", ""), left.get("text", "")
            head_id, tail_id = right.get("identifier", ""), left.get("identifier", "")
        else:
            head, tail = left.get("text", ""), right.get("text", "")
            head_id, tail_id = left.get("identifier", ""), right.get("identifier", "")
        if not head or not tail:
            continue
        rows.append(
            {
                "relation_type": infons.get("type") or infons.get("relation") or "Association",
                "head": head,
                "tail": tail,
                "head_id": head_id,
                "tail_id": tail_id,
            }
        )
    return rows


def to_cid_lines(
    rows: list[dict[str, str]],
    entities: dict[str, Any] | None = None,
    *,
    entities_raw: Any = None,
) -> list[str]:
    """Convert parsed relations to pipeline format: head | CID | tail (MeSH ids when known)."""
    from service.relation_normalize import canonical_mesh_id, normalize_cid_relation_lines

    interim: list[str] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        head = row.get("head") or ""
        tail = row.get("tail") or ""
        head_id = canonical_mesh_id(row.get("head_id") or "")
        tail_id = canonical_mesh_id(row.get("tail_id") or "")
        if not _entity_side_allowed(head, head_id, "Chemical", entities):
            continue
        if not _entity_side_allowed(tail, tail_id, "Disease", entities):
            continue
        head_out = head_id or head
        tail_out = tail_id or tail
        key = (_norm(head_out), _norm(tail_out))
        if key in seen:
            continue
        seen.add(key)
        interim.append(f"{head_out} | CID | {tail_out}")

    raw = entities_raw if entities_raw is not None else entities
    return normalize_cid_relation_lines(interim, raw)


def extract_relations(
    *,
    text: str = "",
    pmid: str = "",
    entities: dict[str, Any] | None = None,
    bioconcept: str = "chemical,disease",
) -> dict[str, Any]:
    """Extract chemical–disease relations via PubTator3 API."""
    del bioconcept
    text = str(text or "").strip()
    pmid = str(pmid or "").strip()
    entity_filter = normalize_entity_filter(entities)
    if not text and not pmid:
        return {"relations": [], "raw_relations": [], "source": ""}

    resolved_pmid = pmid
    source = ""
    if not resolved_pmid and text:
        resolved_pmid = resolve_pmid_from_text(text)
        if resolved_pmid:
            source = f"pubtator3-api:search:{resolved_pmid}"

    if resolved_pmid:
        if not source:
            source = f"pubtator3-api:pmid:{resolved_pmid}"
        article = export_pmid_biocjson(resolved_pmid)
        if not article:
            return {
                "relations": [],
                "raw_relations": [],
                "source": "",
                "error": f"No PubTator3 annotations found for PMID {resolved_pmid}",
            }
        raw_relations = parse_biocjson_relations(article)
    else:
        return {
            "relations": [],
            "raw_relations": [],
            "source": "",
            "error": (
                "PubTator3 API requires a PMID. Provide pmid or text that matches "
                "a PubMed title/abstract (search could not resolve a PMID)."
            ),
        }

    relations = to_cid_lines(raw_relations, entity_filter, entities_raw=entities)
    return {
        "relations": relations,
        "raw_relations": raw_relations,
        "source": source,
        "pmid": resolved_pmid,
    }
