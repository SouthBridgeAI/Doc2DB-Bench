import pytest

# Replace each reason with the GitHub issue number once the issues are filed.
def known(reason):
    return pytest.mark.xfail(strict=True, reason=reason)


@known("scorer: JSON booleans never match boolean strings")
def test_json_boolean_matches_boolean_string(evaluator):
    assert evaluator.compare_cell_values("TRUE", True)["match"]


@known("scorer: keyword fallback accepts wrong values")
def test_keyword_fallback_rejects_different_codes(evaluator):
    assert not evaluator.compare_cell_values("M", "F")["match"]


@known("scorer: column name differing only in case is counted twice")
def test_column_name_case_not_double_counted(evaluator):
    m = evaluator.calculate_cell_metrics({"T": [{"name": "Ann"}]}, {"T": [{"Name": "Ann"}]})
    assert m["cell_f1"] == 100.0          # today: 66.67


@known("scorer: dates and times compared as exact strings")
def test_time_with_seconds_matches(evaluator):
    assert evaluator.compare_cell_values("2008-04-24 10:00", "2008-04-24 10:00:00")["match"]


@known("scorer: empty cells counted, contrary to the paper's non-empty definition")
def test_null_cells_not_counted(evaluator):
    m = evaluator.calculate_cell_metrics(
        {"T": [{"id": 1, "x": "a"}]},
        {"T": [{"id": 1, "x": "a", "note": None}]},
    )
    assert m["total_expected_cells"] == 2  # today: 3


@known("baseline: Markdown table parser drops empty cells and shifts values left")
def test_markdown_parser_keeps_empty_cells_in_place(cascade):
    response = "<TABLE BEGIN>\n| a | b | c |\n|---|---|---|\n| 1 |  | 3 |\n<TABLE END>"
    rows = cascade.parse_llm_response(response, {"name": "T", "attributes": []})["T"]
    assert rows == [{"a": "1", "b": None, "c": "3"}]   # today: b="3", c=None
