"""Each case's schema and ground truth agree, and nothing else is needed to check that (#19).

Known failures are listed below, one case per line, grouped by the report that fixes them.
Each is a strict xfail: the pull request that fixes a case deletes its line.
"""
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = sorted(str(p.parent.relative_to(ROOT / "dataset"))
               for p in (ROOT / "dataset").glob("*/case*/schema.json"))

KNOWN_FAILURES = {
    "layout": set(),                             # #19, layout
    "table_names": set(),                        # #19, layout
    "columns": {                                 # #19, report 002
        "others/case5",
    },
    "foreign_keys": {                            # #19, reports 008 and 009
        "finance/case4",
        "others/case1",
        "others/case10",
        "others/case2",
        "others/case7",
        "sports/case2",
        "sports/case3",
        "university/case3",
        "university/case6",
    },
    "keys_and_not_null": {                       # #19, report 011
        "medical/case2",
        "medical/case3",
        "sports/case3",
    },
}


def cases_for(check):
    return [pytest.param(c, marks=pytest.mark.xfail(strict=True, reason=f"#19: {check}"))
            if c in KNOWN_FAILURES[check] else c for c in CASES]


def schema_tables(case):
    raw = json.loads((ROOT / "dataset" / case / "schema.json").read_text(encoding="utf-8"))
    tables = raw["tables"] if isinstance(raw, dict) else raw
    return {t["name"]: t.get("fields") or t.get("attributes") or [] for t in tables}


def ground_truth(evaluator, case):
    d = ROOT / "dataset" / case
    return evaluator.load_expected_answer({
        "answer_source": "tables" if (d / "tables").is_dir() else "folder",
        "answer_path": d / "tables",
        "answer_file": d / "answer.json" if (d / "answer.json").exists() else None,
        "answer_dir": d / "answer" if (d / "answer").is_dir() else None,
    })


@pytest.mark.parametrize("case", cases_for("layout"))
def test_case_uses_the_canonical_layout(case):
    d = ROOT / "dataset" / case
    assert isinstance(json.loads((d / "schema.json").read_text(encoding="utf-8")), list)
    assert (d / "tables").is_dir() and not (d / "answer").exists() and not (d / "answer.json").exists()


@pytest.mark.parametrize("case", cases_for("table_names"))
def test_ground_truth_tables_are_named_as_in_schema(evaluator, case):
    assert set(ground_truth(evaluator, case)) <= set(schema_tables(case))


@pytest.mark.parametrize("case", cases_for("columns"))
def test_ground_truth_columns_are_defined_in_schema(evaluator, case):
    schema = {name.lower(): {f["name"] for f in fields} for name, fields in schema_tables(case).items()}
    undefined = {}
    for table, rows in ground_truth(evaluator, case).items():
        extra = {col for row in rows for col in row} - schema.get(table.lower(), set())
        if extra:
            undefined[table] = sorted(extra)
    assert undefined == {}


@pytest.mark.parametrize("case", cases_for("foreign_keys"))
def test_ground_truth_foreign_keys_point_to_existing_rows(evaluator, case):
    gt = {name.lower(): rows for name, rows in ground_truth(evaluator, case).items()}
    dangling = {}
    for table, fields in schema_tables(case).items():
        for field in fields:
            fk = (field.get("constraints") or {}).get("foreign_key")
            if not fk or table.lower() not in gt or fk["table"].lower() not in gt:
                continue
            targets = {str(r.get(fk["column"])) for r in gt[fk["table"].lower()]}
            missing = [r[field["name"]] for r in gt[table.lower()]
                       if r.get(field["name"]) is not None and str(r[field["name"]]) not in targets]
            if missing:
                dangling[f"{table}.{field['name']} -> {fk['table']}.{fk['column']}"] = len(missing)
    assert dangling == {}


@pytest.mark.xfail(strict=True, reason="#19: medical/case2 and medical/case3 are identical (report 018)")
def test_no_two_cases_share_the_same_ground_truth(evaluator):
    seen = {}
    for case in CASES:
        digest = hashlib.sha256(json.dumps(ground_truth(evaluator, case), sort_keys=True).encode()).hexdigest()
        seen.setdefault(digest, []).append(case)
    assert [cases for cases in seen.values() if len(cases) > 1] == []


@pytest.mark.parametrize("case", cases_for("keys_and_not_null"))
def test_ground_truth_respects_primary_key_and_not_null(evaluator, case):
    gt = {name.lower(): rows for name, rows in ground_truth(evaluator, case).items()}
    problems = []
    for table, fields in schema_tables(case).items():
        rows = gt.get(table.lower(), [])
        pk = [f["name"] for f in fields if (f.get("constraints") or {}).get("primary_key")]
        if pk:
            keys = [tuple(r.get(c) for c in pk) for r in rows]
            if len(keys) != len(set(keys)):
                problems.append(f"{table}: duplicate primary key {pk}")
        for f in fields:
            if (f.get("constraints") or {}).get("nullable") is False:
                nulls = sum(1 for r in rows if r.get(f["name"]) is None)
                if nulls:
                    problems.append(f"{table}.{f['name']}: {nulls} null values in a NOT NULL column")
    assert problems == []
