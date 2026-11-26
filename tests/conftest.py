"""Shared test setup. No test may call an LLM or need a real API key."""
import os
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))
sys.path.insert(0, str(ROOT))

# evaluation/test_dataset_evaluate.py builds an OpenAI client at import time and
# fails without a key (see issue "The evaluation scripts do not run from a clean clone").
# A dummy key lets the module import; no test makes a network call with it.
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-used")


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
def cascade(monkeypatch):
    """The cascade baseline's helper methods, without running __init__.

    llm_evaluate_cascade imports llm.ours, which is not in the repository;
    a stub stands in until that import is fixed.
    """
    stub = types.ModuleType("llm.ours")
    stub.get_answer = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "llm.ours", stub)
    import llm_evaluate_cascade

    return llm_evaluate_cascade.LLMExtractorEvaluator.__new__(llm_evaluate_cascade.LLMExtractorEvaluator)
