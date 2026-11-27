"""The leaderboard average is taken over the 42 dataset cases, not over the files that exist (report 034)."""
import json

import pytest

from leaderboard import (
    METRICS,
    DuplicateEvaluationError,
    average_over_cases,
    dataset_cases,
    safe_model_name,
)

SUFFIX = "_evaluate_pipeline_oracle.json"


@pytest.fixture
def dataset(tmp_path):
    """A fake dataset with the real benchmark's shape: 42 cases over 7 domains."""
    sizes = {"education": 3, "finance": 10, "medical": 3, "others": 10,
             "sports": 5, "transportation": 5, "university": 6}
    root = tmp_path / "dataset"
    for domain, n in sizes.items():
        for i in range(1, n + 1):
            d = root / domain / f"case{i}"
            d.mkdir(parents=True)
            (d / "schema.json").write_text("{}", encoding="utf-8")
    return root


def write_eval(out, domain, case, model, score, mode="only", subdir=None, **extra):
    prefix = f"{domain}_{case}_{safe_model_name(model)}_{mode}"
    d = out / domain / case / (subdir or prefix)
    d.mkdir(parents=True, exist_ok=True)
    data = {m: score for m in METRICS}
    data.update(extra)
    (d / f"{prefix}{SUFFIX}").write_text(json.dumps(data), encoding="utf-8")


def test_fake_dataset_matches_the_real_one(dataset):
    assert len(dataset_cases(dataset)) == 42


def test_missing_case_counts_zero(dataset, tmp_path):
    out = tmp_path / "outputs"
    cases = dataset_cases(dataset)
    scores = {c: float(i + 1) for i, c in enumerate(cases)}
    for (domain, case), s in scores.items():
        if (domain, case) != ("finance", "case3"):
            write_eval(out, domain, case, "gpt-4o", s)

    res = average_over_cases("gpt-4o", output_dir=out, dataset_dir=dataset)

    present = sum(s for c, s in scores.items() if c != ("finance", "case3"))
    assert res.n_cases == 42
    assert res.missing == ["finance/case3"]
    assert res.failed == []
    for m in METRICS:
        assert res.overall[m] == pytest.approx(present / 42)
    finance = [s for (d, c), s in scores.items() if d == "finance" and c != "case3"]
    assert res.per_domain["finance"]["cell_f1"] == pytest.approx(sum(finance) / 10)


def test_case_whose_file_records_a_failure_counts_zero(dataset, tmp_path):
    out = tmp_path / "outputs"
    for domain, case in dataset_cases(dataset):
        if (domain, case) == ("medical", "case2"):
            write_eval(out, domain, case, "gpt-4o", 80.0, status="failed", error="no output")
        else:
            write_eval(out, domain, case, "gpt-4o", 50.0)

    res = average_over_cases("gpt-4o", output_dir=out, dataset_dir=dataset)

    assert res.failed == ["medical/case2"]
    assert res.missing == []
    assert res.overall["cell_f1"] == pytest.approx(50.0 * 41 / 42)
    assert res.per_domain["medical"]["entity_f1"] == pytest.approx(100.0 / 3)


def test_unreadable_file_counts_as_failed(dataset, tmp_path):
    out = tmp_path / "outputs"
    for domain, case in dataset_cases(dataset):
        write_eval(out, domain, case, "gpt-4o", 42.0)
    bad = out / "sports/case1/sports_case1_gpt_4o_only" / f"sports_case1_gpt_4o_only{SUFFIX}"
    bad.write_text("{not json", encoding="utf-8")

    res = average_over_cases("gpt-4o", output_dir=out, dataset_dir=dataset)

    assert res.failed == ["sports/case1"]
    assert res.overall["llm_score"] == pytest.approx(42.0 * 41 / 42)


@pytest.mark.parametrize("model, other", [("gpt-5", "gpt-5-mini"), ("gpt-4o", "gpt-4o-mini")])
def test_substring_similar_models_are_not_mixed(dataset, tmp_path, model, other):
    out = tmp_path / "outputs"
    for domain, case in dataset_cases(dataset):
        write_eval(out, domain, case, model, 70.0)
        write_eval(out, domain, case, other, 10.0)

    assert average_over_cases(model, output_dir=out, dataset_dir=dataset).overall["cell_f1"] == pytest.approx(70.0)
    assert average_over_cases(other, output_dir=out, dataset_dir=dataset).overall["cell_f1"] == pytest.approx(10.0)


def test_modes_are_not_mixed(dataset, tmp_path):
    out = tmp_path / "outputs"
    for domain, case in dataset_cases(dataset):
        write_eval(out, domain, case, "gpt-4o", 60.0, mode="single")
        if domain != "education":
            write_eval(out, domain, case, "gpt-4o", 20.0, mode="multi")

    single = average_over_cases("gpt-4o", mode="single", output_dir=out, dataset_dir=dataset)
    multi = average_over_cases("gpt-4o", mode="multi", output_dir=out, dataset_dir=dataset)
    assert single.overall["cell_f1"] == pytest.approx(60.0) and single.missing == []
    assert multi.overall["cell_f1"] == pytest.approx(20.0 * 39 / 42)
    assert len(multi.missing) == 3
    assert average_over_cases("gpt-4o", output_dir=out, dataset_dir=dataset).missing == [
        f"{d}/{c}" for d, c in dataset_cases(dataset)
    ]


def test_duplicate_files_for_one_case_raise(dataset, tmp_path):
    out = tmp_path / "outputs"
    for domain, case in dataset_cases(dataset):
        write_eval(out, domain, case, "gpt-4o", 50.0)
    write_eval(out, "university", "case6", "gpt-4o", 90.0, subdir="rerun")

    with pytest.raises(DuplicateEvaluationError, match="university/case6"):
        average_over_cases("gpt-4o", output_dir=out, dataset_dir=dataset)


def test_successful_file_without_a_metric_raises(dataset, tmp_path):
    out = tmp_path / "outputs"
    for domain, case in dataset_cases(dataset):
        write_eval(out, domain, case, "gpt-4o", 50.0, llm_score=None)

    with pytest.raises(ValueError, match="llm_score"):
        average_over_cases("gpt-4o", output_dir=out, dataset_dir=dataset)
