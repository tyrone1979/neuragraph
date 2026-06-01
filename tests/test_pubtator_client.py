from service.pubtator_client import (
    parse_biocjson_relations,
    parse_pubtator_relations,
    to_cid_lines,
)


def test_parse_pubtator_relations_tab_format():
    raw = (
        "123|t|Example title\n"
        "123|a|Dexmedetomidine caused hypotension.\n"
        "123\tPositive_Correlation\tMESH:C001\tDexmedetomidine\tMESH:D001\tHypotension\n"
    )
    rows = parse_pubtator_relations(raw)
    assert len(rows) == 1
    assert rows[0]["head"] == "Dexmedetomidine"
    assert rows[0]["tail"] == "Hypotension"


def test_parse_biocjson_relations():
    article = {
        "passages": [
            {
                "annotations": [
                    {"text": "Dexmedetomidine", "infons": {"type": "Chemical", "identifier": "MESH:C001"}},
                    {"text": "Hypotension", "infons": {"type": "Disease", "identifier": "MESH:D001"}},
                ]
            }
        ],
        "relations": [
            {
                "infons": {"type": "Positive_Correlation"},
                "nodes": [0, 1],
            }
        ],
    }
    rows = parse_biocjson_relations(article)
    assert len(rows) == 1
    assert rows[0]["head"] == "Dexmedetomidine"
    assert rows[0]["tail"] == "Hypotension"


def test_parse_biocjson_relations_role_infons():
    article = {
        "passages": [],
        "relations": [
            {
                "infons": {
                    "type": "Positive_Correlation",
                    "role1": {
                        "type": "Chemical",
                        "name": "Lithium",
                        "identifier": "MESH:D008094",
                    },
                    "role2": {
                        "type": "Disease",
                        "name": "Heart Diseases",
                        "identifier": "MESH:D006331",
                    },
                },
                "nodes": [{"refid": "0", "role": "12,11"}],
            }
        ],
    }
    rows = parse_biocjson_relations(article)
    assert len(rows) == 1
    assert rows[0]["head"] == "Lithium"
    assert rows[0]["tail"] == "Heart Diseases"


def test_normalize_entity_filter_from_list():
    from service.pubtator_client import normalize_entity_filter

    entities = [
        {"text": "Dexmedetomidine", "label": "Chemical", "id": "MESH:C001"},
        {"text": "Hypotension", "label": "Disease", "id": "MESH:D001"},
    ]
    out = normalize_entity_filter(entities)
    assert out == {
        "Chemical": ["Dexmedetomidine"],
        "Disease": ["Hypotension"],
    }


def test_resolve_pmid_query_candidates():
    from service.pubtator_client import resolve_pmid_from_text

    # Title-only resolution is attempted via search; keep helper pure by testing empty input.
    assert resolve_pmid_from_text("") == ""


def test_export_biocjson_calls_pubtator3_api():
    import service.pubtator_client as pc

    calls: list[str] = []
    original = pc._http_get_json

    def fake_get_json(url: str, *, timeout: int = 90):
        calls.append(url)
        return {"PubTator3": []}

    pc._http_get_json = fake_get_json
    try:
        pc.export_biocjson("6794356", full=True)
    finally:
        pc._http_get_json = original

    assert len(calls) == 1
    assert calls[0].startswith(f"{pc.BASE_V3}/publications/export/biocjson?")
    assert "pmids=6794356" in calls[0]
    assert "full=true" in calls[0]


def test_to_cid_lines_filters_by_entities():
    rows = [
        {"head": "Dexmedetomidine", "tail": "Hypotension"},
        {"head": "Aspirin", "tail": "Hypertension"},
    ]
    lines = to_cid_lines(
        rows,
        {"Chemical": ["Dexmedetomidine"], "Disease": ["Hypotension"]},
    )
    assert lines == ["Dexmedetomidine | CID | Hypotension"]
