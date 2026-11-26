"""What the extraction model is shown in each evaluation mode (#7)."""
import builtins
import io
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUB_RESPONSE = "<TABLE BEGIN>\n| x |\n|---|\n| 1 |\n<TABLE END>"


def run_case(tmp_path, monkeypatch, eval_mode, case=("medical", "case1")):
    """Run one case through the cascade with the model stubbed out and every ground-truth file read refused."""
    import llm_evaluate_cascade

    ev = llm_evaluate_cascade.LLMExtractorEvaluator(
        model="stub-model", dataset_dir=ROOT / "dataset", output_dir=tmp_path,
        eval_mode=eval_mode, db_name_filter=case[0], case_name_filter=case[1],
    )
    prompts = []

    def stub_llm(user_prompt, system_prompt=None, model_name=None):
        prompts.append(f"{system_prompt or ''}\n{user_prompt}")
        return STUB_RESPONSE

    monkeypatch.setattr(ev, "_call_llm", stub_llm)
    [case_info] = ev.scan_datasets()

    case_dir = Path(case_info["case_dir"]).resolve()
    ground_truth = {case_dir / "tables", case_dir / "answer", case_dir / "answer.json"}
    real_open = builtins.open

    def guarded_open(file, *args, **kwargs):
        path = Path(file).resolve() if isinstance(file, (str, Path)) else None
        if path and any(path == g or g in path.parents for g in ground_truth):
            raise PermissionError(f"ground truth read: {path}")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(io, "open", guarded_open)
    try:
        result = ev.process_case(case_info)
    finally:
        monkeypatch.undo()
    return result, prompts, tmp_path


def test_pipeline_mode_never_reads_the_ground_truth(tmp_path, monkeypatch):
    result, prompts, out = run_case(tmp_path, monkeypatch, "pipeline")
    assert result["status"] == "success", result.get("error")
    assert prompts
    [metadata] = out.glob("medical/case1/*/metadata.json")
    assert json.loads(metadata.read_text())["pipeline"]["uses_ground_truth"] is False


@pytest.mark.parametrize("eval_mode", ["oracle", "pipeline-oracle"])
def test_oracle_modes_read_the_ground_truth(tmp_path, monkeypatch, eval_mode):
    # Shows that the guard above detects reads: these modes need the ground truth, so they fail under it.
    result, _, _ = run_case(tmp_path, monkeypatch, eval_mode)
    assert result["status"] == "failed"
    assert "ground truth read" in result["error"]

