"""The cascade baseline sends the same prompt for the same case on every run (#38)."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ORDER_PROBE = """
import sys, logging
logging.disable(logging.CRITICAL)
sys.path.insert(0, "..")
import llm_evaluate_cascade as C
cx = C.LLMExtractorEvaluator.__new__(C.LLMExtractorEvaluator)
table_def = {"name": "Appointment", "attributes": [
    {"name": "Patient", "constraints": {"foreign_key": {"table": "Patient", "column": "SSN"}}},
    {"name": "PrepNurse", "constraints": {"foreign_key": {"table": "Nurse", "column": "EmployeeID"}}},
    {"name": "Physician", "constraints": {"foreign_key": {"table": "Physician", "column": "EmployeeID"}}},
]}
answer = {"Patient": [{}], "Nurse": [{}], "Physician": [{}]}
merged = cx._merge_two_rows({"ID": 1, "Name": "A", "Dept": None}, {"ID": 1, "Dept": "B", "Phone": "C"})
print(";".join([",".join(cx._load_reference_tables(table_def, answer)),
                ",".join(cx._load_reference_tables_from_extracted(table_def, answer)),
                ",".join(merged)]))
"""


def test_reference_table_and_column_order_do_not_depend_on_hash_seed():          # report 046
    orders = set()
    for seed in range(6):
        env = {**os.environ, "PYTHONHASHSEED": str(seed), "OPENAI_API_KEY": "unused"}
        r = subprocess.run([sys.executable, "-c", ORDER_PROBE], cwd=ROOT / "evaluation",
                           env=env, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, r.stderr
        orders.add(r.stdout.strip().splitlines()[-1])
    assert orders == {"Patient,Nurse,Physician;Patient,Nurse,Physician;ID,Name,Dept,Phone"}, orders
