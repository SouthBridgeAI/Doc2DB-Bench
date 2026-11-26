import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_readme_links_point_to_existing_files():
    visible = re.sub(r"<!--.*?-->", "", README, flags=re.S)
    targets = re.findall(r"\]\((\./[^)#\s]+)\)", visible) + re.findall(r'src="(?!http)([^"]+)"', visible)
    assert [t for t in targets if not (ROOT / t).exists()] == []


def test_readme_repository_tree_matches_the_repository():
    tree = re.search(r"```text\nDoc2DB-Bench/\n(.*?)```", README, re.S).group(1)
    stack, missing = [], []
    for line in tree.splitlines():
        m = re.match(r"^((?:│   |    )*)[├└]── (.+?)\s*$", line)
        if not m:
            continue
        depth = len(m.group(1)) // 4
        stack = stack[:depth] + [m.group(2).rstrip("/")]
        if not (ROOT.joinpath(*stack)).exists():
            missing.append("/".join(stack))
    assert missing == []


def test_matching_examples_in_the_evaluation_readme_hold(evaluator):
    """The examples table in evaluation/README.md agrees with the scorer."""
    import json

    text = (ROOT / "evaluation" / "README.md").read_text(encoding="utf-8")
    block = re.search(r"<!-- matching-examples:start -->(.*?)<!-- matching-examples:end -->", text, re.S).group(1)
    rows = re.findall(r"^\| `(.+?)` \| `(.+?)` \| (yes|no) \|$", block, re.M)
    assert len(rows) >= 10
    for expected, generated, match in rows:
        result = evaluator.compare_cell_values(json.loads(expected), json.loads(generated))["match"]
        assert result is (match == "yes"), (expected, generated)
