import json

from service.relation_normalize import (
    assign_e2e_group_ids,
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


def test_lookup_all_synonyms_same_mesh():
    lookup = build_entity_id_lookup(
        [
            {"text": "CM", "id": "D003287", "label": "Chemical"},
            {"text": "contrast media", "id": "D003287", "label": "Chemical"},
            {"text": "CIN", "id": "D007674", "label": "Disease"},
            {"text": "contrast-induced nephropathy", "id": "D007674", "label": "Disease"},
        ]
    )
    assert lookup["contrast media"] == "D003287"
    assert lookup["contrast-induced nephropathy"] == "D007674"
    out = normalize_cid_relation_lines(
        ["CM | CID | contrast-induced nephropathy"],
        [
            {"text": "CM", "id": "D003287", "label": "Chemical"},
            {"text": "contrast media", "id": "D003287", "label": "Chemical"},
            {"text": "CIN", "id": "D007674", "label": "Disease"},
            {"text": "contrast-induced nephropathy", "id": "D007674", "label": "Disease"},
        ],
    )
    assert out == ["D003287 | CID | D007674"]


def test_normalize_dedupes():
    lines = normalize_cid_relation_lines(
        ["CM | CID | CIN", "cm | CID | cin"],
        [{"text": "CM", "id": "D003287", "label": "Chemical"}, {"text": "CIN", "id": "D007674", "label": "Disease"}],
    )
    assert lines == ["D003287 | CID | D007674"]


def test_assign_e2e_group_ids_synonyms_share_numeric_id():
    source = [
        {"text": "CYP", "id": "CYP", "label": "Chemical"},
        {"text": "cyclophosphamide", "id": "cyclophosphamide", "label": "Chemical"},
        {"text": "cyclophosphamide-induced", "id": "cyclophosphamide-induced", "label": "Chemical"},
        {"text": "cystitis", "id": "cystitis", "label": "Disease"},
    ]
    groups = [
        {"text": "CYP", "id": "cyclophosphamide", "label": "Chemical"},
        {"text": "cystitis", "id": "cystitis", "label": "Disease"},
    ]
    out = assign_e2e_group_ids(source, groups)
    chem = [e for e in out if e["label"] == "Chemical"]
    assert {e["id"] for e in chem} == {"1"}
    assert {e["text"] for e in chem} >= {"CYP", "cyclophosphamide"}
    assert "cyclophosphamide-induced" not in {e["text"] for e in chem}
    dis = [e for e in out if e["label"] == "Disease"]
    assert dis == [{"text": "cystitis", "id": "1", "label": "Disease"}]


def test_assign_e2e_group_ids_strips_induced_suffix_from_source():
    source = [
        {"text": "levobupivacaine-induced", "label": "Chemical", "id": ""},
        {"text": "levobupivacaine", "label": "Chemical", "id": ""},
    ]
    groups = [{"text": "levobupivacaine", "id": "levobupivacaine", "label": "Chemical"}]
    out = assign_e2e_group_ids(source, groups)
    chem = [e for e in out if e["label"] == "Chemical"]
    assert {e["text"] for e in chem} == {"levobupivacaine"}
    assert {e["id"] for e in chem} == {"1"}


def test_assign_e2e_group_ids_orphans_get_own_id():
    source = [
        {"text": "famotidine", "label": "Chemical", "id": ""},
        {"text": "delirium", "label": "Disease", "id": ""},
        {"text": "stress ulcers", "label": "Disease", "id": ""},
    ]
    # LLM omitted famotidine group
    groups = [
        {"text": "delirium", "id": "delirium", "label": "Disease"},
        {"text": "stress ulcers", "id": "stress ulcers", "label": "Disease"},
    ]
    out = assign_e2e_group_ids(source, groups)
    texts = {e["text"] for e in out}
    assert "famotidine" in texts
    assert "delirium" in texts
    chem = [e for e in out if e["label"] == "Chemical"]
    assert len(chem) == 1 and chem[0]["id"] == "1"


def test_assign_e2e_group_ids_shared_cluster_key_merges_rows():
    source = [
        {"text": "hepatitis", "label": "Disease", "id": ""},
        {"text": "hepatotoxicity", "label": "Disease", "id": ""},
        {"text": "hepatic injury", "label": "Disease", "id": ""},
    ]
    groups = [
        {"text": "hepatitis", "id": "drug-induced liver injury", "label": "Disease"},
        {"text": "hepatotoxicity", "id": "drug-induced liver injury", "label": "Disease"},
        {"text": "hepatic injury", "id": "drug-induced liver injury", "label": "Disease"},
    ]
    out = assign_e2e_group_ids(source, groups)
    dis = [e for e in out if e["label"] == "Disease"]
    assert {e["id"] for e in dis} == {"1"}
    assert {e["text"] for e in dis} >= {"hepatitis", "hepatotoxicity", "hepatic injury"}


def test_normalize_e2e_aliases_gold_head_to_group_id():
    aliases = [
        {"text": "IDM", "id": "1", "label": "Chemical"},
        {"text": "indomethacin", "id": "1", "label": "Chemical"},
        {"text": "hypotension", "id": "1", "label": "Disease"},
    ]
    gold = "indomethacin | CID | hypotension"
    pred = ["1 | 1", "2 | 1", "3 | 1"]
    assert normalize_cid_relation_lines(gold, aliases) == ["1 | CID | 1"]
    assert normalize_cid_relation_lines(pred, aliases) == [
        "1 | CID | 1",
        "2 | CID | 1",
        "3 | CID | 1",
    ]


def test_normalize_cyp_cyclophosphamide_no_cross_label_substring():
    entities = assign_e2e_group_ids(
        [
            {"text": "CYP", "label": "Chemical", "id": "CYP"},
            {"text": "cyclophosphamide", "label": "Chemical", "id": "cyclophosphamide"},
            {"text": "cystitis", "label": "Disease", "id": "cystitis"},
            {"text": "cyclophosphamide-induced cystitis", "label": "Disease", "id": "x"},
        ],
        [
            {"text": "CYP", "id": "cyclophosphamide", "label": "Chemical"},
            {"text": "cystitis", "id": "cystitis", "label": "Disease"},
        ],
    )
    gold = "CYP | CID | cystitis"
    pred = ["1 | cystitis"]
    eg = normalize_cid_relation_lines(gold, entities)
    pg = normalize_cid_relation_lines(pred, entities)
    assert eg == ["1 | CID | 1"]
    assert pg == ["1 | CID | 1"]
