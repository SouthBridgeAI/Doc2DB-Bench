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


def test_column_name_case_not_double_counted(evaluator):
    m = evaluator.calculate_cell_metrics({"T": [{"name": "Ann"}]}, {"T": [{"Name": "Ann"}]})
    assert m["cell_f1"] == 100.0          # was 66.67 (report 024)


def test_column_name_case_not_double_counted_in_entity_and_relation_scores(evaluator):
    schema = [{"name": "T", "type": "entity", "fields": [{"name": "name", "constraints": {}}]},
              {"name": "R", "type": "relation", "fields": [{"name": "note", "constraints": {}}]}]
    m = evaluator.calculate_entity_relation_metrics(
        {"T": [{"Name": "Ann"}], "R": [{"Note": "x"}]}, {"T": [{"name": "Ann"}], "R": [{"note": "x"}]}, schema)
    assert (m["entity_f1"], m["relation_f1"]) == (100.0, 100.0)


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


def test_whitespace_only_gt_value_counts_as_empty(evaluator):
    m = evaluator.calculate_cell_metrics({"T": [{"id": 1, "k": None}]},
                                         {"T": [{"id": 1, "k": " "}]})
    assert m["cell_f1"] == 100.0          # was 50.0 (report 012)


@known("baseline: Markdown table parser drops empty cells and shifts values left")
def test_markdown_parser_keeps_empty_cells_in_place(cascade):
    response = "<TABLE BEGIN>\n| a | b | c |\n|---|---|---|\n| 1 |  | 3 |\n<TABLE END>"
    rows = cascade.parse_llm_response(response, {"name": "T", "attributes": []})["T"]
    assert rows == [{"a": "1", "b": None, "c": "3"}]   # today: b="3", c=None
