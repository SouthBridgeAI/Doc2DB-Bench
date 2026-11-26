"""Schema descriptions must not ask for a value format the ground truth doesn't use.

Field descriptions are shown to extraction systems (the cascade baseline puts them
into its prompt), so a description that names a date format is an instruction. If it
names one format and the ground truth stores another, a system that follows the
schema is marked wrong for doing so.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# A date/time format pattern written in a description, e.g. YYMMDD, YYYY-MM-DD,
# MM/DD/YYYY, yyyy-mm-dd, HH:MM:SS. At least two components, so plain words don't match.
_COMPONENT = r"(?:YYYY|YY|MM|DD|HH|SS)"
FORMAT_IN_TEXT = re.compile(
    rf"(?<![A-Za-z0-9]){_COMPONENT}(?:[-/:.]?{_COMPONENT})+(?![A-Za-z0-9])", re.I
)
TOKEN_REGEX = {"YYYY": r"\d{4}", "YY": r"\d{2}", "MM": r"\d{2}", "DD": r"\d{2}", "HH": r"\d{2}", "SS": r"\d{2}"}


def format_to_regex(fmt: str) -> re.Pattern:
    parts = re.findall(r"YYYY|YY|MM|DD|HH|SS|.", fmt.upper())
    return re.compile("".join(TOKEN_REGEX.get(p, re.escape(p)) for p in parts))


def documented_formats():
    """(case, table, field, format) for every schema field whose description names a format."""
    out = []
    for schema_path in sorted(ROOT.glob("dataset/*/*/schema.json")):
        case = f"{schema_path.parent.parent.name}/{schema_path.parent.name}"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        tables = schema["tables"] if isinstance(schema, dict) else schema
        for table in tables:
            for field in table.get("fields", []):
                for fmt in FORMAT_IN_TEXT.findall(field.get("description") or ""):
                    out.append((case, table["name"], field["name"], fmt))
    return out


def test_format_finder_sees_known_forms():
    text = "x YYMMDD, (yyyy-mm-dd) MM/DD/YYYY HH:MM:SS; added, odd, mmm, dd"
    assert FORMAT_IN_TEXT.findall(text) == ["YYMMDD", "yyyy-mm-dd", "MM/DD/YYYY", "HH:MM:SS"]
    assert format_to_regex("YYMMDD").fullmatch("930226")
    assert not format_to_regex("YYMMDD").fullmatch("1993-02-26")
    assert format_to_regex("yyyy-mm-dd").fullmatch("1993-02-26")


def test_some_descriptions_name_a_format():
    # Guards against the parametrized check below silently checking nothing.
    assert documented_formats()


@pytest.fixture(scope="module")
def ground_truth():
    import test_dataset_evaluate

    ev = test_dataset_evaluate.Doc2DBEvaluator(
        "http://unused", ROOT / "dataset", Path("/tmp/unused-out"), enable_llm_eval=False
    )
    cases = {f"{c['db_name']}/{c['case_name']}": c for c in ev.scan_datasets()}
    return lambda case: ev.load_expected_answer(cases[case])


@pytest.mark.parametrize("case,table,field,fmt", documented_formats(), ids=lambda v: str(v))
def test_ground_truth_follows_documented_format(ground_truth, case, table, field, fmt):
    expected = ground_truth(case)
    rows = next(v for k, v in expected.items() if k.lower() == table.lower())
    values = [row.get(field) for row in rows]
    values = [v for v in values if v is not None and str(v).strip() != ""]
    assert values, f"{case} {table}.{field}: no ground-truth values to check"
    pattern = format_to_regex(fmt)
    bad = [v for v in values if not pattern.fullmatch(str(v).strip())]
    assert not bad, (
        f"{case} {table}.{field}: description says {fmt!r} but {len(bad)}/{len(values)} "
        f"ground-truth values don't match it, e.g. {bad[:3]}"
    )
