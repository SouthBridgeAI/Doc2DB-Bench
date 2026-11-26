import pytest

# Replace each reason with the GitHub issue number once the issues are filed.
def known(reason):
    return pytest.mark.xfail(strict=True, reason=reason)


@pytest.mark.parametrize("expected, generated, match", [
    ("TRUE", True, True), ("FALSE", False, True), ("true", True, True),   # report 026
    (1, True, True), (0, False, True), ("TRUE", "yes", True),             # 0/1 in BOOLEAN columns (medical/case1)
    ("TRUE", False, False), (1, False, False), ("FALSE", "TRUE", False),
    (2, True, False),                                                     # 2 is not a boolean
])
def test_booleans_match_across_spellings(evaluator, expected, generated, match):
    assert evaluator.compare_cell_values(expected, generated)["match"] is match


def test_numbers_are_not_read_as_booleans(evaluator):
    assert evaluator.compare_cell_values(1, 1)["match"]
    assert not evaluator.compare_cell_values(1, 0)["match"]


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


# Pairing the identical rows first (greedy) leaves the other two rows below the 0.3 threshold;
# crossing them pairs both rows and finds 5 correct cells instead of 4 (report 028).
ROW_PAIRING_GT = {"T": [{"a": "alpha", "b": "bravo", "c": "charlie", "d": "delta"},
                        {"a": "alpha", "b": "bravo", "c": "charlie", "d": "zzzzzzzzzz"}]}
ROW_PAIRING_GEN = {"T": [{"a": "alpha", "b": "bravo", "c": "charlie", "d": "delta"},
                         {"a": "alpha", "b": "qqqqqqqqqq", "c": "wwwwwwwwww", "d": "delta"}]}


def test_row_pairing_maximises_total_similarity(evaluator):
    m = evaluator.calculate_cell_metrics(ROW_PAIRING_GEN, ROW_PAIRING_GT)
    assert m["total_correct_cells"] == 5   # was 4 (report 028)


def test_row_pairing_maximises_total_similarity_in_entity_and_relation_scores(evaluator):
    schema = [{"name": "T", "type": "entity", "fields": [{"name": f, "constraints": {}} for f in "abcd"]}]
    m = evaluator.calculate_entity_relation_metrics(ROW_PAIRING_GEN, ROW_PAIRING_GT, schema)
    assert m["entity_correct_cells"] == 5  # was 4 (report 028)


def test_time_with_seconds_matches(evaluator):
    assert evaluator.compare_cell_values("2008-04-24 10:00", "2008-04-24 10:00:00")["match"]


@pytest.mark.parametrize("expected, generated, match", [
    ("1981-8-1", "1981-08-01", True),
    ("2008-04-24T10:00:00", "2008-04-24 10:00", True),
    ("2008-04-24", "2008-04-25", False),
    ("2008-04-24 10:00", "2008-04-24 10:01", False),
])
def test_dates_compared_at_ground_truth_precision(evaluator, expected, generated, match):
    assert evaluator.compare_cell_values(expected, generated)["match"] is match


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
