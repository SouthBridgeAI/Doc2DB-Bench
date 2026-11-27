"""Leaderboard averaging: one score per dataset case, missing or failed cases count 0.

The average is taken over the benchmark's cases (every ``dataset/<domain>/<case>/schema.json``),
not over the evaluation files that happen to exist, so a case that failed or was never run
lowers a model's score instead of disappearing from it.

Evaluation files are found by their exact name, which ``test_dataset_evaluate.py`` builds as
``<output_dir>/<domain>/<case>/<prefix>/<prefix><suffix>`` with
``prefix = f"{domain}_{case}_{safe_model}_{mode}"``. ``mode`` is the folder's last part:
``only`` for the cascade baseline (``llm_evaluate_cascade.py``), ``single`` or ``multi`` for
backend runs. ``suffix`` depends on the evaluation mode (see ``EVAL_FILE_SUFFIXES``).
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

DATASET_DIR = Path(__file__).resolve().parent.parent / "dataset"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs" / "llm"

METRICS = (
    "entity_precision", "entity_recall", "entity_f1",
    "relation_precision", "relation_recall", "relation_f1",
    "cell_precision", "cell_recall", "cell_f1",
    "llm_score",
)

EVAL_FILE_SUFFIXES = {
    "pipeline": "_evaluate.json",
    "pipeline-oracle": "_evaluate_pipeline_oracle.json",
    "oracle": "_evaluate_oracle.json",
}


class DuplicateEvaluationError(ValueError):
    """More than one evaluation file was found for one model, mode and case."""


def safe_model_name(model: str) -> str:
    """The model name as it appears in output folder and file names (same rule as the scripts)."""
    return model.replace("/", "_").replace("\\", "_").replace("-", "_")


def dataset_cases(dataset_dir: Path = DATASET_DIR) -> List[Tuple[str, str]]:
    """Every benchmark case as ``(domain, case)``, sorted."""
    return sorted((p.parent.parent.name, p.parent.name) for p in Path(dataset_dir).glob("*/case*/schema.json"))


def find_evaluation_file(output_dir: Path, domain: str, case: str, model: str, mode: str,
                         eval_mode: str = "pipeline-oracle") -> Optional[Path]:
    """The one evaluation file for this model, mode and case, or None if there is none.

    The file name must match exactly, so ``gpt-5`` never picks up ``gpt-5-mini`` and ``only``
    never picks up ``multi``. Raises DuplicateEvaluationError if the name occurs more than once
    under the case's folder.
    """
    suffix = EVAL_FILE_SUFFIXES[eval_mode]
    name = f"{domain}_{case}_{safe_model_name(model)}_{mode}{suffix}"
    case_dir = Path(output_dir) / domain / case
    if not case_dir.is_dir():
        return None
    matches = sorted(p for p in case_dir.rglob(f"*{suffix}") if p.name == name and p.is_file())
    if len(matches) > 1:
        raise DuplicateEvaluationError(
            f"{len(matches)} evaluation files for model={model!r} mode={mode!r} "
            f"case={domain}/{case}: " + ", ".join(str(m) for m in matches)
        )
    return matches[0] if matches else None


def _read_case(path: Path, metrics: Sequence[str]) -> Tuple[str, Optional[str], Dict[str, float]]:
    """(status, error, scores) for one evaluation file; a failed case scores 0."""
    zeros = {m: 0.0 for m in metrics}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        return "failed", f"unreadable evaluation file: {e}", zeros
    if not isinstance(data, dict):
        return "failed", "evaluation file is not a JSON object", zeros
    if data.get("status", "success") != "success" or data.get("error"):
        return "failed", str(data.get("error") or f"status={data.get('status')!r}"), zeros
    scores = {}
    for m in metrics:
        v = data.get(m)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(f"{path}: metric {m!r} is {v!r}, expected a number")
        scores[m] = float(v)
    return "ok", None, scores


def case_scores(model: str, mode: str = "only", eval_mode: str = "pipeline-oracle",
                output_dir: Path = OUTPUT_DIR, dataset_dir: Path = DATASET_DIR,
                metrics: Sequence[str] = METRICS) -> List[dict]:
    """One row per dataset case: domain, case, model, mode, status, error, file, and every metric.

    ``status`` is ``ok``, ``missing`` (no evaluation file) or ``failed`` (the file records a
    failure or cannot be read). Missing and failed cases score 0 for every metric.
    """
    cases = dataset_cases(dataset_dir)
    if not cases:
        raise ValueError(f"no cases found under {dataset_dir}")
    rows = []
    for domain, case in cases:
        path = find_evaluation_file(output_dir, domain, case, model, mode, eval_mode)
        if path is None:
            status, error, scores = "missing", None, {m: 0.0 for m in metrics}
        else:
            status, error, scores = _read_case(path, metrics)
        rows.append({
            "domain": domain, "case": case, "model": model, "mode": mode,
            "status": status, "error": error, "file": str(path) if path else None,
            **scores,
        })
    return rows


def mean_scores(rows: Sequence[dict], metrics: Sequence[str] = METRICS) -> Dict[str, Optional[float]]:
    """Mean of each metric over ``rows`` (each row is one case); None for no rows."""
    return {m: (sum(r[m] for r in rows) / len(rows) if rows else None) for m in metrics}


@dataclass
class LeaderboardAverage:
    model: str
    mode: str
    eval_mode: str
    overall: Dict[str, float]
    per_domain: Dict[str, Dict[str, float]]
    cases: List[dict] = field(repr=False)

    @property
    def n_cases(self) -> int:
        return len(self.cases)

    @property
    def missing(self) -> List[str]:
        return [f"{r['domain']}/{r['case']}" for r in self.cases if r["status"] == "missing"]

    @property
    def failed(self) -> List[str]:
        return [f"{r['domain']}/{r['case']}" for r in self.cases if r["status"] == "failed"]


def average_over_cases(model: str, mode: str = "only", eval_mode: str = "pipeline-oracle",
                       output_dir: Path = OUTPUT_DIR, dataset_dir: Path = DATASET_DIR,
                       metrics: Sequence[str] = METRICS) -> LeaderboardAverage:
    """Average each metric over all dataset cases, overall and per domain.

    Every case counts once; a missing or failed case counts 0. ``missing`` and ``failed`` on
    the result list which cases those were.
    """
    rows = case_scores(model, mode, eval_mode, output_dir, dataset_dir, metrics)
    domains = sorted({r["domain"] for r in rows})
    return LeaderboardAverage(
        model=model, mode=mode, eval_mode=eval_mode,
        overall=mean_scores(rows, metrics),
        per_domain={d: mean_scores([r for r in rows if r["domain"] == d], metrics) for d in domains},
        cases=rows,
    )
