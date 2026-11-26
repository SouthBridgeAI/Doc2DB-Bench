"""The documents a system reads contain no leftover generator markup (#7)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Tags such as <r0_c3>...</r0_c3> encode the ground-truth row and column a passage was written from.
SYNTHESIS_TAG = re.compile(r"</?r\d+(_c?\d+)+>")


def test_documents_contain_no_synthesis_tags():
    offenders = [str(p.relative_to(ROOT)) for p in sorted((ROOT / "dataset").glob("*/case*/docs/*.md"))
                 if SYNTHESIS_TAG.search(p.read_text(encoding="utf-8"))]
    assert offenders == []
