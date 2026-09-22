"""
Tests for disambiguate.usage: a term linked from anywhere in the repo is in use.

Prune assumed link reachability from the roots was the only form of
use, so a fresh stamp lost every vendored term that agent docs and
scripts link without the roots linking them (disambiguate#84). Use is
an explicit cross-reference to the term, markdown or wiki syntax, in
any text file the repo carries, the glossary directory itself
excluded. A bare mention is never use: that is drift's finding.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from disambiguate.glossary import load_glossary
from disambiguate.usage import linked_slugs

CONSENT = "<!-- d10e: auto-prune -->"
# Resolved once: the fixtures need a real repo, and a resolved path is
# what the bandit rule on partial executable paths asks for.
GIT = shutil.which("git") or "git"
TERMS = {
    "session-memory": f"## Session-memory\n\n{CONSENT}\n\nThe store.\n",
    "agent-session": f"## Agent session\n\n{CONSENT}\n\nOne run.\n",
    "term": f"## Term\n\n{CONSENT}\n\nA word.\n",
    "principal": f"## Principal\n\n{CONSENT}\n\nThe human.\n",
}


def _repo(tmp_path: Path, *, real_git: bool) -> Path:
    glossary = tmp_path / "docs" / "glossary"
    glossary.mkdir(parents=True)
    for slug, body in TERMS.items():
        (glossary / f"{slug}.md").write_text(body, encoding="utf-8")
    if real_git:
        subprocess.run(  # noqa: S603 - args are controlled test data.
            [GIT, "init", "-q"], cwd=tmp_path, check=True
        )
    else:
        (tmp_path / ".git").mkdir()
    return tmp_path


def _linked(repo: Path) -> set[str]:
    return linked_slugs(load_glossary(repo / "docs" / "glossary"), repo)


def test_markdown_and_wiki_links_count_from_any_path(tmp_path: Path) -> None:
    repo = _repo(tmp_path, real_git=False)
    (repo / "AGENTS.md").write_text(
        "Records go to the [store](docs/glossary/session-memory.md).\n",
        encoding="utf-8",
    )
    (repo / "notes").mkdir()
    (repo / "notes" / "run.md").write_text("One [[agent-session]] per ticket.\n")

    assert _linked(repo) == {"session-memory", "agent-session"}


@pytest.mark.xfail(strict=True, reason="red: use by link (disambiguate#84)")
def test_a_bare_mention_is_not_use(tmp_path: Path) -> None:
    """The same spelling can mean something else; only a link commits."""
    repo = _repo(tmp_path, real_git=False)
    (repo / "AGENTS.md").write_text(
        "The principal rules. One agent session per ticket. A term is a word.\n",
        encoding="utf-8",
    )
    (repo / ".github").mkdir()
    (repo / ".github" / "ci.yml").write_text("name: session-memory\n")

    assert _linked(repo) == set()


@pytest.mark.xfail(strict=True, reason="red: use by link (disambiguate#84)")
def test_a_link_inside_code_is_not_use(tmp_path: Path) -> None:
    repo = _repo(tmp_path, real_git=False)
    (repo / "notes.md").write_text(
        "Write `[x](principal.md)` to link.\n\n```md\n[[term]]\n```\n",
        encoding="utf-8",
    )

    assert _linked(repo) == set()


def test_a_link_to_an_unknown_slug_is_ignored(tmp_path: Path) -> None:
    repo = _repo(tmp_path, real_git=False)
    (repo / "README.md").write_text("See [that](docs/other.md) and [[nowhere]].\n")

    assert _linked(repo) == set()


def test_the_glossary_directory_itself_never_counts(tmp_path: Path) -> None:
    repo = _repo(tmp_path, real_git=False)
    (repo / "docs" / "glossary" / "principal.md").write_text(
        f"## Principal\n\n{CONSENT}\n\nOwns a [store](session-memory.md).\n",
        encoding="utf-8",
    )

    assert _linked(repo) == set()


def test_untracked_files_of_a_fresh_stamp_count(tmp_path: Path) -> None:
    """The post-stamp prune runs before the first commit."""
    repo = _repo(tmp_path, real_git=True)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "doctor.sh").write_text(
        "# see [principal](../docs/glossary/principal.md)\n", encoding="utf-8"
    )

    assert _linked(repo) == {"principal"}


def test_ignored_files_do_not_count(tmp_path: Path) -> None:
    repo = _repo(tmp_path, real_git=True)
    (repo / ".gitignore").write_text("build/\n", encoding="utf-8")
    (repo / "build").mkdir()
    (repo / "build" / "out.md").write_text("[[principal]]\n", encoding="utf-8")

    assert _linked(repo) == set()


def test_binary_files_are_skipped(tmp_path: Path) -> None:
    repo = _repo(tmp_path, real_git=False)
    (repo / "blob.bin").write_bytes(b"[[principal]]\x00\x01\x02" * 4)

    assert _linked(repo) == set()


def test_a_tree_without_a_usable_git_is_walked_directly(tmp_path: Path) -> None:
    repo = _repo(tmp_path, real_git=False)
    (repo / "README.md").write_text("A [[principal]] reads this.\n", encoding="utf-8")

    assert _linked(repo) == {"principal"}
