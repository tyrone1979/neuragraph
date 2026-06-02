import json

from service.relation_normalize import (
    build_entity_id_lookup,
    normalize_cid_relation_lines,
    resolve_entity_side,
)
ENTITIES_SAMPLE5 = [
    {"text": "tacrolimus", "id": "D016559", "label": "Chemical"},
    {"text": "IDDM", "id": "D003922", "label": "Disease"},
    {"text": "(insulin-dependent) diabetes mellitus", "id": "D003922", "label": "Disease"},
    {"text": "Pruritus", "id": "D011537", "label": "Disease"},
    {"text": "Cardiomyopathies", "id": "D009202", "label": "Disease"},
]


def test_build_entity_id_lookup_synonyms():
    lookup = build_entity_id_lookup(
        [
            {"text": "CM", "id": "D003287", "label": "Chemical"},
            {"text": "CIN", "id": "D007674", "label": "Disease"},
        ]
    )
    assert lookup["cm"] == "D003287"
    assert lookup["cin"] == "D007674"


def test_resolve_entity_side_mesh_and_text():
    lookup = build_entity_id_lookup(ENTITIES_SAMPLE5)
    assert resolve_entity_side("Diabetes Mellitus Type 1", lookup) == "D003922"
    assert resolve_entity_side("IDDM", lookup) == "D003922"
    assert resolve_entity_side("D016559", lookup) == "D016559"


def test_normalize_predicted_tacrolimus_diabetes():
    preds = ["Tacrolimus | CID | Diabetes Mellitus Type 1", "Tacrolimus | CID | Pruritus"]
    out = normalize_cid_relation_lines(preds, ENTITIES_SAMPLE5)
    assert "D016559 | CID | D003922" in out
    assert "D016559 | CID | D011537" in out


def test_normalize_gold_mixed_text_and_id():
    gold = "ifosfamide | CID | D003556\ntacrolimus | CID | IDDM"
    entities = [
        {"text": "ifosfamide", "id": "D007069", "label": "Chemical"},
        {"text": "tacrolimus", "id": "D016559", "label": "Chemical"},
        {"text": "IDDM", "id": "D003922", "label": "Disease"},
    ]
    out = normalize_cid_relation_lines(gold, entities)
    assert "D007069 | CID | D003556" in out
    assert "D016559 | CID | D003922" in out


def test_normalize_dedupes():
    lines = normalize_cid_relation_lines(
        ["CM | CID | CIN", "cm | CID | cin"],
        [{"text": "CM", "id": "D003287", "label": "Chemical"}, {"text": "CIN", "id": "D007674", "label": "Disease"}],
    )
    assert lines == ["D003287 | CID | D007674"]
