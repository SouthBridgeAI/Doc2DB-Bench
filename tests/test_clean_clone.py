"""The evaluation scripts work from a fresh clone, with no API keys set (#3)."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith(("OPENAI_", "GPT_"))}


def run_python(code, env=CLEAN_ENV):
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT / "evaluation", env=env,
                          capture_output=True, text=True, timeout=120)


def test_scorer_imports_without_api_key():
    r = run_python("import test_dataset_evaluate")
    assert r.returncode == 0, r.stderr


def test_cascade_baseline_imports_without_api_key():
    r = run_python("import sys; sys.path.insert(0, '..'); import llm_evaluate_cascade")
    assert r.returncode == 0, r.stderr


@pytest.mark.xfail(strict=True, reason="#3: scripts read dataset/case/base_latest")
def test_evaluator_finds_the_shipped_dataset(tmp_path):
    r = run_python(
        "import test_dataset_evaluate as T, pathlib; "
        f"ev = T.Doc2DBEvaluator('http://unused', T.DATASET_DIR, pathlib.Path(r'{tmp_path}'), enable_llm_eval=False); "
        "print(len(ev.scan_datasets()))",
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().splitlines()[-1] == "42"


@pytest.mark.xfail(strict=True, reason="#3: no --dataset-dir option, and exit 0 when no case is found")
def test_evaluator_exits_nonzero_when_it_finds_no_cases(tmp_path):
    script = [sys.executable, "test_dataset_evaluate.py"]
    help_text = subprocess.run(script + ["--help"], cwd=ROOT / "evaluation", env=CLEAN_ENV,
                               capture_output=True, text=True, timeout=120).stdout
    assert "--dataset-dir" in help_text
    r = subprocess.run(script + ["--evaluate-only", "--dataset-dir", str(tmp_path)],
                       cwd=ROOT / "evaluation", env=CLEAN_ENV, capture_output=True, text=True, timeout=120)
    assert r.returncode != 0
