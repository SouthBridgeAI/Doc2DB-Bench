"""Identifiers the documents never state are scored up to a consistent renaming (#7)."""
import copy
import json
from pathlib import Path

import pytest

from test_scorer import CASES, ROOT


def case_info(evaluator, case):
    db, name = case.split("/")
    [info] = [c for c in evaluator.scan_datasets() if (c["db_name"], c["case_name"]) == (db, name)]
    return info


def surrogate_keys(evaluator, schema, info):
    """{table: key column} for single-column keys that are not foreign keys and not stated in the documents."""
    stated = evaluator._get_entity_pk_allowed_from_meta(info)
    keys = {}
    for t in evaluator._normalize_schema_for_metrics(schema)["tables"]:
        pk = [f for f in t.get("attributes") or t.get("fields") or [] if (f.get("constraints") or {}).get("primary_key")]
        if len(pk) == 1 and not pk[0]["constraints"].get("foreign_key") and not stated.get(t["name"].lower()):
            keys[t["name"].lower()] = pk[0]["name"]
    return keys


def renumber(gt, schema, keys):
    """The ground truth with each listed key renumbered in reverse row order, foreign keys following.

    New IDs start at 1,000,001 so they cannot collide with the dangling references some cases contain
    (benchmark report 008), which stay as written."""
    gt = copy.deepcopy(gt)
    rows = {k.lower(): v for k, v in gt.items()}
    new_ids = {t: {str(r.get(c)): 1_000_000 + n for n, r in enumerate(reversed(rows.get(t, [])), 1)} for t, c in keys.items()}
    tables = schema["tables"] if isinstance(schema, dict) else schema
    for t in tables:
        for f in t.get("attributes") or t.get("fields") or []:
            c = f.get("constraints") or {}
            fk = c.get("foreign_key")
            target = fk["table"].lower() if fk and keys.get(fk["table"].lower()) == fk["column"] else \
                t["name"].lower() if keys.get(t["name"].lower()) == f["name"] else None
            for r in rows.get(t["name"].lower(), []) if target else []:
                if r.get(f["name"]) is not None:
                    r[f["name"]] = new_ids[target].get(str(r[f["name"]]), r[f["name"]])  # dangling references stay
    return gt


def load(evaluator, case):
    info = case_info(evaluator, case)
    schema = json.loads(Path(info["schema_file"]).read_text(encoding="utf-8"))
    return info, schema, evaluator.load_expected_answer(info)


def test_renumbered_ground_truth_scores_100_smoke(evaluator):
    evaluator.dataset_dir = ROOT / "dataset"
    info, schema, gt = load(evaluator, "medical/case1")
    renumbered = renumber(gt, schema, surrogate_keys(evaluator, schema, info))
    assert renumbered != gt
    m = evaluator.calculate_cell_metrics(renumbered, gt, schema, case_info=info)
    assert m["cell_f1"] == pytest.approx(100.0)


@pytest.mark.slow
@pytest.mark.parametrize("case", CASES)
def test_renumbered_ground_truth_scores_100(evaluator, case):
    evaluator.dataset_dir = ROOT / "dataset"
    info, schema, gt = load(evaluator, case)
    renumbered = renumber(gt, schema, surrogate_keys(evaluator, schema, info))
    m = evaluator.calculate_cell_metrics(renumbered, gt, schema, case_info=info)
    assert m["cell_f1"] == pytest.approx(100.0)


def test_literal_keys_scores_renumbering_as_wrong(evaluator):
    evaluator.dataset_dir = ROOT / "dataset"
    evaluator.align_keys = False
    info, schema, gt = load(evaluator, "medical/case1")
    renumbered = renumber(gt, schema, surrogate_keys(evaluator, schema, info))
    assert evaluator.calculate_cell_metrics(renumbered, gt, schema, case_info=info)["cell_f1"] < 80


def test_a_wrong_link_is_still_wrong(evaluator):
    """Swapping which physician two appointments point to costs exactly those two cells."""
    evaluator.dataset_dir = ROOT / "dataset"
    info, schema, gt = load(evaluator, "medical/case1")
    renumbered = renumber(gt, schema, surrogate_keys(evaluator, schema, info))
    appointments = next(v for k, v in renumbered.items() if k.lower() == "appointment")
    a, b = next((x, y) for x in appointments for y in appointments if x["Physician"] != y["Physician"])
    a["Physician"], b["Physician"] = b["Physician"], a["Physician"]
    m = evaluator.calculate_cell_metrics(renumbered, gt, schema, case_info=info)
    assert m["total_correct_cells"] == m["total_expected_cells"] - 2


def test_keys_the_documents_state_are_scored_as_written(evaluator):
    """finance/case2 states client IDs in the documents (meta.json if_primary_allowed), so renumbering them is wrong."""
    evaluator.dataset_dir = ROOT / "dataset"
    info, schema, gt = load(evaluator, "finance/case2")
    stated = {t["name"].lower(): f["name"] for t in schema for f in t.get("fields") or t.get("attributes") or []
              if t["name"].lower() == "client" and (f.get("constraints") or {}).get("primary_key")}
    renumbered = renumber(gt, schema, stated)
    assert renumbered != gt
    assert evaluator.calculate_cell_metrics(renumbered, gt, schema, case_info=info)["cell_f1"] < 100


def test_keys_of_unpaired_records_match_nothing_and_dangling_keys_are_kept(evaluator):
    schema = {"tables": [
        {"name": "P", "type": "entity", "attributes": [
            {"name": "id", "constraints": {"primary_key": True}}, {"name": "name", "constraints": {}}]},
        {"name": "R", "type": "relation", "attributes": [
            {"name": "p", "constraints": {"foreign_key": {"table": "P", "column": "id"}}}, {"name": "note", "constraints": {}}]},
    ]}
    gt = {"P": [{"id": 7, "name": "Ann Lee"}], "R": [{"p": 7, "note": "x"}]}
    gen = {"P": [{"id": 1, "name": "Ann Lee"}, {"id": 2, "name": "Zed Quinn"}],   # Zed is not in the ground truth
           "R": [{"p": 1, "note": "x"}, {"p": 2, "note": "y"}, {"p": 9, "note": "z"}]}  # 9 refers to no P extracted
    aligned = evaluator.align_surrogate_keys(gen, gt, schema)
    assert [r["id"] for r in aligned["P"]] == [7, evaluator.UNMATCHED_KEY]
    assert [r["p"] for r in aligned["R"]] == [7, evaluator.UNMATCHED_KEY, 9]
