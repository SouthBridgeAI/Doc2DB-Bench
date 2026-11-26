"""Shared test setup. No test may call an LLM or need a real API key."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))
sys.path.insert(0, str(ROOT))


@pytest.fixture
def evaluator(tmp_path):
    """The repository's scorer, with LLM judging off and output written to a temp dir."""
    import test_dataset_evaluate

    return test_dataset_evaluate.Doc2DBEvaluator(
        backend_url="http://unused",
        dataset_dir=tmp_path,
        output_dir=tmp_path / "out",
        enable_llm_eval=False,
    )


@pytest.fixture
def cascade():
    """The cascade baseline's helper methods, without running __init__."""
    import llm_evaluate_cascade

    return llm_evaluate_cascade.LLMExtractorEvaluator.__new__(llm_evaluate_cascade.LLMExtractorEvaluator)
