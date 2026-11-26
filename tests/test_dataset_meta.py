"""Every table named in a case's meta.json must be a table of that case's schema.

The scorer reads ``if_primary_allowed`` (case-insensitively) to decide which
entity keys the documents state, and the reporting code reads ``type`` and
``capability_assignments`` per table. A key that is misspelled, or that was
copied from another case, is silently ignored, so the table it was meant for
falls back to defaults.
"""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CASES = sorted(p.parent for p in (ROOT / "dataset").glob("*/*/meta.json"))
TABLE_KEYED_FIELDS = ("if_primary_allowed", "type", "capability_assignments")


def _schema_tables(case_dir):
    schema = json.loads((case_dir / "schema.json").read_text(encoding="utf-8"))
    if isinstance(schema, dict):
        schema = schema["tables"]
    return {table["name"] for table in schema}


def test_every_case_has_a_meta_json():
    assert len(CASES) == 42


@pytest.mark.parametrize("case_dir", CASES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_meta_keys_name_schema_tables(case_dir):
    meta = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
    tables = _schema_tables(case_dir)
    problems = []
    for field in TABLE_KEYED_FIELDS:
        entries = meta.get(field, {})
        assert isinstance(entries, dict), f"{field} is not keyed by table"
        for key in entries:
            if key not in tables:
                problems.append(f"{field}[{key!r}]")
    assert not problems, f"meta.json keys that are not schema tables {sorted(tables)}: {problems}"
