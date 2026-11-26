# Doc2DB-Bench Evaluation Guide

`evaluation/` is the directory in `Doc2DB-Bench` used for extraction evaluation, baseline comparison, and result aggregation.  
It includes more than `test_dataset_evaluate.py`: it also contains several baseline methods, analysis notebooks, and shared evaluation utilities.

## Directory Structure

```text
evaluation/
├── README.md
├── utils.py
├── test_dataset_evaluate.py
├── llm_evaluate_cascade.py
├── docetl_evaluate.py
├── langchain_evaluate.py
├── langextract_evaluate.py
├── clean_llamaextract_result.py
├── fine_grained_capability_evaluation.ipynb
├── result.ipynb
```

## File Overview

### 1. Main Evaluation Script

- [test_dataset_evaluate.py](./test_dataset_evaluate.py)  
  Main evaluation script. It processes documents, saves `output_tables.json`, and computes structured extraction metrics.

### 2. Extraction Scripts

| Script | Method | Official Link |
|---|---|---|
| [llm_evaluate_cascade.py](./llm_evaluate_cascade.py) | In-repo LLM cascade extraction baseline. Supports `oracle`, `pipeline`, and `pipeline-oracle` modes. | In-repo implementation |
| [docetl_evaluate.py](./docetl_evaluate.py) | Structured extraction and evaluation based on DocETL. | [DocETL GitHub](https://github.com/ucbepic/docetl) |
| [langchain_evaluate.py](./langchain_evaluate.py) | Structured extraction and evaluation based on LangChain + PydanticOutputParser. | [LangChain GitHub](https://github.com/langchain-ai/langchain), [LangChain Website](https://www.langchain.com) |
| [langextract_evaluate.py](./langextract_evaluate.py) | Structured extraction and evaluation based on LangExtract. | [LangExtract GitHub](https://github.com/google/langextract) |

### 3. Result Analysis

- [fine_grained_capability_evaluation.ipynb](./fine_grained_capability_evaluation.ipynb)  
  Notebook for fine-grained capability analysis.

- [result.ipynb](./result.ipynb)  
  Notebook for result organization and analysis.

## Quick Evaluation

A common quick evaluation workflow looks like this:

### 1. Run LLM extraction or another baseline

Choose one extraction method first and generate structured extraction outputs, for example:

```bash
python llm_evaluate_cascade.py --eval-mode pipeline --model gpt-4o
python docetl_evaluate.py --model gpt-4o
python langchain_evaluate.py --model gpt-4o
python langextract_evaluate.py --model gpt-4o
```

The goal of this step is to produce:

- `output_tables.json`
- `extracted_data.json`
- `metadata.json`

### 2. Evaluate with `test_dataset_evaluate.py`

Once extraction outputs are ready, use the main evaluator to compute structured metrics, for example:

```bash
python test_dataset_evaluate.py --evaluate-only
python test_dataset_evaluate.py --evaluate-all-methods
```

This step usually produces:

- `*_evaluate.json`
- optional Excel summary reports

### Data and output folders

Every script reads the cases from `dataset/` (`dataset/<domain>/<case>/`) and writes to `outputs/<method>/` at the repository root, for example `outputs/llm/` for `llm_evaluate_cascade.py` and `test_dataset_evaluate.py`. `outputs/` is git-ignored. Use `--dataset-dir` and `--output-dir` to point elsewhere; to evaluate another method's outputs, pass its folder, for example `python test_dataset_evaluate.py --evaluate-all-methods --output-dir ../outputs/docetl`.

A run exits with status 1 when it finds no case, or when any case fails or has no output, so a batch script or CI job can tell that nothing was scored.

### 3. Use `result.ipynb` for fine-grained analysis

After evaluation finishes, use [result.ipynb](./result.ipynb) to inspect and organize results.

If you need finer capability breakdowns, also use:

- [fine_grained_capability_evaluation.ipynb](./fine_grained_capability_evaluation.ipynb)

## Evaluation Scope and Data Flow

`evaluation/` mainly covers structured extraction evaluation.

### Structured Extraction Evaluation

The goal is to compare extraction quality for the task “documents -> table data”.

Typical inputs:

- `docs/`
- `schema.json`
- `answer.json` or equivalent ground-truth answer directories

Typical outputs:

- `output_tables.json`
- `metadata.json`
- `processing_steps.json`
- `*_evaluate.json`

## Main Evaluation: `test_dataset_evaluate.py`

This is the most complete structured extraction evaluation script in the directory.

**Use `--evaluate-only`.** It scores outputs that an extraction script (step 1 above) has already written, and needs nothing beyond this repository. Without `--evaluate-only`, the script sends each case's documents to a Doc2DB extraction service at `--backend-url` (default `http://localhost:5000`, endpoints `/api/upload` and `/api/doc2db/process`). That service is not included in this repository.

Its full workflow is:

1. Scan the test dataset directory
2. Process documents and generate extraction outputs (end-to-end mode only, through the external service)
3. Extract table data from the results
4. Save `output_tables.json`
5. Compute structured extraction metrics
6. Generate `*_evaluate.json`
7. Optionally aggregate results into Excel reports

### Typical Use Cases

- Evaluate Doc2DB extraction results
- Compare multiple output directories in a unified way
- Generate batch structured metrics and summary reports

### Common Usage

Full processing + evaluation (requires the external extraction service at `--backend-url`):

```bash
python test_dataset_evaluate.py
python test_dataset_evaluate.py --model gpt-4o
python test_dataset_evaluate.py --model gpt-4o --document-mode multi
python test_dataset_evaluate.py --model gpt-4o --run-name exp_001
```

Evaluate existing outputs only:

```bash
python test_dataset_evaluate.py --model gpt-4o --evaluate-only
python test_dataset_evaluate.py --model gpt-4o --document-mode multi --evaluate-only --run-name evaluation_001
```

The LLM judge score (`llm_score`, judged by the pinned `gpt-4o-2024-08-06`) is computed by default; `--no-llm-eval` skips it and stores `llm_score` as `null`, as does a judge call that fails.

Evaluate outputs from all methods:

```bash
python test_dataset_evaluate.py --evaluate-all-methods
python test_dataset_evaluate.py --evaluate-all-methods --force-reevaluate
```

Generate Excel summaries:

```bash
python test_dataset_evaluate.py --generate-excel
python test_dataset_evaluate.py --generate-excel --excel-output ./report.xlsx
```

## Evaluation modes

`llm_evaluate_cascade.py --eval-mode` decides what the model is shown. `test_dataset_evaluate.py --eval-mode` must name the same mode, so that it scores the matching output file.

| Mode | The model sees | Use it for |
|---|---|---|
| `pipeline` (default) | The documents and the schema only. Tables that refer to other tables are given the model's own earlier extractions, in full. The prompt says how to number records the documents do not identify. The ground truth is never read before scoring. | **Evaluating a system, and comparing with others.** Recommended for third-party users. |
| `pipeline-oracle` | Its own extractions for entity tables. For each relationship table, the referenced ground-truth entity tables, identifiers included, cut to the first 50 rows. | Analysis: relationship extraction with correct entity context. The published leaderboard uses this mode. |
| `oracle` | Ground-truth rows in place of every entity table that has no foreign key, and ground-truth reference tables for the others. | Analysis: an upper bound on relationship extraction. |

Each output's `metadata.json` records the mode it was produced in, and whether it used the ground truth (`"uses_ground_truth"`). Scores from different modes are not comparable. Report the mode next to every number.

The DocETL, LangChain and LangExtract baselines have no modes. They read the ground truth only to score their output after extraction.

### How identifiers are scored

Most primary keys in the dataset are surrogate IDs that no document states. A system can't extract them, only invent them. What it can get right is which records they connect: which patient an appointment is for, which physician belongs to which department.

So by default, `test_dataset_evaluate.py` scores those identifiers **up to a consistent renaming**:

1. For each table whose primary key is a single column, isn't a foreign key, and isn't stated in the documents (`meta.json` `if_primary_allowed`), the system's rows are paired one-to-one with ground-truth rows on their other columns.
2. Each of the system's IDs is renamed to the ID of the row it paired with, in that column and in every foreign key that points to it.
3. The cells are then scored as usual.

A system that numbers its records 1, 2, 3… and uses each number consistently can reach 100. A foreign key that links the wrong record is still wrong. An ID that pairs with no ground-truth row matches nothing. IDs the documents do state are scored exactly as written. This happens after extraction, on the scorer's side, so the model never sees the ground truth.

`--literal-keys` turns this off and scores every identifier as a literal value, as the published leaderboard did. Each `*_evaluate.json` records which rule was used (`"key_matching": "aligned"` or `"literal"`).

## Baseline Usage

The other scripts under `evaluation/` are mainly for baseline comparison. They typically read local datasets and documents directly.

### 1. LLM Cascade Baseline

Script: [llm_evaluate_cascade.py](./llm_evaluate_cascade.py)

Supported modes: see [Evaluation modes](#evaluation-modes). `pipeline` is the default.

Examples:

```bash
python llm_evaluate_cascade.py --eval-mode oracle
python llm_evaluate_cascade.py --eval-mode pipeline
python llm_evaluate_cascade.py --eval-mode pipeline-oracle
python llm_evaluate_cascade.py --model gpt-4o --run-name exp_001 --eval-mode oracle
python llm_evaluate_cascade.py --force-rerun --eval-mode pipeline
python llm_evaluate_cascade.py --db-name medical --case-name case2 --model glm-5.1 --eval-mode pipeline-oracle
```

### 2. DocETL Baseline

Script: [docetl_evaluate.py](./docetl_evaluate.py)

Examples:

```bash
python docetl_evaluate.py
python docetl_evaluate.py --model gpt-4o
python docetl_evaluate.py --force-rerun
python docetl_evaluate.py --db-name transportation --case-name case1 --model gpt-5.4
python docetl_evaluate.py --model gpt-4o --run-name baseline_test --force-rerun
```

### 3. LangChain Baseline

Script: [langchain_evaluate.py](./langchain_evaluate.py)

Characteristics:

- Uses `ChatOpenAI`
- Uses `PydanticOutputParser`
- Produces structured JSON directly for downstream evaluation

### 4. LangExtract Baseline

Script: [langextract_evaluate.py](./langextract_evaluate.py)

Examples:

```bash
python langextract_evaluate.py
python langextract_evaluate.py --model gpt-4o
python langextract_evaluate.py --model gpt-5.4 --extraction-passes 1
python langextract_evaluate.py --data-name medical --case-name case2 --model gpt-5.4
python langextract_evaluate.py --model gpt-4o --extraction-passes 1 --run-name baseline_test
```

## Output and Result Files

Different scripts produce slightly different output layouts, but they generally follow a structure organized by method / database / case / model.

Common files include:

- `output_tables.json`  
  Normalized table extraction output. Most downstream evaluation and comparison use this file.

- `extracted_data.json`  
  Raw structured extraction output directly generated by a baseline.

- `metadata.json`  
  Metadata such as model, method, timestamp, and run name.

- `processing_steps.json`  
  Step-level processing information.

- `*_evaluate.json`  
  Per-case evaluation results.

- `*.xlsx`  
  Aggregated summary reports.

### Role of `output_tables.json`

This is the key intermediate format in structured evaluation.  
Whether the source comes from:

- baseline extraction output
- fallback extraction from `full_result`, `snapshot`, or `table_data`

the final result is normalized as much as possible into:

```json
{
  "table_name_1": [
    {"col_a": "value1", "col_b": "value2"}
  ],
  "table_name_2": [
    {"col_x": "value3"}
  ]
}
```

## Evaluation Metrics

### 1. Cell-level Metrics

- `Cell Recall`
- `Cell Precision`
- `Cell F1`

### 2. Structure-level Metrics

- `Table Recall / Precision`
- `Field Recall / Precision`
- `Entity / Relation F1`

### 3. LLM Fine-grained Scoring

Some scripts additionally call an LLM to score output quality. Typical fields include:

- `llm_score`
- `llm_accuracy`
- `llm_completeness`
- `llm_consistency`
- `llm_coverage`
- `llm_comments`

### 4. Notebook Analysis

1. `fine_grained_capability_evaluation.ipynb`

- capability-level error analysis
- case / relation-type breakdown
- output-directory comparison

2. `result.ipynb`

- overall result browsing
- summary organization
- tabular analysis
