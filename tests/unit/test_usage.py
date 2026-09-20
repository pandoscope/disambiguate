"""
Tests for disambiguate.usage: a term mentioned anywhere in the repo is in use.

Prune assumed link reachability from the roots was the only form of
use, so a fresh stamp lost every vendored term that agent docs, scripts
and workflows name without linking (disambiguate#84). A mention is a
case-insensitive, hyphen-aware whole-word occurrence of the term's
canonical name or slug in any text file the repo carries, the glossary
directory itself excluded.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from disambiguate.glossary import load_glossary
from disambiguate.usage import mentioned_slugs

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


def _mentioned(repo: Path) -> set[str]:
    return mentioned_slugs(load_glossary(repo / "docs" / "glossary"), repo)


def test_canonical_name_and_slug_match_case_insensitively(tmp_path: Path) -> None:
    repo = _repo(tmp_path, real_git=False)
    (repo / "AGENTS.md").write_text(
        "Records go to the SESSION-MEMORY store.\n", encoding="utf-8"
    )
    (repo / ".github").mkdir()
    (repo / ".github" / "ci.yml").write_text(
        "name: agent-session probe\n", encoding="utf-8"
    )

    assert _mentioned(repo) == {"session-memory", "agent-session"}


def test_a_compound_word_is_not_a_mention_of_its_part(tmp_path: Path) -> None:
    repo = _repo(tmp_path, real_git=False)
    (repo / "notes.md").write_text(
        "An unlinked-term stays compound.\n", encoding="utf-8"
    )

    assert _mentioned(repo) == set()


def test_the_glossary_directory_itself_never_counts(tmp_path: Path) -> None:
    repo = _repo(tmp_path, real_git=False)
    (repo / "docs" / "glossary" / "principal.md").write_text(
        f"## Principal\n\n{CONSENT}\n\nOwns a session-memory store.\n",
        encoding="utf-8",
    )

    assert _mentioned(repo) == set()


def test_untracked_files_of_a_fresh_stamp_count(tmp_path: Path) -> None:
    """The post-stamp prune runs before the first commit."""
    repo = _repo(tmp_path, real_git=True)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "doctor.sh").write_text(
        "echo 'principal must approve'\n", encoding="utf-8"
    )

    assert _mentioned(repo) == {"principal"}


def test_ignored_files_do_not_count(tmp_path: Path) -> None:
    repo = _repo(tmp_path, real_git=True)
    (repo / ".gitignore").write_text("build/\n", encoding="utf-8")
    (repo / "build").mkdir()
    (repo / "build" / "out.txt").write_text("principal\n", encoding="utf-8")

    assert _mentioned(repo) == set()


def test_binary_files_are_skipped(tmp_path: Path) -> None:
    repo = _repo(tmp_path, real_git=False)
    (repo / "blob.bin").write_bytes(b"principal\x00\x01\x02" * 4)

    assert _mentioned(repo) == set()


def test_a_tree_without_a_usable_git_is_walked_directly(tmp_path: Path) -> None:
    repo = _repo(tmp_path, real_git=False)
    (repo / "README.md").write_text("A principal reads this.\n", encoding="utf-8")

    assert _mentioned(repo) == {"principal"}
