import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = sorted(
    str(p.parent.relative_to(ROOT / "dataset"))
    for p in (ROOT / "dataset").glob("*/case*/schema.json")
)


def load_case(evaluator, case):
    d = ROOT / "dataset" / case
    info = {
        "answer_source": "tables" if (d / "tables").is_dir() else "folder",
        "answer_path": d / "tables",
        "answer_file": d / "answer.json" if (d / "answer.json").exists() else None,
        "answer_dir": d / "answer" if (d / "answer").is_dir() else None,
    }
    schema = json.loads((d / "schema.json").read_text(encoding="utf-8"))
    return schema, evaluator.load_expected_answer(info)


def test_dataset_has_42_cases():
    assert len(CASES) == 42


def test_ground_truth_scores_100_against_itself_smoke(evaluator):
    schema, gt = load_case(evaluator, "medical/case1")
    m = evaluator.calculate_cell_metrics(gt, gt, schema=schema)
    assert m["total_expected_cells"] > 0
    assert m["cell_f1"] == pytest.approx(100.0)


@pytest.mark.slow
@pytest.mark.parametrize("case", CASES)
def test_ground_truth_scores_100_against_itself(evaluator, case):
    schema, gt = load_case(evaluator, case)
    m = evaluator.calculate_cell_metrics(gt, gt, schema=schema)
    assert m["total_expected_cells"] > 0
    assert m["cell_f1"] == pytest.approx(100.0)
