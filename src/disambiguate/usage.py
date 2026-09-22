"""
Usage by link: a term is in use when any file in the repository links it.

Before this module, `prune` counted a term as used only when the roots
reached it. A fresh stamp then lost every vendored term that agent docs
and scripts link but the README does not (disambiguate#84). Now use means
an explicit cross-reference to the term, markdown or wiki syntax, in any
text file the repository carries. Files inside the glossary directory are
excluded: a link from one term to another is a cross-reference, and the
reachability walk already handles those.

A bare mention never counts. Same spelling can mean something else, and
keeping a term for it would blunt prune. `--drift` reports unlinked
mentions.

DECISION:SCOPE: the ticket says "git-tracked". This module reads that as
"what git would carry": tracked files plus untracked files git does not
ignore. The post-stamp prune runs before the first commit, when every
file is untracked. A literal reading would prune the fresh stamp the
ticket protects. Ignored files (build output, caches) stay out. Without
a usable git, the module walks the tree minus `.git/`.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from disambiguate.glossary import Glossary
from disambiguate.parser import extract_all_link_slugs

# Nobody writes prose above this size. Skipping larger files keeps one
# stray dump from turning every prune into a full-disk read.
_MAX_BYTES = 1_000_000
_SNIFF_BYTES = 8_192


def linked_slugs(glossary: Glossary, repo_root: Path) -> set[str]:
    """
    Return slugs of every term that some file under `repo_root` links.

    glossary: the loaded glossary. Files in its directory are not scanned.
    repo_root: the working tree to scan.

    Returns
    -------
    A set of slugs. Empty when no file outside the glossary links a term.
    A link to a slug that names no term is ignored. Links inside code
    never count.

    """
    glossary_dir = glossary.root.resolve()
    found: set[str] = set()
    for path in _candidate_files(repo_root):
        if glossary_dir in path.resolve().parents:
            continue
        text = _read_text(path)
        if text is None:
            continue
        found.update(
            slug for slug in extract_all_link_slugs(text) if slug in glossary.terms
        )
        if len(found) == len(glossary.terms):
            return found
    return found


def _candidate_files(repo_root: Path) -> list[Path]:
    """Every file git would carry, or the whole tree minus `.git/` without git."""
    listed = _git_listed(repo_root)
    if listed is not None:
        return listed
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        files.extend(Path(dirpath) / name for name in filenames)
    return files


def _git_listed(repo_root: Path) -> list[Path] | None:
    """Tracked and untracked-not-ignored paths, or None without a usable git."""
    try:
        result = subprocess.run(
            [  # noqa: S607 — git resolved on PATH by design
                "git",
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            cwd=repo_root,
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return [
        repo_root / entry.decode("utf-8", errors="surrogateescape")
        for entry in result.stdout.split(b"\0")
        if entry
    ]


def _read_text(path: Path) -> str | None:
    """The file's text, or None when the file is binary, oversized or unreadable."""
    try:
        if not path.is_file() or path.stat().st_size > _MAX_BYTES:
            return None
        with path.open("rb") as handle:
            head = handle.read(_SNIFF_BYTES)
            if b"\0" in head:
                return None
            rest = handle.read()
    except OSError:
        return None
    return (head + rest).decode("utf-8", errors="ignore")
