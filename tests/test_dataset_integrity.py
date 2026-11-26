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
    },
    "foreign_keys": {                            # #19, report 008
        "sports/case3",
    },
    "keys_and_not_null": set(),                  # #19, report 011
}


# Foreign-key values the documents state explicitly but never describe (no row exists for them).
# A careful reader writes exactly these values, so they stay in the ground truth (#19, report 008).
STATED_BUT_UNDESCRIBED = {
    "others/case1": {
        "twitter.LocationID": {2619},
    },
    "others/case2": {
        "inventory.film_id": {
            73, 125, 152, 227, 295, 308, 353, 373, 382, 435, 465, 544, 588, 591, 593, 651, 665, 730,
            745, 777, 816, 869, 891, 904, 906, 1000
        },
    },
    "sports/case2": {
        "games_competitor.person_id": {
            1048, 3433, 11223, 16600, 18821, 20097, 20429, 21673, 25225, 25921, 30248, 30620, 33305,
            35504, 38349, 43571, 44366, 49049, 49713, 56004, 56617, 60897, 61000, 68856, 69506,
            70856, 71345, 72715, 79565, 79971, 80393, 82533, 83187, 85715, 88887, 90611, 93641,
            94000, 98248, 98983, 103339, 109131, 121292, 124200, 128094, 130858, 132096, 133086,
            133941
        },
    },
    "sports/case3": {
        "Match.Man_of_the_Match": {187},
    },
    "university/case3": {
        "CLASS.PROF_NUM": {101},
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
            allowed = {str(v) for v in STATED_BUT_UNDESCRIBED.get(case, {}).get(f"{table}.{field['name']}", ())}
            missing = [r[field["name"]] for r in gt[table.lower()]
                       if r.get(field["name"]) is not None and str(r[field["name"]]) not in targets | allowed]
            if missing:
                dangling[f"{table}.{field['name']} -> {fk['table']}.{fk['column']}"] = len(missing)
    assert dangling == {}


# Cases that deliberately share one database, rendered in different document styles (README, #19 report 018).
SAME_DATABASE_RENDERED_TWICE = [["medical/case2", "medical/case3"]]


def test_no_two_cases_share_the_same_ground_truth(evaluator):
    seen = {}
    for case in CASES:
        digest = hashlib.sha256(json.dumps(ground_truth(evaluator, case), sort_keys=True).encode()).hexdigest()
        seen.setdefault(digest, []).append(case)
    assert [cases for cases in seen.values() if len(cases) > 1] == SAME_DATABASE_RENDERED_TWICE


@pytest.mark.parametrize("cases", SAME_DATABASE_RENDERED_TWICE)
def test_cases_sharing_a_database_say_so_and_differ_in_their_documents(cases):
    metas = [json.loads((ROOT / "dataset" / c / "meta.json").read_text(encoding="utf-8")) for c in cases]
    assert len({m["database_name"] for m in metas}) == 1
    docs = [{p.name: p.read_text(encoding="utf-8") for p in (ROOT / "dataset" / c / "docs").glob("*.md")} for c in cases]
    assert all(docs[0][name] != other[name] for other in docs[1:] for name in docs[0])


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


@pytest.mark.parametrize("case", CASES)
def test_foreign_keys_form_no_cycle(case):
    """A table never depends, through its foreign keys, on itself (self-references excepted)."""
    edges = {table.lower(): {(f.get("constraints") or {})["foreign_key"]["table"].lower()
                             for f in fields if (f.get("constraints") or {}).get("foreign_key")} - {table.lower()}
             for table, fields in schema_tables(case).items()}
    visiting, done = set(), set()

    def cycle_from(table, path):
        if table in visiting:
            return path[path.index(table):] + [table]
        if table in done:
            return None
        visiting.add(table)
        for target in edges.get(table, ()):
            found = cycle_from(target, path + [table])
            if found:
                return found
        visiting.discard(table)
        done.add(table)
        return None

    cycles = [c for c in (cycle_from(t, []) for t in edges) if c]
    assert cycles == [], " -> ".join(cycles[0])

