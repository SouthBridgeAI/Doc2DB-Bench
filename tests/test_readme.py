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
