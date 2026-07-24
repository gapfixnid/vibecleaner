import re
from pathlib import Path


MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def test_repository_markdown_relative_links_resolve():
    root = Path(__file__).resolve().parents[1]
    documents = [root / "README.md", root / "README.en.md"]
    documents.extend((root / "docs").rglob("*.md"))
    documents.extend((root / "benchmarks").rglob("*.md"))
    missing: list[str] = []
    for document in documents:
        text = document.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip().split("#", 1)[0]
            if not target or "://" in target or target.startswith(("mailto:", "<")):
                continue
            target = target.rstrip(">")
            if not (document.parent / target).resolve().exists():
                missing.append(f"{document.relative_to(root)} -> {raw_target}")
    assert not missing, "Missing relative Markdown links:\n" + "\n".join(sorted(missing))
